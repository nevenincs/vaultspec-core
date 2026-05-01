"""Tests that ``--fix`` paths preserve the source file newline convention.

A document arriving with CRLF (``\r\n``) line endings must leave with
CRLF after any vault checker rewrites it; mixing LF and CRLF inside a
single file is a regression. These tests use real filesystem writes and
read raw bytes so the newline convention is observable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from ..frontmatter import check_frontmatter
from ..references import _add_related_link

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _make_skeleton(root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


class TestFrontmatterFixPreservesNewlines:
    def test_crlf_file_remains_crlf_after_fix(self, tmp_path):
        _make_skeleton(tmp_path)
        doc = tmp_path / ".vault" / "adr" / "2026-04-30-x-adr.md"
        # Bare ``feature:`` field is what triggers the frontmatter fixer
        # to rebuild the tags block.
        doc.write_bytes(
            b"---\r\nfeature: alpha\r\ndate: 2026-04-30\r\n---\r\n\r\n# body\r\n"
        )
        graph = VaultGraph(tmp_path)
        check_frontmatter(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        raw = doc.read_bytes()
        # No bare LF outside of CRLF pairs.
        without_crlf = raw.replace(b"\r\n", b"")
        assert b"\n" not in without_crlf
        assert b"\r\n" in raw

    def test_lf_file_remains_lf_after_fix(self, tmp_path):
        _make_skeleton(tmp_path)
        doc = tmp_path / ".vault" / "adr" / "2026-04-30-y-adr.md"
        doc.write_bytes(b"---\nfeature: beta\ndate: 2026-04-30\n---\n\n# body\n")
        graph = VaultGraph(tmp_path)
        check_frontmatter(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        raw = doc.read_bytes()
        # An originally-LF file must not gain CRLF endings.
        assert b"\r\n" not in raw


class TestAddToRelatedPreservesNewlines:
    def test_crlf_file_remains_crlf_when_appending_related(self, tmp_path):
        _make_skeleton(tmp_path)
        doc = tmp_path / ".vault" / "plan" / "2026-04-30-z-plan.md"
        doc.write_bytes(
            b"---\r\n"
            b"tags:\r\n"
            b"  - '#plan'\r\n"
            b"  - '#zeta'\r\n"
            b"date: 2026-04-30\r\n"
            b"related:\r\n"
            b"  - '[[seed]]'\r\n"
            b"---\r\n\r\n"
            b"# body\r\n"
        )
        changed = _add_related_link(doc, "added-target")
        assert changed is True

        raw = doc.read_bytes()
        without_crlf = raw.replace(b"\r\n", b"")
        assert b"\n" not in without_crlf
        assert b'\r\n  - "[[added-target]]"' in raw or (
            b"\r\n  - '[[added-target]]'" in raw
        )
