"""Fixtures shared by every test package under :mod:`dev`.

The instruments in this tree - the release builder, the supply-chain gate, the
asset renderers, the code-health report - all assert against the checkout they
operate on rather than against a temporary fixture directory, because what they
guard IS this repository's configuration. Resolving that checkout once here
keeps each cohabiting ``tests`` package from re-deriving it by counting
directory hops, which is the derivation a move silently breaks.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository checkout the development instruments operate on."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def pyproject(repo_root: Path) -> dict[str, Any]:
    """Return the parsed ``pyproject.toml`` of this checkout."""
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
