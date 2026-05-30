from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse


INDEX_URL = "https://www.berkshirehathaway.com/letters/letters.html"
OUTPUT_DIR = Path("output/berkshire")
INDEX_PATH = OUTPUT_DIR / "index.html"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
SOURCES_DIR = OUTPUT_DIR / "sources"
USER_AGENT = "hayeah/letters Berkshire source crawler"

HTML_YEARS = range(1977, 1998)
PDF_YEARS = range(2004, 2025)
LANDING_YEARS = range(1998, 2004)
HTML_AND_PDF_YEARS = range(1998, 2002)
PDF_ONLY_LANDING_YEARS = range(2002, 2004)


def expected_source_paths() -> list[Path]:
    paths = [SOURCES_DIR / str(year) / "letter_html.html" for year in HTML_YEARS]

    for year in HTML_AND_PDF_YEARS:
        paths.extend(
            [
                SOURCES_DIR / str(year) / "landing.html",
                SOURCES_DIR / str(year) / "letter_html.html",
                SOURCES_DIR / str(year) / "letter_pdf.pdf",
            ]
        )

    for year in PDF_ONLY_LANDING_YEARS:
        paths.extend(
            [
                SOURCES_DIR / str(year) / "landing.html",
                SOURCES_DIR / str(year) / "letter_pdf.pdf",
            ]
        )

    paths.extend(SOURCES_DIR / str(year) / "letter_pdf.pdf" for year in PDF_YEARS)
    return paths


@dataclass(frozen=True)
class LetterLink:
    year: int
    role: str
    url: str

    @property
    def ext(self) -> str:
        return extension_for_url(self.url)

    @property
    def source_path(self) -> Path:
        return SOURCES_DIR / str(self.year) / f"{self.role}{self.ext}"


@dataclass(frozen=True)
class LetterSource:
    year: int
    role: str
    url: str
    source_path: str
    content_type: str
    bytes: int
    sha256: str


class BerkshireCrawler:
    def __init__(self, force: bool = False) -> None:
        self.force = force

    def fetch_index(self) -> str:
        if INDEX_PATH.exists() and not self.force:
            return INDEX_PATH.read_text(encoding="utf-8", errors="replace")

        response = self.session().get(INDEX_URL, timeout=30)
        response.raise_for_status()
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(response.text, encoding="utf-8")
        return response.text

    def write_manifest_and_sources(self) -> list[LetterSource]:
        index_html = self.fetch_index()
        links = self.source_links(index_html)
        sources = [self.fetch_source(link) for link in links]
        self.write_manifest(sources)
        return sources

    def source_links(self, index_html: str) -> list[LetterLink]:
        links = []
        for year, url in self.parse_index_letter_urls(index_html):
            links.extend(self.source_links_for_year(year, url))
        return links

    def parse_index_letter_urls(self, index_html: str) -> list[tuple[int, str]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(index_html, "html.parser")
        by_year: dict[int, str] = {}

        for link in soup.find_all("a", href=True):
            href = str(link["href"]).strip()
            text = link.get_text(" ", strip=True)
            year = year_from_link(href, text)
            if year is not None:
                by_year[year] = urljoin(INDEX_URL, href)

        return sorted(by_year.items())

    def source_links_for_year(self, year: int, url: str) -> list[LetterLink]:
        role = "landing" if year in LANDING_YEARS else role_for_url(url)
        link = LetterLink(year=year, role=role, url=url)
        if year not in range(1997, 2004) or link.ext != ".html":
            return [link]

        html = self.fetch_source(link).source_path
        linked_urls = self.parse_same_year_source_urls(
            year,
            url,
            Path(html).read_text(encoding="utf-8", errors="replace"),
        )
        return [link, *[LetterLink(year=year, role=role_for_url(u), url=u) for u in linked_urls]]

    def parse_same_year_source_urls(self, year: int, page_url: str, html: str) -> list[str]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        urls = []
        seen = set()

        for link in soup.find_all("a", href=True):
            href = str(link["href"]).strip()
            url = urljoin(page_url, href)
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != urlparse(INDEX_URL).netloc:
                continue
            if year_from_link(href, link.get_text(" ", strip=True)) != year:
                continue
            if extension_for_url(url) not in {".html", ".pdf", ".txt"}:
                continue
            if url == page_url or url in seen:
                continue

            seen.add(url)
            urls.append(url)

        return urls

    def fetch_source(self, link: LetterLink) -> LetterSource:
        source_path = link.source_path
        source_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.exists() and not self.force:
            content = source_path.read_bytes()
            content_type = guess_content_type(link.ext)
        else:
            response = self.session().get(link.url, timeout=60)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "")
            source_path.write_bytes(content)

        return LetterSource(
            year=link.year,
            role=link.role,
            url=link.url,
            source_path=str(source_path),
            content_type=content_type,
            bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def write_manifest(self, sources: list[LetterSource]) -> None:
        payload = {
            "index_url": INDEX_URL,
            "count": len(sources),
            "sources": [asdict(source) for source in sources],
        }
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def session(self):
        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        return session


def year_from_link(href: str, text: str) -> int | None:
    haystack = f"{href} {text}"
    match = re.search(r"\b(19[6-9]\d|20[0-4]\d)\b", haystack)
    if not match:
        return None

    year = int(match.group(1))
    path = urlparse(href).path.lower()
    if not path.endswith((".html", ".htm", ".pdf", ".txt")):
        return None
    return year


def role_for_url(url: str) -> str:
    ext = extension_for_url(url)
    return {
        ".html": "letter_html",
        ".pdf": "letter_pdf",
        ".txt": "letter_text",
    }.get(ext, "letter")


def extension_for_url(url: str) -> str:
    path = urlparse(url).path.lower()
    suffix = Path(path).suffix
    if suffix in {".html", ".htm", ".pdf", ".txt"}:
        return ".html" if suffix == ".htm" else suffix
    return ".bin"


def guess_content_type(ext: str) -> str:
    return {
        ".html": "text/html",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }.get(ext, "application/octet-stream")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["index", "sources"])
    parser.add_argument("--force", action="store_true", help="download even when files already exist")
    args = parser.parse_args()

    crawler = BerkshireCrawler(force=args.force)
    if args.target == "index":
        crawler.fetch_index()
        print(f"wrote {INDEX_PATH}")
        return

    sources = crawler.write_manifest_and_sources()
    print(f"wrote {len(sources)} Berkshire letter sources to {SOURCES_DIR}")


if __name__ == "__main__":
    main()
