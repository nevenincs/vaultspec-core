---
tags:
  - '#plan'
  - '#cli-presentation-uniformity'
date: '2026-06-24'
modified: '2026-06-24'
tier: L2
related:
  - '[[2026-06-24-cli-presentation-uniformity-adr]]'
  - '[[2026-06-24-cli-presentation-uniformity-research]]'
---

# `cli-presentation-uniformity` plan

Make vaultspec-core help and data read bog-standard like `vaultspec-rag` and `glow`: plain Click help, one hint footer, no table-like surfaces.

## Description

This plan executes the `cli-presentation-uniformity` ADR. It disables Rich help rendering across every Typer app, normalizes help and option text, routes every next-step hint through one `Next action:` footer, converts the remaining hand-formatted data surfaces onto the four shared rendering shapes, collapses the divergent glyph vocabularies to one ASCII set, and adds the contract tests that keep help and data plain. The authorizing decision and its parents (`cli-output-standardization`, `cli-next-step-hints`) are linked in the `related:` frontmatter. Work proceeds phase by phase; each phase is independently shippable.

## Steps

### Phase `P01` - plain-Click help framework

Replace Rich-panel help with plain Click help across every Typer app and normalize help text.

- [x] `P01.S01` - add a Typer factory that injects `rich_markup_mode=None` and the shared `no_args_is_help` default; `src/vaultspec_core/cli/_app.py`.
- [x] `P01.S02` - adopt the factory for the root app and remove its inline Examples block from `help=`; `src/vaultspec_core/cli/root.py`.
- [x] `P01.S03` - adopt the factory for the vault command apps; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S04` - adopt the factory for the plan command apps; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `P01.S05` - adopt the factory for the spec command apps; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P01.S06` - adopt the factory for the config app and remove its inline examples; `src/vaultspec_core/cli/config_cmd.py`.
- [x] `P01.S07` - adopt the factory for the migrations app and remove its inline examples; `src/vaultspec_core/cli/migrations_cmd.py`.
- [x] `P01.S08` - adopt the factory for the link app; `src/vaultspec_core/cli/link_cmd.py`.
- [x] `P01.S09` - normalize option help strings to imperative sentence case with terminal periods; `src/vaultspec_core/cli/`.
- [x] `P01.S10` - relocate the root and group Examples into the bundled CLI reference source; `src/vaultspec_core/builtins/`.

### Phase `P02` - uniform hint footer

Render every next-step hint through one shared helper in the `Next action:` form.

- [x] `P02.S11` - reshape the shared hint helper to emit one `Next action:` footer with the command indented on the next line; `src/vaultspec_core/cli/rendering.py`.
- [x] `P02.S12` - reroute the install and sync ad-hoc footers through the shared hint helper; `src/vaultspec_core/cli/root.py`.
- [x] `P02.S13` - reroute the status rollup and trace hints through the shared hint helper; `src/vaultspec_core/cli/status_cmd.py`.
- [x] `P02.S14` - reroute the migrations suggestion line through the shared hint helper; `src/vaultspec_core/cli/migrations_cmd.py`.

### Phase `P03` - eradicate divergent output surfaces

Convert every hand-formatted data surface onto a Record, Listing, or Tree payload.

- [x] `P03.S15` - convert `vault stats` output to a Record payload; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S16` - convert `vault list` output to a Listing payload; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S17` - convert `vault graph` metric breakdowns to Record plus Listing payloads; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S18` - convert the `vault repair` run report to Tree plus summary payloads; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S19` - convert the `status` rollup to the shared shapes; `src/vaultspec_core/cli/status_cmd.py`.
- [x] `P03.S20` - convert the `status` trace to the shared shapes; `src/vaultspec_core/cli/status_cmd.py`.
- [x] `P03.S21` - convert `migrations status` to a Listing payload; `src/vaultspec_core/cli/migrations_cmd.py`.
- [x] `P03.S22` - collapse `doctor`'s two internal styles onto the shared shapes; `src/vaultspec_core/cli/root.py`.

### Phase `P04` - glyph and wrap unification

Collapse the divergent glyph sets to one ASCII vocabulary and make output wrap on a narrow terminal.

- [x] `P04.S23` - map the preflight glyph set onto the single ASCII status vocabulary; `src/vaultspec_core/cli/root.py`.
- [x] `P04.S24` - map the step-checkbox glyph set onto the single ASCII status vocabulary; `src/vaultspec_core/cli/status_cmd.py`.
- [x] `P04.S25` - map the migration-status glyph set onto the single ASCII status vocabulary; `src/vaultspec_core/cli/migrations_cmd.py`.
- [x] `P04.S26` - adjust console wrapping so plain output wraps on a narrow terminal while renderers stay width-independent; `src/vaultspec_core/console.py`.

### Phase `P05` - tests and bundled reference

Lock the plain-help and uniform-hint guarantees with tests and regenerate the reference.

- [x] `P05.S27` - extend the no-box determinism test to assert no `--help` screen contains a panel border or box-drawing glyph; `src/vaultspec_core/tests/cli/`.
- [x] `P05.S28` - add a help-format test asserting plain `Usage`/`Options`/`Commands` sections and narrow-width wrapping; `src/vaultspec_core/tests/cli/`.
- [x] `P05.S29` - add a hint-uniformity test asserting a single `Next action:` footer form; `src/vaultspec_core/tests/cli/`.
- [x] `P05.S30` - regenerate the bundled CLI reference and update its drift test; `src/vaultspec_core/tests/cli/`.

## Parallelization

`P01` lands first; it changes how help renders and unblocks the help tests. `P02`, `P03`, and `P04` share no hard interdependency and may proceed in parallel once `P01` is in, though `P04.S04` (console wrapping) should land before `P05` asserts narrow-width behavior. `P05` runs last because it locks the guarantees the earlier phases establish. Within `P03`, each Step touches a distinct surface and the eight Steps may be parallelized.

## Verification

The plan is complete when every Step is closed (`- [x]`). Mission success criteria:

- No `--help` screen at any command depth renders a Rich panel or box-drawing glyph; all match the plain `Usage`/`Arguments`/`Options`/`Commands` shape of `vaultspec-rag --help`.
- Help wraps cleanly under a narrow terminal width.
- Every next-step hint renders in exactly one `Next action:` footer form, with the JSON `next_step` field and `--no-hints` / `VAULTSPEC_NO_HINTS` suppression unchanged.
- No data surface emits hand-formatted multi-column output or box-drawing; `vault stats`, `vault list`, `vault graph` metrics, `vault repair`, both `status` modes, `migrations status`, and `doctor` all route through the four shared shapes.
- One ASCII glyph vocabulary appears across all surfaces.
- The extended contract test, help-format test, and hint-uniformity test pass; the bundled CLI reference drift test passes.
