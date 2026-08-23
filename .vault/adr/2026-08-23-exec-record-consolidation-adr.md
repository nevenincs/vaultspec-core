---
tags:
  - '#adr'
  - '#exec-record-consolidation'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v2'
body_hash: 'sha256:bfd5aebd3728b641acec38a03410eba65cf702dc4b6673d22cdec7237edb5c7b'
related:
  - "[[2026-08-23-exec-record-consolidation-research]]"
  - "[[2026-05-17-cli-exec-step-records-adr]]"
---

# `exec-record-consolidation` adr: `Consolidate execution records into one append-only ledger per plan` | (**status:** `proposed`)

## Problem Statement

`2026-05-17-cli-exec-step-records-adr` (accepted) made `vault add exec`
Step-aware: one execution record per plan Step. That decision was correct for
the wall it removed, and it is now the dominant cost in the vault.

`2026-08-23-exec-record-consolidation-research` measures the production corpus
and establishes the shape of the cost: execution records dominate the vault by
both bytes and file count, the Step-to-record mapping is exactly 1:1 so count
grows without bound, the body is overwhelmingly prose that names no file, and no
consumer reads that prose. Reading a single plan's execution history no longer
fits in a context window.

Two independent properties drive it - what a record contains, and how many
records a plan produces. A content fix alone leaves the second untouched.

## Considerations

- The sibling `body-v2` schema change addresses content: a mechanical
  `## Changes` path log replaces Description, Outcome, and Notes. It does not
  address cardinality, so 994 files remain 994 files.
- `2026-05-17-cli-exec-step-records-research` rejected folding Steps into one
  document on two grounds: it loses the granularity the plan Step ids were
  introduced to provide, and per-Step records let `vault plan status`
  cross-reference into a real artifact.
- Both objections are about losing per-Step identity, not about file count.
  Identity can live in a row column as well as in a filename.
- `ExecRecordIndex.by_step` is already a feature-and-Step to stem map, which is
  many-to-one capable. Only its source, a single `step_id` frontmatter field,
  was one-to-one.
- The same research records why the original wall mattered: two agents skipped
  exec records rather than violate the no-hand-edit rule. Any consolidated
  shape must therefore be writable by a verb, not by hand.

## Considered options

- **Keep one record per Step, `body-v2` only.** Cuts bytes by roughly 80% but
  leaves the file count untouched and the 1:1 growth unbounded. Rejected as
  insufficient: it treats the symptom and leaves the larger cost.
- **One document per Phase.** Reduces count without a principled unit. A Phase
  is a planning container, not an execution boundary, and Step identity would
  still need a row column. Rejected: same mechanism, arbitrary granularity.
- **One append-only ledger per plan, Step identity in the row.** Chosen. One
  document per plan, one row per touched path, each row led by its Step id.
- **Drop execution records entirely.** Rejected: `exec_missing` and the
  grounding trace are real consumers, and the audit trail is the point of the
  feature.

## Constraints

- `2026-05-17-cli-exec-step-records-adr` names the `vault add exec` signature a
  user contract and specifies a deprecation cycle for changing it. The ledger
  is therefore additive: the per-Step path is unchanged and remains default.
- The `vault add` Typer signature sits at the repository `max-args` floor of
  17, a ratchet documented as down-only. The ledger writer cannot add flags
  there and belongs in the existing `vault exec` group.
- The immutable body-schema registry forbids editing a published contract, so a
  ledger must reuse an existing shape or declare a new one.
- The no-hand-edit rule means rows must be appended by a verb.
- The 7,362 existing `body-v1` records must keep validating untouched; a schema
  bump must not reclassify them.

## Implementation

A ledger lives at one path per plan inside the feature folder, named with a
`-ledger` stem suffix. Its body is a single `## Changes` section of mechanical
rows, each naming a Step id, a change operation, and the path it touched.

A ledger row is a per-Step record row with a Step-id column prepended, so the
ledger reuses the `body-v2` `Changes` contract exactly and needs no new schema.
`vaultcore/exec_ledger.py` is the single parser both consumers share, so the
index and the check cannot drift. It parses only inside `## Changes`, so a
`## Notes` exception section can never register coverage.

`ExecRecordIndex.build` registers every Step a ledger names against that ledger
stem, in both its graph and disk paths. `check_exec_mapping` classifies every
covered Step against the parent plan, reading the body from the snapshot it
already holds. Writing is `vault exec log`, which creates the ledger on first
use and appends thereafter. Appends route through `refresh_modified_stamp`, the
mandated mutator helper, so the `modified` stamp and the `body_hash`
re-attestation stay paired. Rows are never rewritten, and re-logging a row is
idempotent. The writer never infers an operation from disk state: an executor
knows what it did, and guessing would record evidence nobody produced.

## Rationale

The rejection recorded in `2026-05-17-cli-exec-step-records-research` turns on
granularity, and the ledger preserves it. A Step id resolves through a ledger
exactly as it does through a per-Step file, so `vault plan status` still
cross-references a real artifact and a reader can still trace one Step. What is
lost is one filesystem entry per Step, which was the cost, not the granularity.

The measured effect on the largest plan in the corpus, `import-centralization`
at 388 Steps, is 659 KB across 388 files becoming roughly 56 KB in one file:
91.5% smaller and 388 times fewer files. Because identity moved into a column
rather than being discarded, this is a representation change, not a loss of
fidelity.

Additive delivery is what makes the reversal safe. The per-Step path is
untouched and still the default, so this record supersedes the rejection
recorded in the Considerations of its predecessor, not the Step-awareness
decision itself, which stands.

## Consequences

- Execution history for a plan becomes one document that fits in context, and
  exec growth is bounded by plan count rather than Step count.
- A ledger is a single write target, so two agents logging different Steps of
  one plan concurrently contend on it where per-Step files did not. Appends are
  atomic and idempotent, which makes a lost update recoverable by re-logging,
  but ordering under concurrency is not guaranteed.
- Per-Step file granularity is genuinely gone. A per-Step file history no
  longer exists as a view, and per-Step blame becomes a row-level diff.
- The existing records are not migrated. They keep declaring `body-v1` and
  remain valid, so the corpus is mixed-shape and any reader must handle both.
  Migration would discard prose and require reconstructing file lists from git
  history, and is deliberately left as a separate decision.
- The `--all-steps` bulk form has no ledger equivalent, because pre-scaffolding
  rows invents evidence for work not yet done, which the mechanical contract
  forbids.
