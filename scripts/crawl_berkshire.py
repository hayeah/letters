from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


INDEX_URL = "https://www.berkshirehathaway.com/letters/letters.html"
OUTPUT_DIR = Path("output/berkshire")
SOURCES_DIR = OUTPUT_DIR / "sources"
USER_AGENT = "hayeah/letters Berkshire source crawler"


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
    def __init__(self, output_dir: Path = OUTPUT_DIR, force: bool = False) -> None:
        self.output_dir = output_dir
        self.sources_dir = output_dir / "sources"
        self.force = force
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def crawl(self) -> list[LetterSource]:
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        index_html = self.fetch_index()
        letter_urls = self.parse_letter_urls(index_html)
        sources = []
        for year, url in letter_urls:
            sources.extend(self.fetch_year_sources(year, url))
        self.write_manifest(sources)
        return sources

    def fetch_index(self) -> str:
        index_path = self.output_dir / "index.html"
        if index_path.exists() and not self.force:
            return index_path.read_text(encoding="utf-8", errors="replace")

        response = self.session.get(INDEX_URL, timeout=30)
        response.raise_for_status()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(response.text, encoding="utf-8")
        return response.text

    def parse_letter_urls(self, index_html: str) -> list[tuple[int, str]]:
        soup = BeautifulSoup(index_html, "html.parser")
        by_year: dict[int, str] = {}

        for link in soup.find_all("a", href=True):
            href = str(link["href"]).strip()
            url = urljoin(INDEX_URL, href)
            text = link.get_text(" ", strip=True)
            year = self.year_from_link(href, text)
            if year is None:
                continue
            by_year[year] = url

        return sorted(by_year.items())

    def year_from_link(self, href: str, text: str) -> int | None:
        haystack = f"{href} {text}"
        match = re.search(r"\b(19[6-9]\d|20[0-4]\d)\b", haystack)
        if not match:
            return None

        year = int(match.group(1))
        path = urlparse(href).path.lower()
        if not path.endswith((".html", ".htm", ".pdf", ".txt")):
            return None
        return year

    def fetch_year_sources(self, year: int, url: str) -> list[LetterSource]:
        source_role = "landing" if 1998 <= year <= 2003 else self.role_for_url(url)
        source = self.fetch_letter(year, source_role, url)
        if year not in range(1997, 2004) or not source.source_path.endswith(".html"):
            return [source]

        html = Path(source.source_path).read_text(encoding="utf-8", errors="replace")
        linked_urls = self.parse_same_year_source_urls(year, url, html)
        if not linked_urls:
            return [source]

        sources = [source]
        for linked_url in linked_urls:
            sources.append(self.fetch_letter(year, self.role_for_url(linked_url), linked_url))
        return sources

    def parse_same_year_source_urls(self, year: int, page_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        seen = set()

        for link in soup.find_all("a", href=True):
            href = str(link["href"]).strip()
            url = urljoin(page_url, href)
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != urlparse(INDEX_URL).netloc:
                continue
            if self.year_from_link(href, link.get_text(" ", strip=True)) != year:
                continue

            ext = self.extension_for_url(url)
            if ext not in {".html", ".pdf", ".txt"}:
                continue
            if url == page_url or url in seen:
                continue

            seen.add(url)
            urls.append(url)

        return urls

    def fetch_letter(self, year: int, role: str, url: str) -> LetterSource:
        ext = self.extension_for_url(url)
        source_path = self.sources_dir / str(year) / f"{role}{ext}"
        source_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.exists() and not self.force:
            content = source_path.read_bytes()
            content_type = self.guess_content_type(ext)
        else:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "")
            source_path.write_bytes(content)

        return LetterSource(
            year=year,
            role=role,
            url=url,
            source_path=str(source_path),
            content_type=content_type,
            bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def role_for_url(self, url: str) -> str:
        ext = self.extension_for_url(url)
        return {
            ".html": "letter_html",
            ".pdf": "letter_pdf",
            ".txt": "letter_text",
        }.get(ext, "letter")

    def extension_for_url(self, url: str) -> str:
        path = urlparse(url).path.lower()
        suffix = Path(path).suffix
        if suffix in {".html", ".htm", ".pdf", ".txt"}:
            return ".html" if suffix == ".htm" else suffix
        return ".bin"

    def guess_content_type(self, ext: str) -> str:
        return {
            ".html": "text/html",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
        }.get(ext, "application/octet-stream")

    def write_manifest(self, sources: list[LetterSource]) -> None:
        payload = {
            "index_url": INDEX_URL,
            "count": len(sources),
            "sources": [asdict(source) for source in sources],
        }
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="download even when files already exist")
    args = parser.parse_args()

    sources = BerkshireCrawler(force=args.force).crawl()
    print(f"wrote {len(sources)} Berkshire letter sources to {SOURCES_DIR}")


if __name__ == "__main__":
    main()
