---
tags:
  - '#plan'
  - '#cli-output-standardization'
date: '2026-06-13'
modified: '2026-06-13'
tier: L2
related:
  - '[[2026-06-13-cli-output-standardization-adr]]'
  - '[[2026-06-13-cli-output-standardization-research]]'
---

# `cli-output-standardization` plan

Implement the vaultspec CLI output contract: build a shared shape vocabulary, then
migrate every box-drawing read surface onto it, close the machine-surface gaps, and
pin determinism and the no-box guarantee with a contract test.

## Description

Implements the accepted output-contract ADR on the inventory research. Phase one
builds the foundation in `cli/rendering.py`: the Record, Listing, and box-free Tree
shapes, each with a text renderer and a JSON renderer over one payload object, plus
the shared truncation, summary-line, and empty-state helpers - mirroring how
`OutcomeItem` already feeds `render_outcomes` and `outcomes_as_json`. Phases two and
three migrate the surfaces command by command: the ten `spec` table surfaces, then
`config list`, the graph metrics and graph tree, the dry-run tree, and the
install/uninstall panels, deleting the `rich.table` / `Panel` / `box` imports from
each call site. Phase four closes the `--json` gaps on the mutators the research
flagged (the `vault plan` structural verbs, `vault rule promote`, `vault adr supersede`) by mapping their results onto the existing `Outcome` shape. Phase five
adds the determinism and no-box contract test, updates the few coupled tests, and
runs the suite, `ty`, and `prek` to green. Surfaces that already emit plain,
box-free lines (`vault list`, `vault feature list`, `vault link list`, `migrations status`, and the `render_outcomes` family) need no migration; the contract test
validates them rather than rewriting them. The parent `Outcome` and `json_envelope`
contracts are extended, never forked.

## Steps

### Phase `P01` - shape vocabulary foundation

Build the Record, Listing, and box-free Tree shapes and the shared helpers in the
rendering module, each shape a payload object feeding one text renderer and one JSON
renderer, with unit coverage.

- [x] `P01.S01` - add the Record shape (a Field payload, render_record, record_as_json, and emit_record) for single-entity field/value surfaces, key: value per line at a two-space indent with stable field order equal to the JSON keys; `src/vaultspec_core/cli/rendering.py`.
- [x] `P01.S02` - add the Listing shape (Column and Cell payloads, render_listing, listing_as_json, and emit_listing) for multi-row surfaces, single-space fields with no width padding and optional value-level color for the human surface only; `src/vaultspec_core/cli/rendering.py`.
- [x] `P01.S03` - add a box-free Tree renderer that emits two-space indentation per depth and an ASCII status-glyph set with no connector characters, plus its JSON form; `src/vaultspec_core/cli/rendering.py`.
- [x] `P01.S04` - add the shared helpers: fixed-budget marked truncation, the per-shape terminating summary line, and the explicit one-line empty state; `src/vaultspec_core/cli/rendering.py`.
- [x] `P01.S05` - add factory-based unit tests asserting text and JSON parity, single-space fields, the summary line, empty states, and the absence of any box-drawing glyph for each shape; `src/vaultspec_core/tests/cli/test_rendering.py`.

### Phase `P02` - migrate the spec table surfaces

Move every `spec` Rich table onto the new shapes, deleting the `rich.table` and `box`
imports from each call site.

- [x] `P02.S06` - migrate spec rules status to the Record shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S07` - migrate spec rules list to the Listing shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S08` - migrate spec skills list to the Listing shape with fixed-budget description truncation; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S09` - migrate spec agents list to the Listing shape with fixed-budget description truncation; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S10` - migrate spec hooks list to the Listing shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S11` - migrate spec hooks status to the Record shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S12` - migrate spec mcps list to the Listing shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S13` - migrate spec mcps status to the Record shape; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S14` - migrate spec system show parts and targets into two Listings; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P02.S15` - migrate the workspace diagnosis table shared by spec doctor and root doctor to the Listing shape with value-styled status cells; `src/vaultspec_core/cli/spec_cmd.py`.

### Phase `P03` - migrate the remaining box constructs

Move the config, graph, dry-run, and install panels off box-drawing onto the shapes
and the box-free tree.

- [x] `P03.S16` - migrate config list to the Listing shape; `src/vaultspec_core/cli/config_cmd.py`.
- [x] `P03.S17` - migrate vault graph --metrics to the Record shape; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S18` - migrate the vault graph default tree to the box-free Tree renderer; `src/vaultspec_core/graph/api.py`.
- [x] `P03.S19` - reimplement render_dry_run_tree on the box-free Tree renderer; `src/vaultspec_core/cli/rendering.py`.
- [x] `P03.S20` - replace the install and uninstall Panel summaries with box-free header lines; `src/vaultspec_core/cli/rendering.py`.

### Phase `P04` - close the machine-surface gaps

Give every mutator the research flagged a `--json` surface by mapping its result onto
the existing Outcome shape.

- [x] `P04.S21` - add a --json Outcome surface to the vault plan step mutators; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `P04.S22` - add a --json Outcome surface to the vault plan phase, wave, tier, and epic mutators; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `P04.S23` - add a --json Outcome surface to vault rule promote; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P04.S24` - add a --json Outcome surface to vault adr supersede; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P05` - contract test, coupled tests, and gate

Pin the central guarantees as tests, update the few coupled assertions, and prove the
suite green.

- [x] `P05.S25` - add the output-contract test asserting byte-identical output across two terminal widths and stdout encodings and the absence of box-drawing glyphs in the data path; `src/vaultspec_core/tests/cli/test_output_contract.py`.
- [x] `P05.S26` - update the coupled graph tree-render and doctor substring tests to the box-free format; `src/vaultspec_core/tests`.
- [x] `P05.S27` - run pytest, ty, and prek to green across the changed surfaces and smoke-test a representative list, status, and tree command in text and --json; `repository root`.

## Parallelization

Phase `P01` is a hard prerequisite for every later phase: nothing migrates before the
shapes exist. Once `P01` lands, Phases `P02`, `P03`, and `P04` touch disjoint files
(`spec_cmd.py`; `config_cmd.py` / `vault_cmd.py` / `graph/api.py` / `rendering.py`;
`plan_cmd.py` / `vault_cmd.py`) and may proceed in parallel, with the one caveat that
`P03` and `P04` both touch `vault_cmd.py` and must serialize their edits to that file.
Within a phase, each Step is an independent surface and the Steps may be worked
concurrently. Phase `P05` runs last, after every migration has landed.

## Verification

The plan is complete when every Step is closed (`- [x]`). The mission criteria:
no `rich.table.Table`, `rich.panel.Panel` border, or `box.*` import remains in the
CLI data path; every migrated surface offers `--json` through the canonical envelope;
the contract test proves byte-identical output across two terminal widths and two
stdout encodings and asserts no box-drawing glyph appears; and the full test suite,
`ty`, and `prek` pass. Final sign-off is a `vaultspec-code-review` pass over the
migration.
