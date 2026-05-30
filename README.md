# letters

Source acquisition and conversion experiments for public shareholder letters.

## Berkshire Hathaway

The first target is Warren Buffett's Berkshire Hathaway shareholder letter archive:

- https://www.berkshirehathaway.com/letters/letters.html

The crawler downloads the official index and each linked annual shareholder letter into:

- `output/berkshire/index.html`
- `output/berkshire/sources/<year>/<role>.<ext>`
- `output/berkshire/manifest.json`

Run:

```bash
uvx --from hayeah-pymake pymake run berkshire
```

Useful targets:

```bash
uvx --from hayeah-pymake pymake run berkshire_index
uvx --from hayeah-pymake pymake run berkshire_sources
uvx --from hayeah-pymake pymake which output/berkshire/manifest.json
```

The crawl is intentionally idempotent. Existing source files are reused by default; pass `--force` to the scraper, or run pymake with `-B`, when you want a fresh download.

Some years have multiple official source files. In particular, 1998-2001 have landing pages plus separate HTML and PDF letter versions, while 2002-2003 have landing pages plus PDF letters. The manifest records each source separately with a `role` such as `landing`, `letter_html`, or `letter_pdf`.
