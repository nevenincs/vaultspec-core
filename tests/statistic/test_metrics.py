"""Tests for the seven metric families over a synthetic ``CallRecord`` set.

Every record here is built in code by :func:`_record`, never read from a
transcript, so the metric assertions depend on no machine state, no username, no
absolute path, and no wall-clock date beyond a fixed timezone-aware anchor used
only to satisfy the model's aware-timestamp requirement. Each test asserts the
exact aggregate a hand-constructed record set must produce, so a regression in
any counter or ranking surfaces as a value mismatch rather than a silent drift.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from statistic.metrics.capability import CapabilityInventory
from statistic.metrics.cost import SourceCost, VerbCost, compute_cost
from statistic.metrics.feature_tags import FeatureTagCount, compute_feature_tag_usage
from statistic.metrics.features import compute_features_utilized
from statistic.metrics.hotspots import VerbHotspot, compute_hotspots
from statistic.metrics.misses import (
    RetryCorrection,
    UndeclaredFlagCandidate,
    VerbErrorCount,
    compute_misses,
)
from statistic.metrics.ngrams import FlagCooccurrence, compute_ngrams
from statistic.metrics.surface import compute_surface
from statistic.normalize.exit_status import ExitStatus
from statistic.normalize.models import CallRecord

_ANCHOR = datetime(2000, 1, 1, tzinfo=UTC)


def _record(
    verb_path: tuple[str, ...],
    *,
    flags: dict[str, str | bool] | None = None,
    feature_tag: str | None = None,
    exit_status: ExitStatus = ExitStatus.OK,
    token_cost: int | None = None,
    source: Literal["claude", "codex"] = "claude",
    session_id: str = "s1",
    retry_key: str | None = None,
    order: int = 0,
) -> CallRecord:
    """Build one synthetic record with only the fields a metric reads.

    The ``order`` argument becomes a monotonic offset on the timestamp so a
    session's records carry a deterministic sequence for retry-correction
    detection without pinning any real date.
    """
    return CallRecord(
        source=source,
        session_id=session_id,
        timestamp=_ANCHOR.replace(minute=order % 60, second=order // 60 % 60),
        project="proj",
        cwd="/work/proj",
        verb=verb_path[0] if verb_path else "",
        subcommand=verb_path,
        flags=flags if flags is not None else {},
        feature_tag=feature_tag,
        command_hash=f"hash-{verb_path}-{order}",
        exit_status=exit_status,
        token_cost=token_cost,
        retry_key=retry_key,
    )


def _inventory() -> CapabilityInventory:
    """A small hand-built declared-capability denominator."""
    return CapabilityInventory(
        verb_paths=frozenset(
            {
                ("vault", "list"),
                ("vault", "add"),
                ("vault", "check", "all"),
                ("status",),
                ("sync",),
            }
        ),
        flags={
            ("vault", "add"): frozenset({"--feature", "--step"}),
            ("vault", "list"): frozenset({"--feature"}),
            ("vault", "check", "all"): frozenset({"--fix"}),
        },
    )


# --- (a) hotspots -----------------------------------------------------------


def test_hotspots_rank_by_descending_frequency() -> None:
    """Verb paths rank by count, and equal counts break on the path."""
    records = [
        _record(("vault", "list")),
        _record(("vault", "list")),
        _record(("vault", "list")),
        _record(("vault", "add")),
        _record(("vault", "add")),
        _record(("status",)),
    ]
    assert compute_hotspots(records) == (
        VerbHotspot(("vault", "list"), 3),
        VerbHotspot(("vault", "add"), 2),
        VerbHotspot(("status",), 1),
    )


def test_hotspots_over_empty_stream_is_empty() -> None:
    """No records yields no hotspots rather than an error."""
    assert compute_hotspots([]) == ()


# --- (b) n-grams ------------------------------------------------------------


def test_ngram_patterns_count_verb_and_flag_shapes() -> None:
    """Distinct ``(verb path, flag names)`` shapes count independently."""
    records = [
        _record(("vault", "add"), flags={"--feature": "x", "--step": "S01"}),
        _record(("vault", "add"), flags={"--feature": "y", "--step": "S02"}),
        _record(("vault", "add"), flags={"--feature": "z"}),
    ]
    report = compute_ngrams(records)
    assert report.patterns[0].verb_path == ("vault", "add")
    assert report.patterns[0].flags == ("--feature", "--step")
    assert report.patterns[0].count == 2
    assert report.patterns[1].flags == ("--feature",)
    assert report.patterns[1].count == 1


def test_ngram_flag_cooccurrence_pairs_are_sorted() -> None:
    """Co-occurring flags count as an unordered, sorted pair."""
    records = [
        _record(("vault", "add"), flags={"--step": "S01", "--feature": "x"}),
        _record(("vault", "add"), flags={"--feature": "y", "--step": "S02"}),
        _record(("vault", "list"), flags={"--feature": "z"}),
    ]
    report = compute_ngrams(records)
    assert report.cooccurrences == (FlagCooccurrence(("--feature", "--step"), 2),)


# --- (c) features utilized --------------------------------------------------


def test_features_partition_declared_from_undeclared() -> None:
    """Observed verbs split into declared-and-used versus undeclared."""
    records = [
        _record(("vault", "list")),
        _record(("vault", "list")),
        _record(("vault", "add")),
        _record(("vault", "nonexistent")),
    ]
    result = compute_features_utilized(records, _inventory())
    assert result.utilized == (("vault", "add"), ("vault", "list"))
    assert result.undeclared == (("vault", "nonexistent"),)


# --- (d) feature-tag usage --------------------------------------------------


def test_feature_tag_distribution_and_tagged_split() -> None:
    """Tag values are counted; tagged and untagged records are tallied."""
    records = [
        _record(("vault", "add"), feature_tag="mcp"),
        _record(("vault", "add"), feature_tag="mcp"),
        _record(("vault", "list"), feature_tag="rag"),
        _record(("status",)),
    ]
    usage = compute_feature_tag_usage(records)
    assert usage.tagged == 3
    assert usage.untagged == 1
    assert usage.counts == (
        FeatureTagCount("mcp", 2),
        FeatureTagCount("rag", 1),
    )


# --- (e) misses -------------------------------------------------------------


def test_misses_count_only_errors_not_findings() -> None:
    """Genuine errors count toward the miss rate; findings never do."""
    records = [
        _record(("vault", "list"), exit_status=ExitStatus.ERROR),
        _record(("vault", "check", "all"), exit_status=ExitStatus.FINDINGS),
        _record(("vault", "list"), exit_status=ExitStatus.OK),
        _record(("vault", "list"), exit_status=ExitStatus.ERROR),
    ]
    report = compute_misses(records, _inventory())
    assert report.total_records == 4
    assert report.error_records == 2
    assert report.miss_rate == 0.5
    assert report.errors_by_verb == (VerbErrorCount(("vault", "list"), 2),)


def test_undeclared_flag_candidates_are_advisory() -> None:
    """A flag absent from a declared verb's inventory is a candidate miss."""
    records = [
        _record(("vault", "list"), flags={"--feature": "x", "--bogus": True}),
        _record(("vault", "nonexistent"), flags={"--whatever": True}),
    ]
    report = compute_misses(records, _inventory())
    # only the declared verb path's undeclared flag is reported; the undeclared
    # verb path's flags are not, since the verb itself is the candidate miss.
    assert report.undeclared_flags == (
        UndeclaredFlagCandidate(("vault", "list"), "--bogus", 1),
    )


