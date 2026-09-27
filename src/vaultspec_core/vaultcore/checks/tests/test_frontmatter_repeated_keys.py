"""The frontmatter check flags a repeated key and its fix lets the stamp converge.

A union merge of a ledger keeps both branches' ``modified:`` and
``body_hash:`` lines. Every reader keeps the last occurrence, so a repeated
key hides from the parsed snapshot while a line-based writer edits the
first one. These tests drive the real checkers over real files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from ...body_hash import document_body_digest
from .. import run_all_checks
from ..frontmatter import check_frontmatter

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_BODY = "# `feat` ledger\n\n## Changes\n\n- `S01` `M` `src/foo.py`\n"


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _write_merged_ledger(root: Path) -> Path:
    """Write a ledger shaped like a union merge of two branches' copies."""
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)
    doc = root / ".vault" / "exec" / "2026-02-08-feat" / "2026-02-08-feat-ledger.md"
    doc.parent.mkdir(parents=True)
    left = document_body_digest("---\ndate: x\n---\n\nleft\n")
    right = document_body_digest("---\ndate: x\n---\n\nright\n")
    doc.write_text(
        "---\ntags:\n  - '#exec'\n  - '#feat'\ndate: '2026-02-08'\n"
        "modified: '2026-02-08'\nmodified: '2026-02-09'\n"
        f"body_hash: '{left}'\nbody_hash: '{right}'\n"
        "related:\n  - '[[2026-02-08-feat-plan]]'\n---\n\n" + _BODY,
        encoding="utf-8",
    )
    return doc


def _frontmatter_messages(root: Path) -> list[str]:
    snapshot = VaultGraph(root).to_snapshot()
    return [d.message for d in check_frontmatter(root, snapshot=snapshot).diagnostics]


def test_repeated_keys_are_reported_from_disk(tmp_path: Path) -> None:
    _write_merged_ledger(tmp_path)

    messages = _frontmatter_messages(tmp_path)

    assert len(messages) == 2
    assert "'modified' is written 2 times" in messages[0]
    assert "'body_hash' is written 2 times" in messages[1]


def test_repeated_keys_are_reported_from_the_ingress_texts(tmp_path: Path) -> None:
    doc = _write_merged_ledger(tmp_path)
    graph = VaultGraph(tmp_path)
    graph.ensure_raw_texts()
    text = doc.read_text(encoding="utf-8")
    doc.write_text(text.replace("modified: '2026-02-08'\n", ""), encoding="utf-8")

    result = check_frontmatter(
        tmp_path, snapshot=graph.to_snapshot(), raw_texts=graph.raw_texts
    )

    assert len(result.diagnostics) == 2


def test_fix_keeps_the_last_occurrence_and_touches_nothing_else(
    tmp_path: Path,
) -> None:
    doc = _write_merged_ledger(tmp_path)
    before = doc.read_text(encoding="utf-8")

    result = check_frontmatter(
        tmp_path, snapshot=VaultGraph(tmp_path).to_snapshot(), fix=True
    )

    assert result.fixed_count == 1
    after = doc.read_text(encoding="utf-8")
    first_hash = next(
        line for line in before.split("\n") if line.startswith("body_hash:")
    )
    assert after == before.replace("modified: '2026-02-08'\n", "").replace(
        f"{first_hash}\n", ""
    )
    assert _frontmatter_messages(tmp_path) == []


def test_check_all_fix_converges_on_a_merged_ledger(tmp_path: Path) -> None:
    doc = _write_merged_ledger(tmp_path)

    run_all_checks(tmp_path, fix=True)

    text = doc.read_text(encoding="utf-8")
    assert text.count("\nbody_hash: ") == 1
    assert text.count("\nmodified: ") == 1
    assert f"body_hash: '{document_body_digest(text)}'" in text
    results = {r.check_name: r for r in run_all_checks(tmp_path)}
    assert results["frontmatter"].diagnostics == []
    assert results["modified-stamp"].diagnostics == []
