# letters

Source acquisition and conversion experiments for public shareholder letters.

## Berkshire Hathaway

The first target is Warren Buffett's Berkshire Hathaway shareholder letter archive:

- https://www.berkshirehathaway.com/letters/letters.html

The crawler downloads the official index and each linked annual shareholder letter into:

- `output/berkshire/index.html`
- `output/berkshire/sources/<year>.<ext>`
- `output/berkshire/manifest.json`

Run:

```bash
uvx --from hayeah-pymake pymake run berkshire
```

The crawl is intentionally idempotent. Existing source files are reused by default; pass `--force` to the scraper, or run pymake with `-B`, when you want a fresh download.
