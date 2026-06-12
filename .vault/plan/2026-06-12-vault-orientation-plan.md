---
tags:
  - '#plan'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
tier: L3
related:
  - '[[2026-06-12-vault-orientation-adr]]'
  - '[[2026-06-12-vault-orientation-research]]'
---

# `vault-orientation` plan

Ship the orientation surface: a CLI-maintained modified frontmatter stamp as the
vault's recency source, a batched status core, the vault status rollup and grounding
verb, and the firmware bootstrap mandate that enrolls it.

## Description

Implements the accepted vault-orientation ADR (decisions D1 through D8) on the
grounding research's capability survey. Wave one introduces the `modified:` frontmatter
stamp end to end: document model with lenient multi-format parsing (D3b), scaffold-time
stamping, template schema rows, stamp refresh in every mutating CLI verb, a check-fix
reconciliation path for permitted hand edits, and a backfill migration (D3, D3a). Wave
two builds the batched status core (D6) and the `vault status` verb: a vault-wide
rollup of active features, plans in flight, and recent changes (D2, D4), plus a
targeted grounding trace that maps each plan step to its execution record and groups
grounding documents by type, graph-backed internally but rendered as simple stems and
hints (D1, D5, D7). Wave three documents the stamp in the firmware schema surfaces and
adds the orientation bootstrap mandate, which may only ship once the verb exists (D8).
No standalone builtin rule ships for the stamp discipline; the CLI enforces it.

## Steps

## Wave `W01` - modified stamp foundation

Introduce the CLI-maintained modified frontmatter stamp end to end: model, lenient parsing, scaffold-time stamping, template schema, mutator refresh, check-fix reconciliation, and the backfill migration. The status surface in the next Wave depends on this stamp as its recency source; the authorizing decisions are D3, D3a, and D3b.

### Phase `W01.P01` - stamp model, parsing, and scaffold

Add the modified field to the document model with lenient date parsing, stamp it at scaffold time, and cover the behaviour with tests.

- [x] `W01.P01.S01` - add the modified field with lenient multi-format date parsing and canonical-form validation to DocumentMetadata; `src/vaultspec_core/vaultcore/models.py`.
- [x] `W01.P01.S02` - parse and surface the modified frontmatter field through typed metadata parsing; `src/vaultspec_core/vaultcore/parser.py`.
- [x] `W01.P01.S03` - stamp modified equal to date at scaffold time in document hydration; `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `W01.P01.S04` - add stamp model, lenient parsing, and scaffold-stamp tests using real files; `src/vaultspec_core/vaultcore/tests/test_modified_stamp.py`.

### Phase `W01.P02` - template schema rows

Add the modified field and its FRONTMATTER RULES comment line to every shipped template.

- [x] `W01.P02.S05` - add the modified field and its frontmatter comment line to the research template; `src/vaultspec_core/builtins/templates/research.md`.
- [x] `W01.P02.S06` - add the modified field and its frontmatter comment line to the reference template; `src/vaultspec_core/builtins/templates/reference.md`.
- [x] `W01.P02.S07` - add the modified field and its frontmatter comment line to the adr template; `src/vaultspec_core/builtins/templates/adr.md`.
- [x] `W01.P02.S08` - add the modified field and its frontmatter comment line to the plan template; `src/vaultspec_core/builtins/templates/plan.md`.
- [x] `W01.P02.S09` - add the modified field and its frontmatter comment line to the exec-step template; `src/vaultspec_core/builtins/templates/exec-step.md`.
- [x] `W01.P02.S10` - add the modified field and its frontmatter comment line to the exec-summary template; `src/vaultspec_core/builtins/templates/exec-summary.md`.
- [x] `W01.P02.S11` - add the modified field and its frontmatter comment line to the audit template; `src/vaultspec_core/builtins/templates/audit.md`.
- [x] `W01.P02.S12` - add the modified field and its frontmatter comment line to the code-review template; `src/vaultspec_core/builtins/templates/code-review.md`.
- [x] `W01.P02.S13` - add the modified field and its frontmatter comment line to the index template; `src/vaultspec_core/builtins/templates/index.md`.

### Phase `W01.P03` - mutator stamp refresh

Refresh the modified stamp from every CLI verb that mutates a vault document.

- [x] `W01.P03.S14` - refresh the modified stamp on every plan serialization write; `src/vaultspec_core/plan/serialiser.py`.
- [x] `W01.P03.S15` - refresh the modified stamp on both documents during adr supersession; `src/vaultspec_core/core/adr.py`.
- [x] `W01.P03.S16` - refresh the source audit's modified stamp on rule promotion; `src/vaultspec_core/core/rules.py`.
- [x] `W01.P03.S17` - refresh the modified stamp on related-frontmatter link mutations; `src/vaultspec_core/vaultcore/related_surgery.py`.
- [x] `W01.P03.S18` - refresh the modified stamp on repair-pipeline document rewrites; `src/vaultspec_core/vaultcore/repair.py`.
- [x] `W01.P03.S19` - add mutator stamp-refresh integration tests exercising the real CLI verbs; `src/vaultspec_core/tests/cli/test_modified_stamp_mutators.py`.

### Phase `W01.P04` - reconciliation and backfill

Reconcile hand-edited documents through the check-fix path with canonical normalization, and backfill the stamp on existing vaults via a schema migration.

- [x] `W01.P04.S20` - add a checker that flags missing, unparseable, or stale modified stamps and normalizes parsed values to canonical form under fix; `src/vaultspec_core/vaultcore/checks/modified_stamp.py`.
- [x] `W01.P04.S21` - register the modified-stamp checker in the check registry; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `W01.P04.S22` - add checker tests covering lenient parsing, normalization, and unparseable-value findings; `src/vaultspec_core/vaultcore/checks/tests/test_modified_stamp.py`.
- [x] `W01.P04.S23` - add a schema migration backfilling modified from date across existing vault documents; `src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py`.
- [x] `W01.P04.S24` - add migration tests covering backfill, idempotence, and lenient date handling; `src/vaultspec_core/migrations/tests/test_m_0_1_29_modified_stamp_backfill.py`.

## Wave `W02` - status rollup and grounding verb

Build the batched status core and the vault status CLI verb (rollup and targeted grounding trace) on top of the Wave one stamp. Depends on Wave one for recency data; authorizing decisions are D1, D2, D4, D5, D6, and D7.

### Phase `W02.P05` - batched status core

Compute plans-in-flight, per-plan completion, active features, and recency in one batched pass, with the graph-backed grounding trace kept behind a simple data model.

- [x] `W02.P05.S25` - extend plan status with a batched all-plans collector sharing one exec-record step-id index; `src/vaultspec_core/plan/status.py`.
- [x] `W02.P05.S26` - add the orientation rollup module computing active features, plans in flight, recency ordering, and the graph-backed step-keyed grounding trace; `src/vaultspec_core/vaultcore/orientation.py`.
- [ ] `W02.P05.S27` - add orientation core tests over a synthetic vault covering rollup, recency fallback, and unlinked-record reporting; `src/vaultspec_core/vaultcore/tests/test_orientation.py`.

### Phase `W02.P06` - vault status verb

Expose the rollup and the targeted grounding trace as the vault status CLI verb with hints and the versioned JSON envelope.

- [ ] `W02.P06.S28` - add the vault status command with rollup and targeted modes, limit and since flags, advisory hints, and the versioned json envelope; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W02.P06.S29` - add cli tests for vault status covering both modes, hints, json schema, and stem-only output; `src/vaultspec_core/tests/cli/test_vault_status.py`.

