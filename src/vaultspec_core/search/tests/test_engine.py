"""The engine's pure logic: questions, packing, shortlist, windows and ranking."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

import pytest

from vaultspec_core.search._corpus import Record
from vaultspec_core.search._engine import (
    MAX_CHOICE_OPTIONS,
    Judgment,
    Meter,
    Question,
    build_wide_questions,
    build_windows,
    excerpt_blocks,
    kind_question,
    option_keys,
    pack_requests,
    rank,
    shortlist,
)
from vaultspec_core.search._questions import (
    KIND_WEIGHT,
    MODEL,
    NO_RECORD,
    NONE_KEY,
    SECOND_BLOCK_FLOOR,
    SHORTLIST_FLOOR,
    SHORTLIST_PER_GROUP,
    SHORTLIST_SIZE,
    WIDE,
)
from vaultspec_core.search._transport import ChoiceAnswer, Evaluation, estimate_tokens
from vaultspec_core.vaultcore.markdown import Block
from vaultspec_core.vaultcore.models import DocType

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit]

#: The typographic stand-ins the transport maps angle brackets to.
LA = "\N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}"
RA = "\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}"


def record(
    name: str,
    doc_type: DocType = DocType.ADR,
    *,
    date: str = "2026-01-02",
    body: str = "",
    title: str | None = None,
) -> Record:
    """An in-memory record; engine logic never touches its path."""
    rel_path = f".vault/{doc_type.value}/{name}.md"
    return Record(
        name=name,
        path=Path(rel_path),
        rel_path=rel_path,
        doc_type=doc_type,
        feature="demo",
        date=date,
        title=title if title is not None else f"{name} title",
        body=body,
        body_line=1,
    )


def block(line: int, text: str = "text") -> Block:
    return Block(heading_path=("Section",), line_start=line, line_end=line, text=text)


def choice(
    probabilities: Mapping[str, float], chosen: str | None = None
) -> ChoiceAnswer:
    best = chosen or max(probabilities, key=lambda key: probabilities[key])
    return ChoiceAnswer(
        choice=best,
        probabilities=MappingProxyType(dict(probabilities)),
        confidence=probabilities.get(best, 0.0),
    )


class TestOptionKeys:
    def test_date_prefix_is_dropped(self) -> None:
        assert option_keys([record("2026-01-02-cache-adr")]) == ["cache-adr"]

    def test_colliding_keys_are_disambiguated(self) -> None:
        records = [
            record("2026-01-02-cache-adr"),
            record("2026-03-04-cache-adr", date="2026-03-04"),
        ]

        assert option_keys(records) == ["cache-adr", "cache-adr-2"]

    def test_no_record_ever_takes_the_no_match_key(self) -> None:
        assert option_keys([record("2026-01-02-none")]) == ["none-2"]

    def test_undated_record_keeps_its_stem(self) -> None:
        assert option_keys([record("notes-adr", date="")]) == ["notes-adr"]

    def test_mismatched_date_keeps_the_stem(self) -> None:
        assert option_keys([record("2026-01-02-x-adr", date="2026-05-05")]) == [
            "2026-01-02-x-adr"
        ]


class TestWideQuestions:
    def test_one_choice_per_group_with_a_no_match_option(self) -> None:
        records = [
            record("2026-01-02-a-adr"),
            record("2026-01-02-b-reference", DocType.REFERENCE),
            record("2026-01-02-c-audit", DocType.AUDIT),
            record("2026-01-02-d-exec", DocType.EXEC),
        ]

        questions = build_wide_questions(records, bound=20_000)

        assert [q.qid for q in questions] == [
            "wide_adr_0",
            "wide_reference_audit_0",
            "wide_exec_0",
        ]
        shared = questions[1]
        criteria = cast("dict[str, object]", shared.payload["criteria"])
        assert list(criteria) == ["b-reference", "c-audit", NONE_KEY]
        assert criteria[NONE_KEY] == NO_RECORD
        assert shared.payload["instructions"] == WIDE
        assert shared.tokens == pytest.approx(estimate_tokens(shared.payload))

    def test_cards_are_sanitised(self) -> None:
        (question,) = build_wide_questions(
            [record("2026-01-02-a-adr", title="`python -m pytest` <b>")], bound=20_000
        )

        (option,) = question.options
        # Code spans are unwrapped for reading; angle brackets are mapped.
        assert option.card == {"title": f"python -m pytest {LA}b{RA}"}

    def test_a_group_over_the_bound_is_split(self) -> None:
        body = "".join(f"## Distinct topic {i}\n\ntext\n\n" for i in range(10))
        records = [record(f"2026-01-02-r{i:02d}-adr", body=body) for i in range(30)]

        questions = build_wide_questions(records, bound=1_000)

        assert len(questions) > 1
        assert all(q.qid.startswith("wide_adr_") for q in questions)
        assert all(q.tokens <= 1_000 for q in questions)
        assert sum(len(q.options) for q in questions) == 30

    def test_a_group_over_the_option_cap_is_split(self) -> None:
        records = [
            record(f"2026-01-02-r{i:03d}-plan", DocType.PLAN)
            for i in range(MAX_CHOICE_OPTIONS + 3)
        ]

        questions = build_wide_questions(records, bound=1_000_000)

        assert [len(q.options) for q in questions] == [MAX_CHOICE_OPTIONS, 3]


class TestPacking:
    def test_questions_pack_in_order_up_to_the_target(self) -> None:
        questions = [
            Question(f"q{i}", {}, tokens) for i, tokens in enumerate([5, 5, 5, 8, 2])
        ]

        requests = pack_requests(questions, target=12)

        assert [[q.qid for q in request] for request in requests] == [
            ["q0", "q1"],
            ["q2"],
            ["q3", "q4"],
        ]

    def test_oversize_question_travels_alone(self) -> None:
        questions = [Question("small", {}, 1), Question("big", {}, 50)]

        assert [len(r) for r in pack_requests(questions, target=10)] == [1, 1]

    def test_kind_question_shares_the_first_request(self) -> None:
        kind = kind_question()
        wide = build_wide_questions(
            [record("2026-01-02-a-adr"), record("2026-01-02-b-plan", DocType.PLAN)],
            bound=20_000,
        )

        (request,) = pack_requests([kind, *wide])

        assert [q.qid for q in request] == ["kind", "wide_adr_0", "wide_plan_0"]


class TestShortlist:
    def test_takes_group_leaders_above_the_floor(self) -> None:
        adrs = [record(f"2026-01-02-a{i}-adr") for i in range(6)]
        plans = [record(f"2026-01-02-p{i}-plan", DocType.PLAN) for i in range(3)]
        wide = {r.rel_path: 0.1 + i / 100 for i, r in enumerate(adrs)}
        wide |= {plans[0].rel_path: 0.5, plans[1].rel_path: SHORTLIST_FLOOR / 2}

        picked = shortlist([*adrs, *plans], wide, [])

        assert picked[0] is plans[0]
        assert [r.name for r in picked[1:]] == [
            f"2026-01-02-a{i}-adr" for i in (5, 4, 3, 2)
        ]
        assert len(picked[1:]) == SHORTLIST_PER_GROUP

    def test_total_is_capped(self) -> None:
        records = [
            record(f"2026-01-02-x{i}-{t.value}", t)
            for t in (DocType.ADR, DocType.PLAN, DocType.RESEARCH)
            for i in range(4)
        ]
        wide = {r.rel_path: 0.3 for r in records}

        assert len(shortlist(records, wide, [])) == SHORTLIST_SIZE

    def test_lexical_matches_join_once(self) -> None:
        a, b, c = (record(f"2026-01-02-{n}-adr") for n in "abc")

        picked = shortlist([a, b, c], {a.rel_path: 0.9}, [c, a, b])

        assert picked == [a, c, b]


class TestWindows:
    def test_ids_number_the_record_and_windows_fit_the_bound(self) -> None:
        blocks = [block(i, "word " * 200) for i in range(1, 11)]
        one = estimate_tokens({"b000": {"section": "Section", "text": "word " * 200}})

        windows = build_windows(blocks, base_tokens=100, bound=100 + 3.5 * one)

        assert [len(w) for w in windows] == [3, 3, 3, 1]
        ids = [bid for window in windows for bid, _ in window]
        assert ids == [f"b{i:03d}" for i in range(10)]
        assert [b for window in windows for _, b in window] == blocks

    def test_oversize_block_travels_alone(self) -> None:
        blocks = [block(1, "x" * 50_000), block(2)]

        windows = build_windows(blocks, base_tokens=10, bound=1_000)

        assert [len(w) for w in windows] == [1, 1]

    def test_windows_hold_at_most_the_option_cap(self) -> None:
        blocks = [block(i, "t") for i in range(MAX_CHOICE_OPTIONS + 1)]

        windows = build_windows(blocks, base_tokens=0, bound=1_000_000)

        assert [len(w) for w in windows] == [MAX_CHOICE_OPTIONS, 1]


class TestExcerptBlocks:
    WINDOW = (("b000", block(1)), ("b001", block(3)), ("b002", block(5)))

    def test_best_block_ignores_the_no_match_option(self) -> None:
        where = choice({NONE_KEY: 0.7, "b002": 0.2, "b000": 0.1})

        excerpt, supporting = excerpt_blocks(self.WINDOW, where)

        assert excerpt == block(5)
        assert supporting is None

    def test_second_block_needs_the_floor(self) -> None:
        above = choice({"b001": 0.5, "b000": SECOND_BLOCK_FLOOR})
        below = choice({"b001": 0.5, "b000": SECOND_BLOCK_FLOOR - 0.01})

        assert excerpt_blocks(self.WINDOW, above) == (block(3), block(1))
        assert excerpt_blocks(self.WINDOW, below) == (block(3), None)

    def test_without_probabilities_the_chosen_block_stands(self) -> None:
        where = ChoiceAnswer(
            choice="b001", probabilities=MappingProxyType({}), confidence=0.9
        )
        empty = ChoiceAnswer(
            choice=NONE_KEY, probabilities=MappingProxyType({}), confidence=0.9
        )

        assert excerpt_blocks(self.WINDOW, where) == (block(3), None)
        assert excerpt_blocks(self.WINDOW, empty) == (None, None)


def judgment(r: Record, answers: float, about: float = 0.5) -> Judgment:
    return Judgment(r, answers, about, 0.0, None, None)


class TestRank:
    def test_score_adds_the_weighted_kind_probability(self) -> None:
        adr = record("2026-01-02-x-adr")
        research = record("2026-01-02-x-research", DocType.RESEARCH)
        kind = {DocType.ADR: 0.1, DocType.RESEARCH: 0.8}

        ranked = rank(
            [judgment(adr, 0.9), judgment(research, 0.85)], kind=kind, wide={}
        )

        assert [j.record for j, _ in ranked] == [research, adr]
        assert ranked[0][1] == pytest.approx(0.85 + KIND_WEIGHT * 0.8)
        assert ranked[1][1] == pytest.approx(0.9 + KIND_WEIGHT * 0.1)

    def test_ties_break_on_about_then_recall_then_path(self) -> None:
        a, b, c, d = (record(f"2026-01-02-{n}-adr") for n in "abcd")
        judged = [
            judgment(d, 0.5, 0.2),
            judgment(c, 0.5, 0.2),
            judgment(b, 0.5, 0.2),
            judgment(a, 0.5, 0.9),
        ]

        ranked = rank(judged, kind={}, wide={b.rel_path: 0.3})

        assert [j.record for j, _ in ranked] == [a, b, c, d]


class TestMeter:
    def test_refusal_is_cleared_by_a_later_read(self) -> None:
        meter = Meter()
        first, second = record("2026-01-02-a-adr"), record("2026-01-02-b-adr")

        meter.refused([first, second])
        meter.read(first)

        assert meter.usage().unscored == 1

    def test_usage_sums_answered_requests(self) -> None:
        meter = Meter()
        answered = Evaluation(
            answers=MappingProxyType({}),
            model="jev-reported",
            input_tokens=40,
            output_tokens=1,
            elapsed_ms=1.0,
        )

        meter.sent()
        meter.sent()
        meter.answered(answered)
        meter.answered(answered)
        usage = meter.usage()

        assert (usage.model, usage.requests, usage.input_tokens) == (
            "jev-reported",
            2,
            80,
        )
        assert usage.elapsed_ms >= 0

    def test_model_defaults_to_the_pinned_version(self) -> None:
        assert Meter().usage().model == MODEL
