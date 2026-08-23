"""Regression coverage for the plan serialiser faults reported in issue #313.

Three defects, one document each time:

1. **Commented template examples became live rows.** The shipped plan scaffold
   documents its own grammar inside HTML comments - a ``### Phase`` heading,
   two Step rows, a ``## Wave`` heading. The parser read those examples as
   structure, so a freshly scaffolded L3 plan already "contained" a Phase
   ``P02`` nobody wrote, and the next mutation serialised a real Wave *inside*
   the comment.
2. **A semicolon in an action was read as the action / scope delimiter.** The
   row was accepted and written, then failed its own post-write verification
   because it read back truncated with the remainder folded into the scope.
3. **A failed verification left the mutation persisted.** Because the only
   round-trip check ran after ``atomic_write``, both faults above exited
   non-zero over a document they had already modified.

The tests below pin the contract those defects violated: comments are
commentary at every structural surface, an action may carry a semicolon, and
**a plan mutation that exits non-zero leaves the document byte-identical**.

Section 4 covers the boundary of the scaffold exemption that fix #1 required
(issue #317). Once commented examples stopped being parsed, a fresh scaffold
correctly held nothing - and the source-structure guard then refused the very
mutation that would populate it. The exemption added for that has to admit a
genuinely empty document without admitting one that merely *parses* as empty
because every row in it is malformed.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.plan.parser import mask_html_comments_text, parse_plan
from vaultspec_core.plan.row_contract import (
    RowContentError,
    validate_action,
    validate_intent,
    validate_scope,
    validate_title,
)
from vaultspec_core.plan.serialiser import serialise_plan
from vaultspec_core.plan.write_guard import (
    PlanWriteGuardError,
    PlanWriteVerificationError,
    guard_plan_write,
    write_plan_verified,
)
from vaultspec_core.tests.plan._factories import make_clean_plan

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def runner() -> CliRunner:
    """Typer test runner with colour disabled."""
    return CliRunner(env={"NO_COLOR": "1"})


def _write_plan(
    tmp_path: Path,
    tier: str,
    *,
    seed: int,
    waves: int = 0,
    phases: int = 0,
    steps: int = 0,
) -> Path:
    """Render a clean plan at *tier* onto disk and return its path."""
    spec = make_clean_plan(
        tier,
        rng=random.Random(seed),
        waves=waves,
        phases=phases,
        steps=steps,
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / f"2026-08-22-regression-{tier.lower()}-plan.md"
    path.write_text(spec.render(), encoding="utf-8")
    return path


def _scaffolded_l3_plan(tmp_path: Path) -> Path:
    """Render the *shipped* plan template at L3, annotations intact.

    Deliberately not a factory plan: the whole point of the first defect is
    that the scaffold's own commented grammar examples were parsed, so the
    regression has to run against the real template bytes rather than a
    synthesised document that never carried them.
    """
    from importlib.resources import files

    template = (
        files("vaultspec_core.builtins")
        .joinpath("templates/plan.md")
        .read_text(encoding="utf-8")
    )
    text = (
        template.replace("{feature}", "serializer-repro")
        .replace("{yyyy-mm-dd-*}", "2026-08-22-example-adr")
        .replace("{yyyy-mm-dd}", "2026-08-22")
        .replace("'{tier}'", "L3")
    )
    path = tmp_path / "2026-08-22-serializer-repro-plan.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---- 1. HTML comments are commentary, not structure -------------------------


def test_the_shipped_scaffold_parses_as_an_empty_plan(tmp_path: Path) -> None:
    """A fresh L3 scaffold holds no Waves, Phases, or Steps.

    Every container the template mentions lives inside an HTML comment as a
    format example. Before the fix the scaffold parsed as a plan already
    holding ``P02``, ``W01``, and two Steps.
    """
    plan = parse_plan(_scaffolded_l3_plan(tmp_path).read_text(encoding="utf-8"))

    assert plan.waves == []
    assert plan.phases == []
    assert plan.steps == []


def test_grammar_inside_arbitrary_comments_is_ignored(tmp_path: Path) -> None:
    """Valid-looking Wave, Phase, and Step rows in a comment are not parsed."""
    path = _write_plan(tmp_path, "L3", seed=101, waves=1, phases=1, steps=1)
    original = parse_plan(path.read_text(encoding="utf-8"))

    injected = path.read_text(encoding="utf-8") + (
        "\n<!-- an arbitrary note:\n"
        "     ## Wave `W09` - a wave that is only an example\n"
        "     ### Phase `W09.P09` - a phase that is only an example\n"
        "     - [x] `W09.P09.S09` - do nothing; `nowhere.py`.\n"
        "-->\n"
    )
    path.write_text(injected, encoding="utf-8")
    reparsed = parse_plan(injected)

    assert [w.canonical_id for w in reparsed.waves] == [
        w.canonical_id for w in original.waves
    ]
    assert [p.canonical_id for p in reparsed.phases] == [
        p.canonical_id for p in original.phases
    ]
    assert [s.canonical_id for s in reparsed.steps] == [
        s.canonical_id for s in original.steps
    ]


def test_a_single_line_comment_masks_only_its_own_span() -> None:
    """Masking is span-accurate: text outside a comment on the same line stays."""
    masked = mask_html_comments_text("live <!-- hidden --> live again\nplain")

    assert masked == "live                 live again\nplain"
    assert len(masked.splitlines()[0]) == len("live <!-- hidden --> live again")


def test_an_unterminated_comment_masks_to_the_end_of_the_document() -> None:
    """An opener with no closer hides everything below it, as a renderer does."""
    masked = mask_html_comments_text("keep\n<!-- open\nhidden\nalso hidden")

    assert [line.strip() for line in masked.splitlines()] == ["keep", "", "", ""]


def test_sequential_wave_and_phase_adds_on_a_fresh_scaffold(
    tmp_path: Path, runner: CliRunner
) -> None:
    """The issue's reproduction: two ``wave add`` calls then a ``phase add``.

    No annotations cleanup first, no ``--canonicalise``. Every call must
    succeed, and the document must end up holding exactly the three containers
    that were requested - no ``P02`` from the template's Phase example.
    """
    path = _scaffolded_l3_plan(tmp_path)

    for title, intent in (
        ("first wave", "First wave intent."),
        ("second wave", "Second wave intent."),
    ):
        result = runner.invoke(
            app,
            [
                "vault",
                "plan",
                "wave",
                "add",
                str(path),
                "--title",
                title,
                "--intent",
                intent,
            ],
        )
        assert result.exit_code == 0, result.stdout + (result.stderr or "")

    plan = parse_plan(path.read_text(encoding="utf-8"))
    assert [wave.canonical_id for wave in plan.waves] == ["W01", "W02"]

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "phase",
            "add",
            str(path),
            "--wave",
            "W01",
            "--title",
            "first phase",
            "--intent",
            "First phase intent.",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    plan = parse_plan(path.read_text(encoding="utf-8"))
    assert [wave.canonical_id for wave in plan.waves] == ["W01", "W02"]
    assert [phase.canonical_id for phase in plan.phases] == ["P01"]
    assert plan.steps == []
    assert [phase.canonical_id for phase in plan.waves[0].phases] == ["P01"]


def test_a_scaffold_mutation_never_writes_inside_a_comment(
    tmp_path: Path, runner: CliRunner
) -> None:
    """The added Wave heading must be live document text, not commented out."""
    path = _scaffolded_l3_plan(tmp_path)

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "wave",
            "add",
            str(path),
            "--title",
            "first wave",
            "--intent",
            "First wave intent.",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    text = path.read_text(encoding="utf-8")
    heading = "## Wave `W01` - first wave"
    assert heading in text
    # The masked document still carries the heading, which is only true when
    # the heading sits outside every comment span.
    assert heading in mask_html_comments_text(text)


# ---- 2. The action / scope delimiter ----------------------------------------


def test_an_action_may_contain_semicolons_at_every_tier(tmp_path: Path) -> None:
    """A semicolon-bearing action round-trips with its scope intact."""
    action = "Ground the credentials contract; implement the reader; verify it"
    scope = "src/cadrumo/core/_credentials.py"

    for tier, counts in (
        ("L1", {"steps": 2}),
        ("L2", {"phases": 1, "steps": 2}),
        ("L3", {"waves": 1, "phases": 1, "steps": 2}),
    ):
        path = _write_plan(tmp_path / tier, tier, seed=202, **counts)
        plan = parse_plan(path.read_text(encoding="utf-8"))
        plan.steps[0].action = action
        plan.steps[0].scope = scope

        reparsed = parse_plan(serialise_plan(plan))

        assert reparsed.steps[0].action == action, tier
        assert reparsed.steps[0].scope == scope, tier


@pytest.mark.parametrize(
    "action",
    [
        "a; b",
        "a; b; c",
        "a; `quoted`; b",
        "wrap `src/x.py`; then `src/y.py` too",
        "trailing semicolon inside; ",
        "; leading separator",
    ],
)
def test_action_delimiter_fuzzing_round_trips(tmp_path: Path, action: str) -> None:
    """Every accepted action shape reads back exactly as written."""
    path = _write_plan(tmp_path, "L1", seed=203, steps=1)
    plan = parse_plan(path.read_text(encoding="utf-8"))
    plan.steps[0].action = validate_action(action)
    plan.steps[0].scope = "src/module/parser.py"

    reparsed = parse_plan(serialise_plan(plan))

    assert reparsed.steps[0].action == action.strip()
    assert reparsed.steps[0].scope == "src/module/parser.py"


@pytest.mark.parametrize(
    "scope",
    ["src/a.py; src/b.py", "src/`a`.py", "src/a.py <!-- x", "src/a.py -->", "", "   "],
)
def test_a_scope_that_cannot_round_trip_is_refused(scope: str) -> None:
    """Characters the scope span cannot carry are rejected, not written."""
    with pytest.raises(RowContentError):
        validate_scope(scope)


@pytest.mark.parametrize("action", ["multi\nline", "with <!-- opener", "", "   "])
def test_an_action_that_cannot_round_trip_is_refused(action: str) -> None:
    """A line break or comment delimiter in an action is refused up front."""
    with pytest.raises(RowContentError):
        validate_action(action)


def test_a_container_title_may_not_carry_a_comment_delimiter() -> None:
    """A Wave or Phase title that would open a comment is refused."""
    with pytest.raises(RowContentError):
        validate_title("a title <!-- with an opener", container="Wave")


def test_step_add_rejects_a_delimiter_bearing_scope_without_writing(
    tmp_path: Path, runner: CliRunner
) -> None:
    """The CLI refuses the scope before serialising, leaving the plan intact."""
    path = _write_plan(tmp_path, "L2", seed=204, phases=1, steps=1)
    before = path.read_bytes()

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(path),
            "--phase",
            "P01",
            "--action",
            "reconcile the ledger",
            "--scope",
            "src/a.py; src/b.py",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert path.read_bytes() == before


# ---- 3. A non-zero exit leaves the document byte-identical -------------------


def test_a_round_trip_failure_never_touches_the_file(tmp_path: Path) -> None:
    """The in-memory round-trip guard refuses before ``atomic_write`` runs."""
    path = _write_plan(tmp_path, "L1", seed=301, steps=2)
    original = path.read_text(encoding="utf-8")
    plan = parse_plan(original)
    # Bypass the command-boundary validators to reach the guard directly.
    plan.steps[0].scope = "src/module/parser.py <!-- and more"
    doomed = serialise_plan(plan)

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        write_plan_verified(path, doomed, plan, original_text=original)

    assert "mutation aborted" in str(excinfo.value)
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("one\r\ntwo", "one\ntwo"),
        ("one\rtwo", "one\ntwo"),
        ("one\ntwo", "one\ntwo"),
        ("one\r\ntwo\rthree", "one\ntwo\nthree"),
    ],
)
def test_intent_line_endings_are_normalised_at_the_boundary(
    supplied: str, expected: str
) -> None:
    """A caller's carriage returns collapse to ``\\n`` before anything is written.

    A ``\\r`` that reaches the document is written verbatim but reads back as
    ``\\n``, so the mutation would land, fail its own verification, and roll
    back over a difference the caller could not act on. Normalising here makes
    that a no-op instead (issue #316).
    """
    assert validate_intent(supplied, container="Phase") == expected


def test_a_post_write_verification_failure_restores_the_original(
    tmp_path: Path,
) -> None:
    """When the persisted bytes diverge, the pre-mutation document comes back.

    Reaching this branch needs a divergence the *pre*-write round-trip guard
    cannot foresee, since anything it can see never reaches the file. A lone
    carriage return is exactly that:
    :func:`~vaultspec_core.core.helpers.atomic_write` encodes to UTF-8 and
    writes the bytes verbatim, while the verifier's
    :meth:`~pathlib.Path.read_text` applies universal newlines - so the ``\r``
    is persisted faithfully and reads back as ``\n``. Nothing is patched and
    no seam is opened for the test: the divergence is a genuine property of
    the two real calls (issue #316).

    The guard must both fail the write and put the original bytes back.
    """
    path = _write_plan(tmp_path, "L2", seed=304, phases=1, steps=2)
    original = path.read_text(encoding="utf-8")
    plan = parse_plan(original)
    # The CR goes in a Phase intent, which is prose: `_document_rows` excludes
    # intent paragraphs, so the pre-write round-trip guard cannot see this and
    # the write genuinely happens. A CR in an action would be caught before the
    # file is touched - which is that guard working, not this branch.
    plan.phases[0].intent = "Deliver the reconciliation.\rIn two sittings."
    doomed = serialise_plan(plan)

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        write_plan_verified(path, doomed, plan, original_text=original)

    message = str(excinfo.value)
    assert "does not match the text this mutation wrote" in message
    assert "restored to its pre-mutation bytes" in message
    assert path.read_text(encoding="utf-8") == original


def test_the_restored_document_is_still_a_usable_plan(tmp_path: Path) -> None:
    """Restoration returns a parseable plan, not merely equal bytes.

    Byte equality is the assertion that matters, but a restore that produced
    a document the parser could no longer read would satisfy it only because
    the original was captured before the write. Parsing the restored file
    proves the plan survived the failed mutation intact.
    """
    path = _write_plan(tmp_path, "L2", seed=305, phases=1, steps=2)
    original = path.read_text(encoding="utf-8")
    before = parse_plan(original)

    plan = parse_plan(original)
    plan.phases[0].intent = "Deliver the reconciliation.\rIn two sittings."

    with pytest.raises(PlanWriteVerificationError):
        write_plan_verified(path, serialise_plan(plan), plan, original_text=original)

    after = parse_plan(path.read_text(encoding="utf-8"))
    assert [step.canonical_id for step in after.steps] == [
        step.canonical_id for step in before.steps
    ]
    assert [step.action for step in after.steps] == [
        step.action for step in before.steps
    ]


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (
            [
                "step",
                "add",
                "--phase",
                "P01",
                "--action",
                "act",
                "--scope",
                "src/a.py; b.py",
            ],
            "delimiter in scope",
        ),
        (
            [
                "step",
                "add",
                "--phase",
                "P01",
                "--action",
                "line\nbreak",
                "--scope",
                "src/a.py",
            ],
            "line break in action",
        ),
        (
            [
                "step",
                "add",
                "--phase",
                "P01",
                "--action",
                "opens <!-- comment",
                "--scope",
                "src/a.py",
            ],
            "comment opener in action",
        ),
        (["step", "edit", "S01", "--scope", "src/a.py; b.py"], "edit with bad scope"),
        (["step", "check", "S99"], "unknown Step"),
        (["phase", "add", "--title", "t <!-- x", "--intent", "i"], "bad Phase title"),
        (["phase", "remove", "P99"], "unknown Phase"),
        (["wave", "add", "--title", "t", "--intent", "i"], "Waves illegal at L2"),
    ],
)
def test_every_failing_mutator_leaves_the_plan_byte_identical(
    tmp_path: Path, runner: CliRunner, argv: list[str], reason: str
) -> None:
    """No non-zero plan mutation may change a single byte of the document."""
    path = _write_plan(
        tmp_path / reason.replace(" ", "-"), "L2", seed=303, phases=1, steps=2
    )
    before = path.read_bytes()

    result = runner.invoke(app, ["vault", "plan", *argv[:2], str(path), *argv[2:]])

    assert result.exit_code != 0, f"{reason}: expected a refusal, got {result.stdout}"
    assert path.read_bytes() == before, f"{reason}: the document was modified"


# ---- 4. The scaffold exemption admits absence, never lost structure ----------


def _l2_plan(body: str) -> str:
    """Return an L2 plan document whose Steps section holds *body*."""
    return (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#exemption'\n"
        "date: '2026-08-23'\n"
        "modified: '2026-08-23'\n"
        "tier: L2\n"
        "---\n"
        "\n"
        "# `exemption` plan\n"
        "\n"
        "## Steps\n"
        "\n"
    ) + body


def _guard_verdict(source: str) -> str:
    """Return ``"refused"`` or ``"allowed"`` for a rewrite of *source*.

    Drives the real guard through :func:`guard_plan_write`, the entry point
    every write path uses, rather than reaching for the private helper.
    """
    plan = parse_plan(source)
    try:
        guard_plan_write(source, serialise_plan(plan), None, path_name="p.md")
    except PlanWriteGuardError:
        return "refused"
    return "allowed"


@pytest.mark.parametrize(
    ("body", "description"),
    [
        ("", "nothing at all"),
        ("Notes about what this plan will eventually do.\n", "prose but no rows"),
        ("<!-- ### Phase `P01` - only an example -->\n", "structure only in a comment"),
    ],
)
def test_a_genuinely_empty_plan_stays_mutable(body: str, description: str) -> None:
    """A plan that never held structure is rewritable, so it can be populated."""
    assert _guard_verdict(_l2_plan(body)) == "allowed", description


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            "### phase `p01` - a phase\n\n- [ ] `p01.s01` - do it; `src/a.py`.\n",
            "PLAN050 lowercase structural noun",
        ),
        (
            "### Phase `P1` - a phase\n\n- [ ] `P1.S1` - do it; `src/a.py`.\n",
            "PLAN020 under-padded identifiers",
        ),
        (
            "### Phase `P01` \u2014 a phase\n\n"
            "- [ ] `P01.S01` \u2014 do it; `src/a.py`.\n",
            "PLAN060 em-dash separator",
        ),
    ],
)
def test_a_plan_whose_rows_are_all_malformed_is_refused(body: str, code: str) -> None:
    """Parsing to nothing is not the same as holding nothing (issue #317).

    Each document below carries a Phase heading and a Step row a reader would
    call structure, but each is malformed in a way the parser skips - so the
    model comes back empty and looks exactly like a fresh scaffold. The
    exemption must not fire: the author is told to repair the rows instead of
    having them quietly demoted to prose by a rewrite.
    """
    assert _guard_verdict(_l2_plan(body)) == "refused", code


def test_the_exemption_defers_to_the_checkers_rather_than_its_own_matcher() -> None:
    """A malformed row is caught because a rule reports it, not by a regex here.

    The predicate this replaced matched the parser's own strict patterns, which
    cannot work: anything the parser drops is by construction not matched by
    the patterns the parser matches with. Deferring to the detection rules is
    what makes the guard see rows the parser cannot, and it keeps one home for
    "what does a broken plan look like" (issue #317).
    """
    from vaultspec_core.plan.checks import Severity, collect_all

    source = _l2_plan("### Phase `P1` - a phase\n\n- [ ] `P1.S1` - go; `a.py`.\n")
    plan = parse_plan(source)
    errors = [f for f in collect_all(plan, source) if f.severity is Severity.ERROR]

    # The model is empty, exactly as for a fresh scaffold ...
    assert not plan.phases
    assert not plan.steps
    # ... and the only thing separating the two is what the rules reported.
    assert {f.code for f in errors} > {"PLAN010"}
