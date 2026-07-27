"""Complexity budgets for the check pipeline, asserted as operation counts.

The scale gate enforces the complexity budgets mechanically and
deterministically: instead of wall-clock thresholds (flaky on shared CI
runners), it counts real operations with ``sys.setprofile`` - observation of
the genuine execution, never a stub - over synthetic corpora generated at
test time at two sizes, and asserts:

- **Single ingress:** a non-mutating ``run_all_checks`` pass reads each
  corpus document exactly once, at every corpus size.
- **Memoized plan parsing:** the pass parses no more plans than the corpus
  contains, no matter how many execution records reference them.
- **No superlinear checks:** tag-extraction work (the signature operation of
  the banned O(features x documents) scan shape) grows at most linearly
  between the two corpus sizes.

Marked ``benchmark`` so the default run (which deselects ``benchmark`` via
``addopts``) skips the corpus generation cost; run explicitly with
``pytest -m benchmark``.
"""

from __future__ import annotations

import sys
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from ...vaultcore.checks import run_all_checks
from ...vaultcore.scanner import scan_vault

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.benchmark]

_SMALL = 120
_LARGE = 480

#: Allowed growth factor for per-document operations across the 4x corpus
#: step. Linear scaling gives ~4x; the banned quadratic shape gives ~16x.
_LINEAR_SLACK = 6.0


def _profile_counts(fn) -> Counter[str]:
    """Run *fn* under a profiler, counting the operations the gate budgets."""
    counts: Counter[str] = Counter()

    def profiler(frame, event: str, arg: object) -> None:
        if event != "call":
            return
        name = frame.f_code.co_name
        if name in ("read_bytes", "read_text"):
            target = frame.f_locals.get("self")
            parts = getattr(target, "parts", None)
            if parts and ".vault" in parts and str(target).endswith(".md"):
                counts["corpus_reads"] += 1
        elif name in ("parse_plan", "extract_feature_tags"):
            counts[name] += 1

    sys.setprofile(profiler)
    try:
        fn()
    finally:
        sys.setprofile(None)
    return counts


def _prepare_corpus(root: Path, n_docs: int) -> tuple[int, int]:
    """Build a corpus and settle migrations; return (doc, plan) counts."""
    reset_config()
    build_synthetic_vault(root, n_docs=n_docs, seed=17, edge_probability=0.3)
    # One throwaway scan settles any pending migrations so the instrumented
    # pass observes only the check pipeline's own reads.
    scanned = list(scan_vault(root))
    plans = sum(1 for p in scanned if p.parent.name == "plan")
    return len(scanned), plans


class TestComplexityBudgets:
    @pytest.mark.parametrize("n_docs", [_SMALL, _LARGE])
    def test_single_ingress_read_budget(self, tmp_path: Path, n_docs: int) -> None:
        doc_count, plan_count = _prepare_corpus(tmp_path, n_docs)

        counts = _profile_counts(lambda: run_all_checks(tmp_path, fix=False))

        assert counts["corpus_reads"] == doc_count, (
            f"the pass read the corpus {counts['corpus_reads']} times for "
            f"{doc_count} documents; the single-ingress budget is exactly one "
            "read per document"
        )
        assert counts["parse_plan"] <= plan_count, (
            f"{counts['parse_plan']} plan parses for {plan_count} plan "
            "documents; per-plan parsing must be memoized"
        )

    def test_tag_extraction_scales_linearly(self, tmp_path: Path) -> None:
        small_root = tmp_path / "small"
        large_root = tmp_path / "large"
        small_root.mkdir()
        large_root.mkdir()

        _prepare_corpus(small_root, _SMALL)
        small = _profile_counts(lambda: run_all_checks(small_root, fix=False))

        _prepare_corpus(large_root, _LARGE)
        large = _profile_counts(lambda: run_all_checks(large_root, fix=False))

        assert small["extract_feature_tags"] > 0
        ratio = large["extract_feature_tags"] / small["extract_feature_tags"]
        assert ratio <= _LINEAR_SLACK, (
            f"tag extraction grew {ratio:.1f}x across a 4x corpus step; the "
            "budget is linear growth (a features x documents scan shape "
            "regressed)"
        )
