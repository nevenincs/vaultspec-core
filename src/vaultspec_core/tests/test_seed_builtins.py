"""Outcome-classification tests for :func:`seed_builtins`.

``seed_builtins`` reports per-builtin canonical actions so the
``install --upgrade`` surface can render created/updated/unchanged
outcomes (cli-sync-vocabulary ADR) instead of a flat re-seeded count.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.builtins import seed_builtins

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


class TestSeedBuiltinsOutcomes:
    def test_empty_target_reports_all_added(self, tmp_path: Path):
        results = seed_builtins(tmp_path, force=True)
        assert results, "bundled builtins should exist"
        assert all(action == "[ADD]" for _rel, action in results)

    def test_reseed_of_identical_tree_reports_unchanged(self, tmp_path: Path):
        seed_builtins(tmp_path, force=True)
        results = seed_builtins(tmp_path, force=True)
        assert results
        assert all(action == "[UNCHANGED]" for _rel, action in results)

    def test_modified_builtin_reports_updated(self, tmp_path: Path):
        first = seed_builtins(tmp_path, force=True)
        drifted = first[0][0]
        (tmp_path / drifted).write_text("local drift\n", encoding="utf-8")

        results = dict(seed_builtins(tmp_path, force=True))

        assert results[drifted] == "[UPDATE]"
        # Every other builtin is still unchanged.
        assert all(
            action == "[UNCHANGED]"
            for rel, action in results.items()
            if rel != drifted
        )

    def test_no_force_skips_existing_builtins(self, tmp_path: Path):
        seed_builtins(tmp_path, force=True)
        # Without force, builtins that already exist are skipped outright
        # and never appear in the result.
        assert seed_builtins(tmp_path, force=False) == []
