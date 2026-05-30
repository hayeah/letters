"""Project tasks.

Run with:
    uvx --from hayeah-pymake pymake run berkshire
"""

from pathlib import Path

from pymake import sh, task


BERKSHIRE_OUTPUT = Path("output/berkshire")
BERKSHIRE_MANIFEST = BERKSHIRE_OUTPUT / "manifest.json"


@task(outputs=[BERKSHIRE_MANIFEST])
def berkshire():
    """Download the official Berkshire Hathaway shareholder letter sources."""
    sh("uv run python scripts/crawl_berkshire.py")


task.default(berkshire)
