"""Tests for shipped package metadata and console script names."""

from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.repo]

#: The README's runtime badge, whose message states the supported interpreters.
RUNTIME_BADGE = re.compile(
    r"!\[runtime\]\(https://img\.shields\.io/badge/runtime-([^-]+)-"
)

#: A ``3.13``-style version inside prose or a badge message.
MINOR_VERSION = re.compile(r"3\.\d+")


def _supported_minors(requires_python: str) -> list[str]:
    """Expand a ``>=3.x,<3.y`` specifier into the minor versions it admits."""
    pairs: list[tuple[str, str]] = re.findall(r"(>=|<)\s*(3\.\d+)", requires_python)
    bounds = dict(pairs)
    low = int(bounds[">="].split(".")[1])
    high = int(bounds["<"].split(".")[1])
    return [f"3.{minor}" for minor in range(low, high)]


def test_project_scripts_ship_vaultspec_core_and_mcp(pyproject: dict[str, Any]) -> None:
    scripts: dict[str, str] = pyproject["project"]["scripts"]

    assert "vaultspec-core" in scripts
    assert scripts["vaultspec-core"] == "vaultspec_core.__main__:main"
    assert "vaultspec-mcp" in scripts
    assert scripts["vaultspec-mcp"] == "vaultspec_core.mcp_server.app:run"
    assert "vaultspec" not in scripts


def test_the_runtime_badge_names_every_supported_interpreter_and_no_other(
    pyproject: dict[str, Any], repo_root: Path
) -> None:
    """The badge is a claim about `requires-python`, so it must not outrun it.

    It read "Python 3.13+" while the specifier was ">=3.13,<3.15". The "+"
    promises every later release, so a reader on 3.15 follows the documented
    path and gets a resolution failure instead of an install. A badge is the
    first thing a reader believes, and nothing here checked it against the
    metadata it describes.
    """
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    badge = RUNTIME_BADGE.search(readme)
    assert badge is not None, "no runtime badge found in README.md"

    claimed = MINOR_VERSION.findall(urllib.parse.unquote(badge.group(1)))
    supported = _supported_minors(pyproject["project"]["requires-python"])

    assert claimed == supported, (
        f"runtime badge claims {claimed} but requires-python admits {supported}"
    )
    # An open-ended marker re-introduces the same lie without changing a number.
    assert "+" not in urllib.parse.unquote(badge.group(1))


def test_the_readme_states_how_to_get_uv_before_telling_you_to_use_it(
    repo_root: Path,
) -> None:
    """Every documented install channel runs through uv, which is not preinstalled.

    A stock macOS machine has no uv, no uvx and no Homebrew, and its system
    Python is 3.9 - below the floor - so "uvx vaultspec-core install" is not a
    runnable instruction on its own. How to get uv must appear, and it must
    appear before the first command that depends on it.
    """
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    # Two forms answer "how do I get uv", and the guard accepts either. The
    # installer script is one. A link to uv's own installation page is the
    # other, and is better in one respect: it stays correct as uv's platform
    # support and install methods change, where a pinned `curl | sh` line in
    # this README goes stale without anything noticing. What the guard is
    # actually protecting is the ORDER below - that the reader is told how to
    # get uv before being handed a command that needs it.
    positions = [
        found
        for marker in (
            "astral.sh/uv/install",
            "astral.sh/uv/getting-started/installation",
        )
        if (found := readme.find(marker)) != -1
    ]
    assert positions, "README never says how to install uv"
    installer = min(positions)

    first_use = min(
        position
        for position in (
            readme.find("uvx vaultspec-core"),
            readme.find("uv tool install"),
            readme.find("uv add "),
        )
        if position != -1
    )
    assert installer < first_use, (
        "the uv install instruction appears after the first command needing it"
    )
