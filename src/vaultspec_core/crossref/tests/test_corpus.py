"""The ADR corpus and the code-only stage, on real files and without a provider."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.enums import AdrStatus
from vaultspec_core.crossref._corpus import (
    CorpusTooLargeError,
    clip,
    fingerprint,
    load_adrs,
)
from vaultspec_core.crossref._engine import _deal, _selection, max_evaluations
from vaultspec_core.crossref._prefilter import Index, fuse
from vaultspec_core.crossref._questions import (
    CHOICE_CHUNK,
    CUT,
    DECISION_CHARS,
    DECLARED_EXTRA,
    MAX_CORPUS,
    POOL,
)

from .vault import write_adr

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def test_a_record_reads_as_header_decision_and_links(tmp_path: Path) -> None:
    write_adr(tmp_path, "2026-01-01-other-adr")
    write_adr(
        tmp_path,
        "2026-01-02-cache-adr",
        feature="graph-cache",
        title="keep the graph cache fresh",
        status="superseded",
        problem="Rebuilding the graph costs seconds.\n\nA second paragraph.",
        related=("2026-01-01-other-adr", "2026-01-05-some-research"),
        extra="## Considerations\n\nScope includes external writers.",
    )

    record = {r.stem: r for r in load_adrs(tmp_path)}["2026-01-02-cache-adr"]

    assert record.feature == "graph-cache"
    assert record.title == "keep the graph cache fresh"
    assert record.status is AdrStatus.SUPERSEDED
    assert record.lead == "Rebuilding the graph costs seconds."
    assert record.header() == (
        "[graph-cache] keep the graph cache fresh. Rebuilding the graph costs seconds."
    )
    assert "## Implementation" in record.decision
    assert "Scope includes external writers" in record.decision
    assert not record.input_truncated
    # A research record is no ADR link.
    assert record.declared == ("2026-01-01-other-adr",)
    assert record.rel_path == ".vault/adr/2026-01-02-cache-adr.md"


def test_the_decision_state_is_bounded(tmp_path: Path) -> None:
    write_adr(tmp_path, "2026-01-02-long-adr", implementation="word " * 5_000)

    (record,) = load_adrs(tmp_path)

    assert len(record.decision) <= DECISION_CHARS
    assert record.input_truncated


def test_decision_sections_and_custom_amendments_are_not_silently_omitted(
    tmp_path: Path,
) -> None:
    write_adr(
        tmp_path,
        "2026-01-02-durable-adr",
        extra=(
            "## Decision\n\nNever acknowledge uncommitted writes.\n\n"
            "## Scope amendment\n\nThis also binds the external writer.\n\n"
            "## Scope amendment\n\nThe read-only importer is exempt."
        ),
    )
    (record,) = load_adrs(tmp_path)
    assert "Never acknowledge uncommitted writes" in record.decision
    assert "external writer" in record.decision
    assert "read-only importer is exempt" in record.decision
    assert not record.input_truncated


def test_long_context_cannot_displace_a_short_constraint(tmp_path: Path) -> None:
    write_adr(
        tmp_path,
        "2026-01-02-durable-adr",
        problem="History and motivation. " * 500,
        implementation="A tentative implementation approach. " * 500,
        extra=(
            "## Constraints\n\n### Durability\n\nNever acknowledge uncommitted writes."
        ),
    )
    (record,) = load_adrs(tmp_path)
    assert "Never acknowledge uncommitted writes" in record.decision
    assert len(record.decision) <= DECISION_CHARS
    assert record.input_truncated


def test_pathological_section_count_stays_bounded(tmp_path: Path) -> None:
    write_adr(
        tmp_path,
        "2026-01-02-many-adr",
        extra="\n\n".join(f"## Clause {i}\n\nObligation." for i in range(4000)),
    )
    (record,) = load_adrs(tmp_path)
    assert len(record.decision) <= DECISION_CHARS
    assert record.input_truncated


def test_the_fingerprint_names_artifacts_not_prose() -> None:
    body = (
        "Uses `src/vaultspec_core/graph/cache.py:42` and `build_graph()`; runs "
        "`vaultspec-core vault check all --fix`. Status `accepted`, count `12`, "
        "see `2026-01-02-other-adr`, emphasis `NOTE`. <!-- `hidden.py` -->"
    )

    found = fingerprint(body)

    assert set(found) == {
        "src/vaultspec_core/graph/cache.py",
        "build_graph",
        "vaultspec-core vault check all",
    }


def test_clip_keeps_words_and_marks_the_cut() -> None:
    assert clip("short", 10) == "short"
    cut = clip("one two three four five six", 15)
    assert len(cut) <= 15
    assert cut.endswith("\N{HORIZONTAL ELLIPSIS}")
    assert cut.startswith("one two")


def test_a_corpus_over_the_ceiling_is_refused_before_reading(tmp_path: Path) -> None:
    directory = tmp_path / ".vault" / "adr"
    directory.mkdir(parents=True)
    for number in range(MAX_CORPUS + 1):
        (directory / f"2026-01-01-n{number}-adr.md").write_bytes(b"\xff")

    with pytest.raises(CorpusTooLargeError) as caught:
        load_adrs(tmp_path)
    assert caught.value.count == MAX_CORPUS + 1


def test_a_shared_artifact_outranks_a_shared_title_word(tmp_path: Path) -> None:
    write_adr(
        tmp_path,
        "2026-01-01-source-adr",
        title="lock files",
        implementation=(
            "Writers take `vaultcore/edit_engine.py` and `document_write_lock`."
        ),
    )
    write_adr(
        tmp_path,
        "2026-01-02-sharer-adr",
        title="rename safety",
        implementation="Renames take `document_write_lock` too.",
    )
    write_adr(tmp_path, "2026-01-03-titled-adr", title="lock files for tests")
    for number in range(6):
        write_adr(tmp_path, f"2026-01-1{number}-filler-adr", title=f"filler {number}")
    index = Index(load_adrs(tmp_path))
    source = index.records["2026-01-01-source-adr"]

    by_artifact, _ = index.signals(source)

    assert by_artifact[0] == "2026-01-02-sharer-adr"
    assert "2026-01-01-source-adr" not in index.rank(source)
    assert index.distinctive("2026-01-01-source-adr") == ["document_write_lock"]


def test_fusion_weights_ranks_and_breaks_ties_by_stem() -> None:
    assert fuse(((1.0, ["b", "a"]), (1.0, ["a", "b"]))) == ["a", "b"]
    assert fuse(((2.0, ["c", "a"]), (1.0, ["a", "c"])))[0] == "c"


def test_the_pool_is_dealt_into_balanced_chunks() -> None:
    pool = [f"s{i}" for i in range(POOL)]

    chunks = _deal(pool)

    assert len(chunks) == -(-POOL // CHOICE_CHUNK)
    assert all(len(chunk) <= CHOICE_CHUNK for chunk in chunks)
    assert max(map(len, chunks)) - min(map(len, chunks)) <= 1
    assert sorted(s for chunk in chunks for s in chunk) == sorted(pool)
    assert chunks[0][0] == "s0"
    assert chunks[1][0] == "s1"


def test_declared_links_outside_the_cut_are_judged_up_to_the_ceiling(
    tmp_path: Path,
) -> None:
    fused = [f"c{i:03d}" for i in range(100)]
    declared = (*(f"c{i:03d}" for i in range(95, 95 - 14, -1)), "c001")
    write_adr(tmp_path, "2026-01-01-src-adr")
    (source,) = load_adrs(tmp_path)
    source = replace(source, declared=declared)

    judged, unjudged = _selection(source, fused)

    assert judged[:CUT] == fused[:CUT]
    extra = judged[CUT:]
    assert len(extra) == DECLARED_EXTRA
    # Best fused rank first, and a declared link already in the cut is not
    # judged twice.
    assert extra == sorted(extra)
    assert "c001" not in extra
    assert len(unjudged) == len(declared) - 1 - DECLARED_EXTRA


def test_a_source_has_a_fixed_evaluation_ceiling() -> None:
    assert max_evaluations() == -(-POOL // CHOICE_CHUNK) + CUT + DECLARED_EXTRA == 46