def test_retry_correction_pairs_errored_call_with_reflagged_retry() -> None:
    """An errored call then a same-verb different-flag retry is a correction."""
    records = [
        _record(
            ("vault", "add"),
            flags={"--feature": "x"},
            exit_status=ExitStatus.ERROR,
            session_id="s1",
            order=0,
        ),
        _record(
            ("vault", "add"),
            flags={"--feature": "x", "--step": "S01"},
            exit_status=ExitStatus.OK,
            session_id="s1",
            order=1,
        ),
    ]
    report = compute_misses(records, _inventory())
    assert report.retry_corrections == (
        RetryCorrection("s1", "vault", ("--feature",), ("--feature", "--step")),
    )


def test_retry_correction_ignores_identical_reissue() -> None:
    """An errored call retried with the identical flag set is not a correction."""
    records = [
        _record(
            ("vault", "add"),
            flags={"--feature": "x"},
            exit_status=ExitStatus.ERROR,
            session_id="s1",
            order=0,
        ),
        _record(
            ("vault", "add"),
            flags={"--feature": "x"},
            exit_status=ExitStatus.ERROR,
            session_id="s1",
            order=1,
        ),
    ]
    report = compute_misses(records, _inventory())
    assert report.retry_corrections == ()


# --- (f) surface ------------------------------------------------------------


def test_surface_reports_dead_and_observed_and_undeclared() -> None:
    """Observed-declared, undeclared usage, and dead surface partition cleanly."""
    records = [
        _record(("vault", "list")),
        _record(("vault", "list")),
        _record(("vault", "add")),
        _record(("vault", "nonexistent")),
    ]
    report = compute_surface(records, _inventory())
    assert report.observed_declared == (
        VerbHotspot(("vault", "list"), 2),
        VerbHotspot(("vault", "add"), 1),
    )
    assert report.undeclared_usage == (VerbHotspot(("vault", "nonexistent"), 1),)
    # declared but never invoked: status, sync, vault check all.
    assert report.dead_surface == (
        ("status",),
        ("sync",),
        ("vault", "check", "all"),
    )
    assert report.declared_total == 5
    assert report.observed_declared_count == 2
    assert report.coverage == 2 / 5


# --- (g) cost ---------------------------------------------------------------


def test_cost_groups_attributed_tokens_by_verb() -> None:
    """Attributed token cost sums per verb class, ranked by cost."""
    records = [
        _record(("vault", "add"), token_cost=100),
        _record(("vault", "add"), token_cost=50),
        _record(("vault", "list"), token_cost=10),
        _record(("status",), token_cost=None),
    ]
    report = compute_cost(records)
    assert report.total_cost == 160
    assert report.by_verb[0] == VerbCost("vault", 160, 3, 3)
    assert report.by_verb[1] == VerbCost("status", 0, 1, 0)


def test_cost_reports_per_source_totals_separately() -> None:
    """Claude and Codex token totals are kept separate for directionality."""
    records = [
        _record(("vault", "add"), token_cost=100, source="claude"),
        _record(("vault", "list"), token_cost=40, source="codex"),
    ]
    report = compute_cost(records)
    assert report.by_source == (
        SourceCost("claude", 100, 1),
        SourceCost("codex", 40, 1),
    )