## Wave `W03` - firmware and documentation

Ship the orientation bootstrap mandate and the modified stamp schema documentation across the builtin firmware, regenerate the CLI references, and update the user-facing docs. Depends on Wave two because firmware must never name unshipped verbs; authorizing decision is D8 plus the firmware-reference-parity rule.

### Phase `W03.P07` - firmware mandate and schema docs

Document the modified field in the firmware schema surfaces and add the orientation bootstrap mandate now that the verb ships.

- [ ] `W03.P07.S30` - document the modified field in the frontmatter schema and tag sections; `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [ ] `W03.P07.S31` - add the vault status command row and the orientation bootstrap mandate; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [ ] `W03.P07.S32` - add the zeroth-move orientation paragraph ahead of the pipeline table; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [ ] `W03.P07.S33` - add modified to the curator's allowed frontmatter keys with the lenient-parse repair note; `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.

### Phase `W03.P08` - reference and user docs

Regenerate the generator-owned CLI references and describe the orientation surface in the user-facing documentation.

- [ ] `W03.P08.S34` - regenerate the generator-owned cli reference regions for the new verb; `src/vaultspec_core/builtins/reference/cli.md`.
- [ ] `W03.P08.S35` - describe the orientation surface and the modified stamp in the framework manual; `docs/framework.md`.

## Parallelization

Waves are sequenced: Wave two consumes the stamp Wave one introduces, and Wave three's
firmware may only name the verb Wave two ships. Within Wave one, Phase `W01.P01` must
land first (the model is the dependency of everything else); `W01.P02` (templates) and
`W01.P03` (mutators) may then run in parallel; `W01.P04` (reconciliation and backfill)
follows `W01.P03` because the checker validates the stamps the mutators write. Within
Wave two, `W02.P05` precedes `W02.P06` (the verb renders the core). Within Wave three,
`W03.P07` and `W03.P08` may run in parallel. Template rows inside `W01.P02` are
mutually independent and freely parallel.

## Verification

The plan is complete when every Step is closed and the following checks hold:

- The full test suite passes, including the new stamp, orientation, migration, and
  `vault status` test files; no mocks, skips, or tautological assertions.
- A fresh scaffold via `vaultspec-core vault add` carries `modified:` equal to `date:`;
  a plan mutation, an adr supersession, and a link mutation each refresh the target's
  stamp.
- `vaultspec-core vault check all --fix` normalizes a deliberately mis-formatted stamp
  to canonical form and flags an unparseable one without dropping it.
- `vaultspec-core migrations run` backfills `modified:` across a pre-existing vault and
  is idempotent on a second run.
- `vaultspec-core vault status` lists plans in flight with open-step counts and recent
  documents as stems plus hints, with no graph structures in the output; the targeted
  mode maps steps to record stems and reports unlinked records; `--json` matches the
  versioned envelope.
- The CLI language-contract and reference-drift suites pass after the reference
  regeneration, proving every firmware mention of the new verb resolves against the
  live command tree.
- Code review via the verify phase signs off with no critical or high findings.
