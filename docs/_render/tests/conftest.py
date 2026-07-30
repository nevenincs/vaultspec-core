"""Fixtures for the documentation asset-renderer guards.

These assert against the checkout the renderers actually read - the real
``.vault/`` corpus, the real ``docs/assets/`` output directory - rather than a
temporary fixture tree, because what they guard IS this repository's content.
Resolving the checkout once here keeps each test off the directory-hop
arithmetic a move silently breaks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository checkout the renderers read and write."""
    return REPO_ROOT


@pytest.fixture
def preserved_no_color() -> Generator[None]:
    """Restore ``NO_COLOR`` around tests that import the asset renderers.

    :mod:`docs._render.render_readme_assets` deletes ``NO_COLOR`` from the process
    environment at import time, because its recording consoles are never a real
    terminal and must emit colour regardless of the shell that started them.
    That is correct for a renderer but leaks into any session that also runs the
    CLI test suite, which sets ``NO_COLOR=1`` globally. Snapshotting the
    variable here keeps the import side effect inside the test that triggers
    it.
    """
    saved = os.environ.get("NO_COLOR")
    yield
    if saved is None:
        os.environ.pop("NO_COLOR", None)
    else:
        os.environ["NO_COLOR"] = saved
