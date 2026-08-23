---
tags:
  - '#plan'
  - '#envelope-optimization'
date: '2026-08-23'
tier: L3
related:
  - '[[2026-08-23-envelope-optimization-adr]]'
  - '[[2026-08-23-envelope-optimization-research]]'
modified: '2026-08-23'
body_schema: body-v1
body_hash: 'sha256:78a92e10fa3fb9d1ea263cf73e9d88da7c9a7f0ebd6dd03008afb3d645b4e01b'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace envelope-optimization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `envelope-optimization` plan

<!-- One-line headline summary plan. -->

## Description

Executes `2026-08-23-envelope-optimization-adr`, grounded in
`2026-08-23-envelope-optimization-research`. The ADR governs every Wave: it sets the budget
ladder, the four-part boundedness contract, the density floor, and the rule that elision
belongs in the payload rather than the render.

Waves are sequenced by leverage, not by severity. `W01` restores honest measurement and
removes the two multipliers that sit beneath every later change, so no reduction after it is
measured through a doubling that a subsequent change removes anyway. `W02` inverts the
contract itself; without it the next author reads a specification that still says the machine
surface is uncapped. `W03` is separated because a quadratic enumeration is a compute defect
that no response budget can reach. `W04` applies the contract per command in measured-byte
order. `W05` is last because it is fixed cost rather than corpus-scaled.

This plan is expected to grow. `W04` in particular is open-ended: commands join it as
measurement finds them, and Steps are appended at the next canonical id rather than
renumbered. Every Step carries a before and after measurement taken against a
10,476-document benchmark corpus, so expansion stays traceable and each claim of improvement
is anchored to a number rather than to a judgement.

## Steps

## Wave `W01` - Instrument and de-multiply

Correct the measurement that failed to see half the surface, then remove the two multipliers that apply beneath every later fix. Nothing downstream can be measured honestly until this wave lands.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

### Phase `W01.P01` - Correct the ratchet

The tool-surface guard measured 21,943 of 43,919 real characters. Restore honest measurement and give the read-only surface its own ceiling before any reduction is attempted.

- [x] `W01.P01.S01` - Serialise the tool definition in the true wire form and add a read-only ceiling; `src/vaultspec_core/mcp_server/tests/test_context_budget.py`.

### Phase `W01.P02` - Remove the surface-wide multipliers

Double serialisation on the MCP path and indent-2 on the CLI path are flat multipliers on every command. One registration-layer change and one shared emitter.

- [x] `W01.P02.S02` - Return an explicit result object carrying a summary text block so the transport stops emitting a second copy; `src/vaultspec_core/mcp_server/tools`.
- [x] `W01.P02.S03` - Route every CLI envelope through one emitter using compact separators, with pretty output opt-in; `src/vaultspec_core/cli/rendering_shapes.py`.

## Wave `W02` - Invert the boundedness contract

Move elision out of the render layer and into the payload, so the machine surface is bounded by contract and the human render derives from the same fields. This is the premise change the ADR turns on.

### Phase `W02.P03` - Move elision into the payload

Relocate the existing elision helper ahead of the format branch and define the envelope vocabulary that carries returned, total, truncated and next offset.

- [x] `W02.P03.S04` - Define the bounded envelope vocabulary carrying returned, total, truncated and next offset; `src/vaultspec_core/cli/rendering_shapes.py`.
- [x] `W02.P03.S05` - Apply elision to the payload ahead of the format branch and derive the human summary line from it; `src/vaultspec_core/cli/_repair_render.py`.

### Phase `W02.P04` - Retire the uncapped-machine-contract wording

Three docstrings specify the machine surface as deliberately uncapped. Leaving them in place guarantees the defect is reintroduced by the next author.

- [x] `W02.P04.S06` - Replace the uncapped-machine-contract docstrings with the bounded contract; `src/vaultspec_core/vaultcore/checks/_base.py`.

## Wave `W03` - Bound the quadratic enumeration

Derived-edge generation is a compute defect before it is a payload defect; a response budget cannot reach a command that does not return. Bound it at the algorithm.

### Phase `W03.P05` - Bound derived-edge generation

Replace full pair materialisation with a bounded per-node selection, and invert the CLI default so the expensive product is opt-in.

- [x] `W03.P05.S07` - Replace full pair materialisation with a bounded per-node selection and a weight floor; `src/vaultspec_core/graph/derived.py`.
- [x] `W03.P05.S08` - Invert the derived-edge CLI default and require an explicit scope for a full graph export; `src/vaultspec_core/cli/vault_cmd.py`.

## Wave `W04` - Bound per-command envelopes

Apply the contract to individual commands in measured-byte order, largest first. Expandable: new commands join this wave as measurement finds them.

