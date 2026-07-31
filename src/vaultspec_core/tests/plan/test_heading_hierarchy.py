"""Heading-hierarchy invariants for the plan serialiser and its repair path.

A plan document's ``### Phase`` heading is an ``h3``. At ``L3``/``L4`` the
``## Wave`` heading supplies the intervening ``h2``, but ``L1``/``L2`` plans
have no Wave: without a serialiser-owned ``## Steps`` section heading the
``h1`` title is followed directly by an ``h3``, which markdownlint reports as
``MD001`` (heading-increment). The template carries ``## Steps``, but as
ordinary prose the serialiser did not own - so ``canonicalise=True`` stripped
it and no re-emission restored it.

These tests pin the heading contract structurally: the increment is legal at
every tier, the section heading survives canonicalisation, an authored copy is
never duplicated, and the repair is a fixed point so
``vaultspec-core vault plan check --fix`` stays idempotent. The final pair
covers the CLI repair path itself, including the byte-level line-ending
contract the project's ``mdformat`` gate (``end_of_line = "lf"``) enforces.

See :func:`vaultspec_core.plan.serialiser.serialise_plan` and
:mod:`vaultspec_core.plan.fixes` for the surfaces under test.
"""

from __future__ import annotations

import itertools
import random
import re
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_TIERS = ("L1", "L2", "L3", "L4")

_ATX_HEADING = re.compile(r"^(?P<hashes>#{1,6}) +\S")

_LEGACY_L2_PLAN = (
    "---\n"
    "tags:\n"
    "  - '#plan'\n"
    "  - '#legacy-heading'\n"
    "date: '2026-07-31'\n"
    "tier: L2\n"
    "related:\n"
    "  - '[[2026-07-31-legacy-heading-adr]]'\n"
    "---\n"
    "\n"
    "# `legacy-heading` plan\n"
    "\n"
    "### Phase `P01` - legacy phase\n"
    "\n"
    "Legacy phase intent.\n"
    "\n"
    "- [x] `P01.S01` - do the work; `src/module/parser.py`.\n"
)

_TEMPLATE_SHAPED_L2_PLAN = (
    "---\n"
    "tags:\n"
    "  - '#plan'\n"
    "  - '#steps-heading'\n"
    "date: '2026-07-31'\n"
    "tier: L2\n"
    "related:\n"
    "  - '[[2026-07-31-steps-heading-adr]]'\n"
    "---\n"
    "\n"
    "# `steps-heading` plan\n"
    "\n"
    "## Description\n"
    "\n"
    "Prose the serialiser does not own.\n"
    "\n"
    "## Steps\n"
    "\n"
    "### Phase `P01` - author the section\n"
    "\n"
    "Deliver the section heading.\n"
    "\n"
    "- [ ] `P01.S01` - emit the heading; `src/module/serialiser.py`.\n"
    "\n"
    "## Verification\n"
    "\n"
    "Closing prose the serialiser does not own.\n"
)


@pytest.fixture()
def runner() -> CliRunner:
    """Typer test runner with colour disabled."""
    return CliRunner(env={"NO_COLOR": "1"})


def _atx_heading_levels(text: str) -> list[int]:
    """Return the ATX heading levels of ``text`` in document order.

    Lines inside fenced code blocks are skipped so a fenced Markdown
    example never registers as a document heading.

    Args:
        text: Markdown document text.

    Returns:
        One integer per heading, in document order.
    """
    levels: list[int] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = _ATX_HEADING.match(line)
        if match is not None:
            levels.append(len(match.group("hashes")))
    return levels


def _assert_legal_increments(levels: list[int], context: str) -> None:
    """Assert no heading level in ``levels`` jumps by more than one."""
    assert levels, f"{context}: document emitted no headings"
    assert levels[0] == 1, f"{context}: first heading is h{levels[0]}, expected h1"
    for previous, current in itertools.pairwise(levels):
        assert current - previous <= 1, (
            f"{context}: heading level jumped h{previous} -> h{current} in {levels}"
        )


# ---- Serialiser output ------------------------------------------------------


@pytest.mark.parametrize("tier", _TIERS)
def test_serialised_heading_levels_increment_by_one(tier: str) -> None:
    """Serialised output never skips a heading level (markdownlint MD001)."""
    spec = make_clean_plan(tier, rng=random.Random(11), waves=2, phases=2, steps=2)

    rendered = serialise_plan(parse_plan(spec.render()))

    _assert_legal_increments(_atx_heading_levels(rendered), tier)


