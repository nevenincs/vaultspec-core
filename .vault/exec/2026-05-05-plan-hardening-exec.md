---
tags:
  - '#exec'
  - '#plan-hardening'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-05-plan-hardening-plan]]'
  - '[[2026-05-05-plan-hardening-adr]]'
  - '[[2026-05-06-plan-hardening-adr]]'
---

# `plan-hardening` exec summary

Aggregated summary of the `#plan-hardening` feature work spanning Wave 1 (firmware: rule extension prose) and Wave 2 (Python implementation: the `vault plan` CLI). Both Waves landed; the originating plan is at 99 / 99 closed Steps.

## Pipeline phases executed

- Research note in `.vault/research/2026-05-05-plan-hardening-research.md` framing the convention question (row-per-Step plan documents, mechanical tracking, four complexity tiers).
- Convention ADR in `.vault/adr/2026-05-05-plan-hardening-adr.md` codifying the `Epic > Wave > Phase > Step` hierarchy, tier model (`L1`-`L4`), flat append-only canonical identifiers (`S##` / `P##` / `W##`), and the row contract (one prompt-run + one commit per row).
- CLI ADR in `.vault/adr/2026-05-06-plan-hardening-adr.md` codifying the `vault plan` subcommand surface, identifier-retirement contract, autofix idempotency rule, and the seven detection codes (`PLAN001` to `PLAN060`).
- Plan in `.vault/plan/2026-05-05-plan-hardening-plan.md` (L3) wrapping 99 Steps across 17 Phases and 2 Waves.

## What shipped in Wave 1 (firmware)

Rule extension prose mandating the convention across nine `.vaultspec/` surfaces: the plan template, write skill, execute skill, exec-step template, exec-summary template, the system rule under `rules/system/03-vaultspec.md`, the public rule under `rules/rules/vaultspec.builtin.md`, the writer agent persona, and the three executor agent personas (low / standard / high).

Substantive changes:

- Plan template now embeds tier-conditional Hierarchy / Identifiers / No-Compression hint blocks, and shows Phase / Wave / Epic block format examples verbatim from the convention ADR.
- Writer persona carries an Approved-Vocabulary table, tier-selection criteria, and a binding CLI usage mandate citing every subcommand verb.
- Three executor personas carry the binding `MUST use vault plan step check / uncheck / toggle` clause that flips canonical-id-affecting state through the CLI rather than hand-editing the checkbox glyph.
- Public README replaces the old catalog blurb with a narrative section walking through one realistic flow (close a Step, add at the tail, re-parent, promote a tier).

## What shipped in Wave 2 (Python implementation)

The `vault plan` Typer subcommand group registered on the existing `vaultspec-core` app, exposing the full ADR surface:

- **Read.** `status` (with `--json`), `check` (with `--fix` and `--json`), `query` (filter by `--phase` / `--wave` / `--open` / `--closed`).
- **Step.** `add`, `insert`, `edit`, `move`, `remove`, plus the state verbs `check` / `uncheck` / `toggle`.
- **Phase.** `add`, `insert`, `edit`, `move`, `remove` (with cascading retirement of descendant Step ids).
- **Wave.** `add`, `insert`, `edit`, `move`, `remove` (cascading retirement of descendant Phase + Step ids; descendants display-paths recomputed).
- **Epic intent.** `show`, `edit` (`L4` plans only; raises `EpicIntentError` on lower tiers).
- **Tier.** `show`, `promote` (transitive `L1` to `L4` in one revision), `demote` (refuses multi-child collapse without `--force`).

The hidden `<!-- RETIRED: ... -->` HTML-comment ledger persists retired canonical ids across parse / serialise round-trips so `next_available_step` / `next_available_phase` / `next_available_wave` never reissue a retired identifier.

## Code review and post-review hardening

The Wave 2 Python implementation went through a code review that produced 5 CRITICAL plus 7 HIGH plus 9 MEDIUM findings. Five CRITICAL fixes (C1 through C5) and six HIGH fixes (H1 through H4 plus H7) landed on the branch as targeted commits with regression tests:

- C1 / C5: identifier retirement now persists via the ledger; `_next_available_id` consults the union of live and retired ids.
- C2 / C3: `_walk_body` captures Phase and Wave intent prose into the model so `apply_all_fixes` no longer overwrites authored text with the `TODO:` placeholder on first pass.
- C4: `move_step` / `move_phase` / `move_wave` reject self-anchored moves with the relevant typed `Move{Step,Phase,Wave}Error`; the dead position-overwrite block in `move_wave` is removed.
- H1: `assert anchor_id is not None` patterns replaced with `if anchor_id is None: raise <typed-error>` so `python -O` invocations surface the documented exception rather than crashing on `NoneType`.
- H2: `noqa: ARG001` suppressions removed from `check_row_contract` and `check_vocabulary`; the unused `plan` parameter is documented and made explicit with `del plan`.
- H3: `check_vocabulary` now matches the bare `## Epic intent` shape (in addition to backticked Wave / Phase headings); a regression test exercises an `## Initiative intent` heading.
- H4: `check_identifiers` runs a parallel raw-text scan for under-padded heading ids that the strict parser silently drops, so a hand-edited Phase heading whose canonical id is one digit wide still produces a `PLAN020` finding.
- H7: `_extract_number` uses a lenient `[SPW]\d+` pattern so legacy single-digit ids do not crash the next-available counters.

