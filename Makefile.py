"""Project tasks.

Run with:
    uvx --from hayeah-pymake pymake run berkshire
"""

from pathlib import Path

from pymake import sh, task

from letters.berkshire import INDEX_PATH, MANIFEST_PATH, expected_source_paths


BERKSHIRE_SOURCE_PATHS = expected_source_paths()
BERKSHIRE_DONE = Path("output/berkshire/.complete")


@task(outputs=[INDEX_PATH])
def berkshire_index():
    """Download the official Berkshire Hathaway letter index."""
    sh("uv run python -m letters.berkshire index")


@task(inputs=[INDEX_PATH], outputs=[MANIFEST_PATH, *BERKSHIRE_SOURCE_PATHS])
def berkshire_sources():
    """Download the official Berkshire Hathaway shareholder letter sources."""
    sh("uv run python -m letters.berkshire sources")


@task(inputs=[berkshire_sources], touch=BERKSHIRE_DONE)
def berkshire():
    """Build the Berkshire Hathaway source archive."""
    pass


task.default(berkshire)
