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
from ..references import check_schema

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _make_skeleton(root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


class TestFrontmatterFixPreservesNewlines:
    def test_crlf_file_remains_crlf_after_fix(self, tmp_path: Path) -> None:
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

    def test_lf_file_remains_lf_after_fix(self, tmp_path: Path) -> None:
        _make_skeleton(tmp_path)
        doc = tmp_path / ".vault" / "adr" / "2026-04-30-y-adr.md"
        doc.write_bytes(b"---\nfeature: beta\ndate: 2026-04-30\n---\n\n# body\n")
        graph = VaultGraph(tmp_path)
        check_frontmatter(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        raw = doc.read_bytes()
        # An originally-LF file must not gain CRLF endings.
        assert b"\r\n" not in raw


class TestAddToRelatedPreservesNewlines:
    """Drives the ``related:`` link fixer through ``check_schema``.

    The fixer that appends ``[[wiki-link]]`` entries is private to
    ``references.py`` and has no consumer outside that module, so these
    tests exercise it the way production code does: a plan missing its
    required ADR reference, fixed via the public ``check_schema`` entry
    point, which appends the link through the same code path.
    """

    def test_crlf_file_remains_crlf_when_appending_related(
        self, tmp_path: Path
    ) -> None:
        _make_skeleton(tmp_path)
        adr = tmp_path / ".vault" / "adr" / "2026-04-30-zeta-adr.md"
        adr.write_text(
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#zeta'\n"
            "date: 2026-04-30\n"
            "related: []\n"
            "---\n\n# body\n",
            encoding="utf-8",
        )
        doc = tmp_path / ".vault" / "plan" / "2026-04-30-zeta-plan.md"
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

        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)
        assert result.fixed_count == 1

        raw = doc.read_bytes()
        without_crlf = raw.replace(b"\r\n", b"")
        assert b"\n" not in without_crlf
        assert b"\r\n  - '[[2026-04-30-zeta-adr]]'" in raw
        assert b'\r\n  - "[[2026-04-30-zeta-adr]]"' not in raw

    def test_empty_related_field_expands_with_single_quoted_link(
        self, tmp_path: Path
    ) -> None:
        _make_skeleton(tmp_path)
        adr = tmp_path / ".vault" / "adr" / "2026-04-30-eta-adr.md"
        adr.write_text(
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#eta'\n"
            "date: 2026-04-30\n"
            "related: []\n"
            "---\n\n# body\n",
            encoding="utf-8",
        )
        doc = tmp_path / ".vault" / "plan" / "2026-04-30-eta-plan.md"
        doc.write_text(
            "---\n"
            "tags:\n"
            "  - '#plan'\n"
            "  - '#eta'\n"
            "date: 2026-04-30\n"
            "related: []\n"
            "---\n\n"
            "# body\n",
            encoding="utf-8",
        )

        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)
        assert result.fixed_count == 1

        text = doc.read_text(encoding="utf-8")
        assert "related:\n  - '[[2026-04-30-eta-adr]]'" in text
        assert '"[[2026-04-30-eta-adr]]"' not in text
