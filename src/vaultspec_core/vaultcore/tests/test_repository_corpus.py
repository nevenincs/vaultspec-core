"""Parity tests that walk the markdown of this checkout.

Each test pins a shared implementation against the code it replaced, over
every markdown file in the repository: a rebuild must not move one byte for
any document the old code handled. They read the checkout instead of
exercising the library alone, so they are ``repo`` tests, selected by the
``repo`` lane and never by the library lanes. Each reference, and the
synthetic input classes it is also held to, lives beside the unit tests of
the implementation it pins.

No mocks, patches, or skips.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan.test_serialiser import (
    _assert_frontmatter_matches_reference as _assert_plan_frontmatter_matches,
)

from .test_body_hash import _assert_matches_reference as _assert_fence_matches
from .test_frontmatter_render import (
    _assert_matches_reference as _assert_render_matches,
)
from .test_modified_stamp import _assert_stamp_matches_reference

pytestmark = [pytest.mark.repo]

_REPO_ROOT = Path(__file__).resolve().parents[4]

_SKIPPED_DIRS = frozenset({".venv", ".git", "node_modules"})

#: A ``modified:`` line at the margin. Removing it sends the stamp down its
#: insertion path, so both of the stamper's paths meet the whole corpus.
_MODIFIED_LINE_RE = re.compile(r"^modified:[^\n]*\n", re.MULTILINE)


def _repository_markdown() -> list[tuple[Path, str]]:
    """Return every markdown file in the checkout with its decoded text."""
    documents = [
        (path, path.read_bytes().decode("utf-8", "surrogateescape"))
        for path in _REPO_ROOT.rglob("*.md")
        if not _SKIPPED_DIRS.intersection(path.relative_to(_REPO_ROOT).parts)
    ]
    assert len(documents) > 100
    return documents


def test_frontmatter_renderer_matches_its_references() -> None:
    for _path, text in _repository_markdown():
        _assert_render_matches(text.replace("\r\n", "\n"))


def test_fingerprint_fence_matches_its_reference() -> None:
    for _path, text in _repository_markdown():
        _assert_fence_matches(text)


def test_checker_stamp_matches_its_reference() -> None:
    for _path, text in _repository_markdown():
        normalised = text.replace("\r\n", "\n")
        _assert_stamp_matches_reference(normalised)
        _assert_stamp_matches_reference(_MODIFIED_LINE_RE.sub("", normalised, 1))


def test_plan_frontmatter_matches_its_reference() -> None:
    rendered = 0
    for path, text in _repository_markdown():
        if path.parent.name != "plan":
            continue
        try:
            plan = parse_plan(text)
        except ValueError:
            # Only a parsed plan is ever serialised.
            continue
        _assert_plan_frontmatter_matches(plan)
        rendered += 1
    assert rendered > 50
