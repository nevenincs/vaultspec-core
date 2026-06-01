"""Acceptance gates for stable insertion (#109) and duplicate repair (#108).

The alpha-suffix insertion model and the display-path duplicate-repair path are
both implemented in the plan command layer; these tests lock the exact
behaviours the two issues call for so they cannot silently regress:

- #109: inserting between existing Waves / Phases allocates a lowercase alpha
  suffix instead of renumbering; appending another insert at the same anchor
  advances the suffix; suffixed ids survive a round-trip and are removable;
  alpha suffixes are rejected for Steps.
- #108: a plan carrying duplicate Step ids parses without bailing; a bare leaf
  id raises an actionable ambiguity error; the full display path repairs the
  intended row; the retired id is recorded only when no live row keeps it.

The tests drive the real parser, command layer, and serialiser - no mocks.
"""

from __future__ import annotations

import pytest

from vaultspec_core.plan.commands.phase_ops import insert_phase
from vaultspec_core.plan.commands.step_ops import (
    AmbiguousStepError,
    add_step,
    find_step,
    remove_step,
)
from vaultspec_core.plan.commands.wave_ops import insert_wave, remove_wave
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan

pytestmark = [pytest.mark.unit]


_L3_TWO_WAVES = """---
tags:
  - '#plan'
  - '#stable-insert'
date: '2026-06-01'
tier: L3
related: []
---

# `demo` plan

## Wave `W01` - one

Wave one intent.

### Phase `W01.P01` - first

Phase intent.

- [ ] `W01.P01.S01` - a; `src/a.py`.

## Wave `W02` - two

Wave two intent.

### Phase `W02.P01` - second

Phase intent.

- [ ] `W02.P01.S01` - b; `src/b.py`.
"""

_L2_TWO_PHASES = """---
tags:
  - '#plan'
  - '#stable-insert'
date: '2026-06-01'
tier: L2
related: []
---

# `demo` plan

### Phase `P01` - first

Phase one intent.

- [ ] `P01.S01` - a; `src/a.py`.

### Phase `P02` - second

Phase two intent.

- [ ] `P02.S01` - b; `src/b.py`.
"""


# ---------------------------------------------------------------------------
# #109 - stable alpha-suffix insertion for Waves and Phases
# ---------------------------------------------------------------------------
class TestStableSuffixInsertion:
    def test_insert_between_waves_allocates_suffix_not_renumber(self) -> None:
        plan = parse_plan(_L3_TWO_WAVES)
        new_wave = insert_wave(plan, title="inserted", intent="i", before="W02")
        assert new_wave.canonical_id == "W01a"
        # Existing ids are never renumbered by a stable insertion.
        assert [w.canonical_id for w in plan.waves] == ["W01", "W01a", "W02"]

    def test_repeated_insert_at_same_anchor_advances_suffix(self) -> None:
        plan = parse_plan(_L3_TWO_WAVES)
        insert_wave(plan, title="first", intent="i", before="W02")
        second = insert_wave(plan, title="second", intent="i", before="W02")
        assert second.canonical_id == "W01b"
        assert [w.canonical_id for w in plan.waves] == ["W01", "W01a", "W01b", "W02"]

    def test_insert_between_phases_allocates_suffix(self) -> None:
        plan = parse_plan(_L2_TWO_PHASES)
        new_phase = insert_phase(plan, title="inserted", intent="i", before="P02")
        assert new_phase.canonical_id == "P01a"
        assert [p.canonical_id for p in plan.phases] == ["P01", "P01a", "P02"]

    def test_suffixed_ids_round_trip_byte_stable(self) -> None:
        plan = parse_plan(_L3_TWO_WAVES)
        insert_wave(plan, title="inserted", intent="i", before="W02")
        text = serialise_plan(plan)
        assert "W01a" in text
        assert serialise_plan(parse_plan(text)) == text

    def test_suffixed_wave_is_removable_and_retires_its_id(self) -> None:
        plan = parse_plan(_L3_TWO_WAVES)
        insert_wave(plan, title="inserted", intent="i", before="W02")
        retired_id, _phases, _steps = remove_wave(plan, "W01a")
        assert retired_id == "W01a"
        assert [w.canonical_id for w in plan.waves] == ["W01", "W02"]
        assert "W01a" in plan.retired_wave_ids

    def test_steps_reject_alpha_suffix_addressing(self) -> None:
        plan = parse_plan(_L2_TWO_PHASES)
        with pytest.raises((AmbiguousStepError, KeyError, ValueError)):
            find_step(plan, "S01a")


# ---------------------------------------------------------------------------
# #108 - duplicate Step id parses and is repairable via display path
# ---------------------------------------------------------------------------
_DEGRADED_DUPLICATE = """---
tags:
  - '#plan'
  - '#dup-repair'
date: '2026-06-01'
tier: L2
related: []
---

# `demo` plan

### Phase `P334` - first

Intent one.

- [ ] `P334.S1951` - original; `src/a.py`.

### Phase `P335` - second

Intent two.

- [ ] `P335.S1951` - accidental duplicate; `src/b.py`.
"""


class TestDuplicateStepRepair:
    def test_duplicate_step_ids_parse_without_bailing(self) -> None:
        plan = parse_plan(_DEGRADED_DUPLICATE)
        assert [s.canonical_id for s in plan.steps] == ["S1951", "S1951"]
        assert [s.display_path for s in plan.steps] == [
            "P334.S1951",
            "P335.S1951",
        ]

    def test_bare_leaf_id_raises_actionable_ambiguity(self) -> None:
        plan = parse_plan(_DEGRADED_DUPLICATE)
        with pytest.raises(AmbiguousStepError) as exc:
            find_step(plan, "S1951")
        # The error lists the display paths the operator can disambiguate with.
        assert "P334.S1951" in str(exc.value)
        assert "P335.S1951" in str(exc.value)

    def test_display_path_repairs_the_intended_duplicate(self) -> None:
        plan = parse_plan(_DEGRADED_DUPLICATE)
        retired = remove_step(plan, "P335.S1951")
        assert retired == "S1951"
        # The other occurrence survives, so the id is still live and not retired.
        assert [s.display_path for s in plan.steps] == ["P334.S1951"]
        assert "S1951" not in plan.retired_step_ids

    def test_removing_final_occurrence_retires_the_id(self) -> None:
        plan = parse_plan(_DEGRADED_DUPLICATE)
        remove_step(plan, "P335.S1951")
        remove_step(plan, "P334.S1951")
        assert plan.steps == []
        assert "S1951" in plan.retired_step_ids

    def test_repaired_plan_then_allocates_past_retired_id(self) -> None:
        plan = parse_plan(_DEGRADED_DUPLICATE)
        remove_step(plan, "P335.S1951")
        # A fresh add must never reissue a live or retired id.
        new_step = add_step(plan, action="new work", scope="src/c.py", phase_id="P334")
        assert new_step.canonical_id == "S1952"