@pytest.mark.parametrize("tier", _TIERS)
def test_serialised_output_carries_exactly_one_steps_heading(tier: str) -> None:
    """The ``## Steps`` section heading is serialiser-owned at every tier."""
    spec = make_clean_plan(tier, rng=random.Random(12), waves=2, phases=2, steps=2)

    rendered = serialise_plan(parse_plan(spec.render()))

    assert rendered.count("\n## Steps\n") == 1


@pytest.mark.parametrize("tier", _TIERS)
def test_canonicalise_retains_the_steps_heading(tier: str) -> None:
    """``canonicalise=True`` drops authored prose but keeps ``## Steps``.

    Canonicalisation discards unknown blocks; while the heading was
    ordinary prose this silently stripped the ``h2`` that kept a
    following ``### Phase`` a legal increment.
    """
    spec = make_clean_plan(tier, rng=random.Random(13), waves=2, phases=2, steps=2)

    rendered = serialise_plan(parse_plan(spec.render()), canonicalise=True)

    assert rendered.count("\n## Steps\n") == 1
    _assert_legal_increments(_atx_heading_levels(rendered), tier)


@pytest.mark.parametrize("tier", _TIERS)
def test_steps_heading_precedes_every_phase_and_wave_heading(tier: str) -> None:
    """``## Steps`` opens the container section it names."""
    spec = make_clean_plan(tier, rng=random.Random(14), waves=2, phases=2, steps=2)

    rendered = serialise_plan(parse_plan(spec.render()))

    steps_index = rendered.index("\n## Steps\n")
    for heading in ("\n## Wave ", "\n### Phase "):
        if heading in rendered:
            assert steps_index < rendered.index(heading)


def test_authored_steps_heading_is_not_duplicated() -> None:
    """A document already carrying ``## Steps`` as prose keeps exactly one.

    The parser consumes the authored heading as a structural token, so
    the serialiser's own emission replaces it rather than stacking a
    second copy on every round-trip.
    """
    first = serialise_plan(parse_plan(_TEMPLATE_SHAPED_L2_PLAN))
    second = serialise_plan(parse_plan(first))

    assert first.count("\n## Steps\n") == 1
    assert second.count("\n## Steps\n") == 1
    assert first == second


def test_authored_prose_around_the_steps_heading_survives() -> None:
    """Consuming ``## Steps`` does not swallow the prose bracketing it."""
    rendered = serialise_plan(parse_plan(_TEMPLATE_SHAPED_L2_PLAN))

    assert "## Description" in rendered
    assert "Prose the serialiser does not own." in rendered
    assert "## Verification" in rendered
    assert "Closing prose the serialiser does not own." in rendered


def test_plan_without_steps_heading_gains_one_and_then_stabilises() -> None:
    """A legacy plan missing ``## Steps`` is repaired by one round-trip.

    The repair is a fixed point: a second round-trip changes nothing, so
    ``vaultspec-core vault plan check --fix`` stays idempotent.
    """
    assert "## Steps" not in _LEGACY_L2_PLAN

    repaired = serialise_plan(parse_plan(_LEGACY_L2_PLAN))
    stable = serialise_plan(parse_plan(repaired))

    assert repaired.count("\n## Steps\n") == 1
    assert repaired == stable
    assert _atx_heading_levels(repaired) == [1, 2, 3]


@pytest.mark.parametrize("seed", range(10))
def test_round_trip_stays_a_fixed_point_under_random_plans(seed: int) -> None:
    """Randomised plans: the second serialisation is byte-identical."""
    rng = random.Random(seed)
    tier = rng.choice(_TIERS)
    spec = make_clean_plan(
        tier,
        rng=rng,
        waves=rng.randint(1, 3),
        phases=rng.randint(1, 3),
        steps=rng.randint(1, 4),
    )

    once = serialise_plan(parse_plan(spec.render()))
    twice = serialise_plan(parse_plan(once))

    assert once == twice
    _assert_legal_increments(_atx_heading_levels(once), f"{tier}/seed{seed}")


def test_step_counts_survive_the_repair_round_trip() -> None:
    """Repairing the heading changes no Step, Phase, or Wave identity."""
    spec = make_clean_plan("L3", rng=random.Random(15), waves=2, phases=2, steps=3)

    before = parse_plan(spec.render())
    after = parse_plan(serialise_plan(before))

    assert [s.canonical_id for s in before.steps] == [
        s.canonical_id for s in after.steps
    ]
    assert [s.checked for s in before.steps] == [s.checked for s in after.steps]
    assert [p.canonical_id for p in before.phases] == [
        p.canonical_id for p in after.phases
    ]
    assert [w.canonical_id for w in before.waves] == [
        w.canonical_id for w in after.waves
    ]