A second independent review (post-hardening) surfaced two new HIGH findings and four mediums, all addressed:

- H-NEW-1: `_walk_body` and `_extract_epic_intent` now skip lines matching the retirement-ledger pattern when accumulating intent prose, so a ledger comment lodged inside an intent block parses into the retirement set without polluting authored text and without duplicating on round-trip.
- H-NEW-2: every mutating Typer command applies the `_render_user_errors` decorator that catches the union of typed handler exceptions and emits `error: <message>` plus exit 1 instead of a Rich traceback. Programmer errors still propagate.
- M-NEW-1: dropped `re.IGNORECASE` from the ledger regex so case-sensitivity is consistent end-to-end.
- M-NEW-2 / M-NEW-5: docstring notes on the canonical-position invariant of the ledger and on the in-place mutation semantics of the `clear() + extend(...)` mirror rebuilds.
- M-NEW-3: widened the ledger token regex to `[SPW]\d+` so sub-canonical tokens survive parse, and added `_detect_underpadded_retired_ids` to surface them as `PLAN020`.
- M-NEW-4: replaced the unreachable fallback in `_compute_flat_position` with a `RuntimeError` carrying a clear invariant message.
- L-NEW-1 / L-NEW-2: empty title now serialises as `# (untitled plan)`; previously-silent edit / state verbs now echo a one-line confirmation.

The originally-deferred findings then closed:

- H5: `move_phase` and `move_wave` no longer rebuild `plan.phases` / `plan.steps` via `clear()` + walk; they splice the moving slice via remove + insert at the new flat index. Non-moving entries keep their relative order.
- H6: `phase_remove` and `wave_remove` now `clear()` the removed container's internal lists after detaching, so callers holding references see consistent empty state.
- M1: `_extract_epic_intent` cutoff extended to also stop at H3 sub-headings, not just H1 / H2.
- M3: `promote_tier` parameters now accept `str | None` so callers can distinguish "use the canonical placeholder" from "use this exact text".
- M7: `query.py` uses `!=` rather than `is not` for `Tier` value comparison.
- M4 / M8 / M9: documentation-only fixes covering O(n) lookup complexity and the load-bearing role of corruption factories.

A new CLI verb landed during the closeout: `vault plan phase renumber <PATH> <P##> --to <P##>` is the audited remediation surface for legacy plans where `P##` was incorrectly Wave-scoped. The verb retires the old id, validates the target against live and retired sets, and recomputes descendant Step display paths against the new parent. Applied to the originating plan: W02's `P01`-`P07` are now `P11`-`P17` (W01 already used `P01`-`P10`); plan completion stays at 99 / 99 and `vault plan check` is clean.

Rule-extension prose review surfaced one CRITICAL (C2: missing `MUST` in three executor agent CLI mandates) and six lower-tier findings; all are addressed.

## Tests

The plan-package test suite stands at 369 tests, all passing:

- `test_frontmatter` (45): tier parsing, legacy fallback, malformed schema rejection.
- `test_parser` (75+): clean-plan parametrised matrix at every tier, document-order preservation, intent-prose round-trip (Phase + Wave), corruption tolerance (5 corruption operators), gap preservation on deletion.
- `test_identifiers` (32+): next-available counters with retirement, padding violations, duplicate detection.
- `test_display_path`, `test_serialiser`, `test_status`, `test_query`, `test_checks`, `test_fixes`: full coverage of the supporting modules.
- `test_additive_commands`, `test_state_commands`, `test_destructive_commands`: end-to-end coverage of every mutating verb plus self-anchor rejection regressions and retirement-persistence regressions.
- `test_e2e` (11): Typer CliRunner exercises the full CLI surface end-to-end (status, status --json, check, step check / add / remove, query, tier show / promote, --help, plus the user-grade error-rendering regression).

Every commit cleared the pre-commit gate (`ruff-check`, `ruff-format`, `ty`, `mdformat-check`, `pymarkdown`, Vault Doctor fix / check, provider-artifact check).

## Verification status

Plan completion at 100% (99 of 99 Steps closed via `vault plan step check`); workspace `spec doctor` clean; `vault check all` passes against the new convention rules; `vault plan check` returns zero findings on the originating plan after `--fix` runs idempotently. The full vaultspec_core test suite (1207 tests across every package) passes, confirming the plan-hardening work introduced no regressions in unrelated modules.
