---
tags:
  - '#plan'
  - '#cli-reference-automation'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-10-firmware-wording-review-audit]]'
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `cli-reference-automation` plan

Track the remaining firmware-wording-review follow-ups: harden the renamed-template transitional fallback and reference accuracy now, then decide whether to build a Typer-surface CLI-reference auto-generator.

## Description

This plan tracks the two follow-ups the firmware-wording-review campaign deferred rather than closed. The campaign's decision record deferred automated regeneration of the bundled CLI reference (decision D6) as a logged follow-up, and its code review left a small band of LOW notes against the transitional template-rename fallback and one residual reference-accuracy gap (the `REVIEW-005` fallback and the `P03` doc gap).

Phase `P01` is the ready-to-execute hardening pass. The firmware campaign renamed the `ref-audit.md` template to `reference.md` and added a legacy-filename fallback in `get_template_path` so a not-yet-upgraded workspace still resolves the `REFERENCE` doc type; `P01` adds a removal-milestone marker scheduling that grace path for removal one release after the rename, lifts the in-function current-name template `mapping` to module scope beside `_LEGACY_TEMPLATE_NAMES` for symmetry, and corrects the `vault add --feature` required-marker annotation in the bundled `cli.md` that no longer matches live `--help`. All `P01` work lands in `src/vaultspec_core/vaultcore/hydration.py` and `src/vaultspec_core/builtins/reference/cli.md` and must keep the existing five fallback hydration tests green.

Phase `P02` is design-gated. The bundled `cli.md` is hand-authored and guarded by an enforced drift test (`test_cli_reference_drift.py`) that walks the live Typer tree and asserts every command and non-global option appears in the reference, so silent drift is already prevented today. `P02` therefore opens with a decision ADR weighing a Typer-surface auto-generator against the existing hand-authored-plus-drift-guard approach; only if that ADR concludes build do the generator implementation and the CLI-rule documentation steps execute.

## Steps

### Phase `P01` - transitional-fallback and reference accuracy hardening

Harden the ref-audit.md legacy fallback and correct residual reference-accuracy gaps the firmware-wording-review code review left as LOW notes.

- [x] `P01.S01` - Add a removal-milestone marker to the legacy template-name fallback so the ref-audit.md grace path is scheduled for removal one release after the rename, keeping the existing five fallback tests green (REVIEW-005 fallback); `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `P01.S02` - Relocate the in-function current-name template mapping to module scope beside \_LEGACY_TEMPLATE_NAMES for symmetry, keeping tests green (REVIEW-005 fallback); `src/vaultspec_core/vaultcore/hydration.py`.
- [ ] `P01.S03` - Correct the vault add --feature required-marker annotation to match live --help and grep the reference for any other stale required-markers (P03 doc gap); `src/vaultspec_core/builtins/reference/cli.md`.

### Phase `P02` - cli reference generator decision and rollout

Decide whether to build a Typer-surface auto-generator for the bundled reference and roll it out only if the decision concludes build, since the enforced drift guard already prevents silent drift today.

- [x] `P02.S04` - Produce a decision ADR weighing a Typer-surface auto-generator for the bundled reference against the existing hand-authored-plus-drift-guard approach, deciding whether to build it (D6 deferral); `.vault/adr`.
- [ ] `P02.S05` - GATED on the ADR deciding build, implement the generator and wire it into the pre-commit and CI surface beside the drift guard, regenerating the bundled reference from the live Typer tree with covering tests (D6 deferral); `src/vaultspec_core`.
- [ ] `P02.S06` - GATED on the ADR deciding build, document the generator as the canonical reference-update path in the CLI rule (D6 deferral); `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.

## Parallelization

Phase `P01` is ready and independent of `P02`. Its three Steps share two files: `P01.S01` and `P01.S02` both edit `src/vaultspec_core/vaultcore/hydration.py` and so carry a soft ordering (sequence them to avoid a merge conflict), while `P01.S03` edits the bundled `cli.md` and may run in parallel with either.

Phase `P02` is design-gated and does not block `P01`. Its first Step (`P02.S04`, the decision ADR) must land before either downstream Step. `P02.S05` and `P02.S06` execute only if the decision ADR concludes "build"; if the ADR concludes "do not build", both close as decided-not-to-build with the ADR as their evidence rather than producing code or rule changes. Because `P02` is an enhancement decision and not a gap closure, the plan can ship with `P01` complete and `P02` resolved either way.

## Verification

Phase `P01` is verified by green hydration tests plus a drift-guard run and a reference-accuracy grep. After `P01.S01` and `P01.S02` the targeted hydration suite in `src/vaultspec_core/vaultcore/tests/test_hydration.py` must stay green, with the existing five fallback tests (current-name preference, legacy fallback with warning, both-missing `None`, end-to-end legacy scaffolding, actionable error) unchanged. After `P01.S03` the `cli.md` drift guard `test_cli_reference_drift.py` must still pass, and a grep of `src/vaultspec_core/builtins/reference/cli.md` for stale required-markers in the option-default columns must return only the markers that match live `--help`.

Phase `P02` is verified by the persisted decision ADR and, if the ADR concludes build, a generator that reproduces the current bundled reference plus a passing drift guard. `P02.S04` is complete when the decision ADR exists under `.vault/adr/` with an explicit build-or-not verdict. If build, `P02.S05` is complete when the generator regenerates `cli.md` byte-identically to the hand-authored reference at its current surface, is wired into the pre-commit and CI surface beside the drift guard, and ships covering tests that pass; `P02.S06` is complete when the CLI rule names the generator as the canonical reference-update path. If not build, `P02.S05` and `P02.S06` are complete when both are closed as decided-not-to-build citing `P02.S04`.

Note explicitly that the enforced drift guard already prevents silent drift between the live CLI surface and the bundled reference today, so `P02` is an enhancement decision (auto-fix versus the renderer's maintenance burden), not a gap closure. The plan is complete when every Step is closed (`- [x]`); `vault plan check` exits 0; and `vault check all` is green on the documents this plan introduces.