def test_trailing_prose_is_separated_from_the_step_list() -> None:
    """Preserved tail prose never lands flush against the last Step row.

    A list immediately followed by a heading is MD032 plus MD022. The
    Phase and Wave blocks already terminate with a blank line; the
    ``L1`` row list must do the same, since it has no container block to
    close it.
    """
    source = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#tail-prose'\n"
        "date: '2026-07-31'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-07-31-tail-prose-adr]]'\n"
        "---\n"
        "\n"
        "# `tail-prose` plan\n"
        "\n"
        "## Steps\n"
        "\n"
        "- [x] `S01` - do the work; `src/module/parser.py`.\n"
        "\n"
        "## Description\n"
        "\n"
        "Tail prose the serialiser preserves but does not own.\n"
    )

    rendered = serialise_plan(parse_plan(source))
    lines = rendered.splitlines()
    heading_index = lines.index("## Description")

    assert lines[heading_index - 1] == "", rendered
    assert "## Description" in rendered
    assert rendered == serialise_plan(parse_plan(rendered))


# ---- CLI repair path --------------------------------------------------------


def test_check_fix_repairs_a_missing_steps_heading(
    tmp_path: Path, runner: CliRunner
) -> None:
    """``vault plan check --fix`` restores the ``## Steps`` section heading."""
    plan_path = tmp_path / "legacy-plan.md"
    plan_path.write_text(_LEGACY_L2_PLAN, encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "check", str(plan_path), "--fix"])

    assert result.exit_code in {0, 1}, result.stdout
    repaired = plan_path.read_text(encoding="utf-8")
    assert "\n## Steps\n" in repaired
    assert repaired.index("\n## Steps\n") < repaired.index("\n### Phase ")


def test_check_fix_reattests_the_body_hash_it_rewrites(
    tmp_path: Path, runner: CliRunner
) -> None:
    """``vault plan check --fix`` re-stamps the document it repairs.

    The serialiser rebuilds frontmatter from the fields it owns, so a
    repair that did not re-stamp would land a body the stored
    ``body_hash:`` no longer describes - leaving every repaired document
    reading as hand-edited to the reconciliation check.
    """
    from vaultspec_core.vaultcore.body_hash import document_body_digest
    from vaultspec_core.vaultcore.parser import parse_frontmatter

    stamped = _LEGACY_L2_PLAN.replace(
        "date: '2026-07-31'\n",
        "date: '2026-07-31'\nmodified: '2026-01-01'\nbody_hash: 'sha256:stale'\n",
    )
    plan_path = tmp_path / "legacy-plan.md"
    plan_path.write_text(stamped, encoding="utf-8", newline="")

    result = runner.invoke(app, ["vault", "plan", "check", str(plan_path), "--fix"])

    assert result.exit_code in {0, 1}, result.stdout
    repaired = plan_path.read_text(encoding="utf-8")
    metadata, _body = parse_frontmatter(repaired)
    assert metadata["body_hash"] != "sha256:stale"
    assert metadata["body_hash"] == document_body_digest(repaired)
    assert metadata["modified"] != "2026-01-01"


def test_check_fix_writes_lf_line_endings(tmp_path: Path, runner: CliRunner) -> None:
    """``vault plan check --fix`` persists LF-only bytes on every platform.

    The repaired document is read back as raw bytes on purpose: a
    platform-translated text write emits ``\\r\\n`` on Windows, which the
    project's ``mdformat`` gate (``end_of_line = "lf"``) rejects. Reading
    the file as text would hide the defect, because universal newlines
    normalise the carriage returns away before the assertion sees them.
    """
    plan_path = tmp_path / "legacy-plan.md"
    plan_path.write_text(_LEGACY_L2_PLAN, encoding="utf-8", newline="")

    result = runner.invoke(app, ["vault", "plan", "check", str(plan_path), "--fix"])

    assert result.exit_code in {0, 1}, result.stdout
    raw = plan_path.read_bytes()
    assert raw != _LEGACY_L2_PLAN.encode("utf-8"), "the --fix branch wrote nothing"
    assert b"\r" not in raw