### Phase `W04.P06` - Bound the orientation path

The rollup emitted on every session open, and the trace behind it.

- [x] `W04.P06.S09` - Cap active features in the rollup, rank by recency and emit the total; `src/vaultspec_core/vaultcore/orientation_rollup.py`.
- [x] `W04.P06.S10` - Forward a limit from the status tool instead of calling the rollup bare; `src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `W04.P06.S11` - Evaluate the projection flag before the format flag so a narrowing flag cannot increase the payload; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `W04.P07` - Bound the discovery and listing paths

Document search, feature listing and the full-corpus document dump.

- [x] `W04.P07.S12` - Replace the boolean body flag with a bounded projection and enforce a response byte budget; `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `W04.P07.S13` - Bound and validate the find limit and split the two-mode result row; `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `W04.P07.S14` - Add limit and offset to document listing, make paths vault-relative and drop derivable fields; `src/vaultspec_core/vaultcore/query_listing.py`.
- [x] `W04.P07.S24` - Window the feature listing, which returns every feature unbounded; `src/vaultspec_core/cli/vault_feature_cmd.py`.

### Phase `W04.P08` - Bound the diagnostics and batch paths

Payloads whose size grows with how broken the vault is, and batch results that echo one row per submitted item.

- [x] `W04.P08.S15` - Cap diagnostics per check on the machine surface and honour the verbosity flag there; `src/vaultspec_core/cli/vault_check_cmd.py`.
- [x] `W04.P08.S16` - Make the batch result exception-based and cap batch input length; `src/vaultspec_core/mcp_server/results.py`.
- [x] `W04.P08.S19` - Emit each repair finding once instead of five times and bound the preview payload; `src/vaultspec_core/cli/_repair_render.py`.

## Wave `W05` - Reduce the static per-turn surface

Fixed cost rather than corpus-scaled, so it ranks last; but it is the only cost paid on every turn of every conversation regardless of what the agent does.

### Phase `W05.P09` - Stop shipping developer documentation to the model

Output schemas are 61% of the static surface because Pydantic lifts model docstrings into schema descriptions.

- [x] `W05.P09.S17` - Suppress model docstrings and auto-derived titles in generated schemas; `src/vaultspec_core/mcp_server/results.py`.
- [x] `W05.P09.S18` - Trim returns, raises and context prose from tool descriptions and move parameter guidance onto fields; `src/vaultspec_core/mcp_server/tools`.

## Wave `W06` - Repair the index-preview regression

Not an envelope defect and not governed by the envelope ADR; tracked here for continuity because it was found by this campaign's benchmarking and blocks measuring the repair surface at all. Commit 7d6678ca made the dry-run index preview build a fresh cache-disabled vault graph once per feature, giving O(features x documents). Three independent methods - profiling, a scaling ladder, and bisection - agree.

### Phase `W06.P10` - Restore a single shared graph for the index preview

The preview needs index filenames per feature, not a private graph per feature. One shared graph, reused.

- [x] `W06.P10.S20` - Build the vault graph once and reuse it across features in the index preview; `src/vaultspec_core/vaultcore/repair.py`.
- [x] `W06.P10.S21` - Stop disabling the graph cache in feature index generation; `src/vaultspec_core/vaultcore/index.py`.
- [x] `W06.P10.S22` - Add a scaling regression guard asserting repair stays linear in document count; `src/vaultspec_core/tests`.
- [x] `W06.P10.S23` - Remove the per-feature graph rebuild from the mutating index refresh while keeping the under-lock membership guarantee; `src/vaultspec_core/vaultcore/repair.py`.

## Parallelization

Waves are sequenced and must land in order; the dependency is real rather than conventional,
because `W01` changes what every later measurement means and `W02` changes the contract those
measurements are judged against.

Within Waves, Phases may run in parallel where they share no file. `W01.P01` must precede
`W01.P02`, since the corrected ratchet is what proves the multiplier removals held. `W04.P06`,
`W04.P07` and `W04.P08` are independent of one another and may proceed in any order once `W02`
has landed, with the exception that both `W04.P06` and `W03.P05` touch the graph command and
must not be executed concurrently.

## Verification

A Step is complete when all five hold: the command declares a default cap, a hard ceiling the
caller cannot raise, a total count, and a truncation marker; its payload sits inside the
budget tier the ADR assigns it, measured against the benchmark corpus; information density is
at or above the floor; every narrowing flag reduces the payload monotonically; and no
truncation occurs without a marker.

Measurement is taken before and after each Step against the same corpus and recorded with the
Step's execution record, so a later reader can reconstruct the gain rather than trust it. The
tool-surface ratchet corrected in `W01.P01` guards the static surface for the duration of the
campaign; its ceiling is lowered as Waves land and is never raised.
