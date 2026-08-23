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
body_hash: 'sha256:ece2f79255f0c8f14496ff7df29724b44412ae57dd8d4339b8cd6bc4bd609037'
---

# `envelope-optimization` plan

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
