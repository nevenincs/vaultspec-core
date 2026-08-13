---
tags:
  - '#adr'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:cd303dd69c4223f1d8d9244499025fb7727197d54ecde945ae631380c74d624a'
related:
  - "[[2026-08-13-plan-mutation-concurrency-research]]"
  - "[[2026-08-13-plan-mutation-concurrency-reference]]"
---

# `plan-mutation-concurrency` adr: `lock-scoped plan mutation transactions` | (**status:** `accepted`)

## Problem Statement

Plan mutation verbs are the canonical owner of identifier-affecting changes, but their
current read-modify-write sequence is not serialized. Atomic replacement and
post-write verification do not prevent two valid writers from deriving from the same
snapshot and losing one update. The repository needs one concurrency contract shared
by CLI and MCP (`2026-08-13-plan-mutation-concurrency-research`).

## Considerations

- The lock must cover load, parse, mutation, guards, persistence, and post-write
  verification; beginning at persistence is too late
  (`2026-08-13-plan-mutation-concurrency-reference`).
- Independent plan documents should remain independently mutable.
- Lock sentinels must stay outside the tracked document corpus.
- Dry-run is a point-in-time preview and must not claim a reservation.
- Existing atomic-write, identifier-integrity, and verification guarantees remain
  mandatory and complementary.

## Considered options

1. **Shared per-document plan transaction.** One plan-layer owner serializes the whole
   read-modify-write lifecycle for CLI and MCP. Narrow concurrency and one enforceable
   contract; requires refactoring callers onto a callback-shaped core.
1. **Docs-domain transaction.** Correctly prevents lost updates but serializes mutations
   to unrelated plans and conflates single-document edits with multi-document rename
   transactions. Rejected as broader than the invariant requires.
1. **Locks in each presentation handler.** Smaller initial diff, but duplicates lock
   lifecycle across every container verb and MCP, making omission and drift likely.
   Rejected because the issue is an ownership gap.
1. **Optimistic hash refusal only.** Detects contention after callers supply revision
   state but turns ordinary local writers into a retry protocol. Retained for remote or
   long-lived clients, rejected as the primary plan-verb contract.
1. **Post-write verification only.** Already present; it cannot detect a valid later
   replacement. Rejected as incomplete.

## Constraints

- Use the existing cross-platform `advisory_lock`; add no dependency.
- Reuse the ignored per-document lock-target convention and create its parent only for
  applying mutations, not previews.
- Preserve existing CLI text/JSON and MCP result schemas.
- Preserve canonical identifier allocation, retired-ID guards, body preservation,
  atomic replacement, modified stamps, and graph-cache invalidation.
- Coordinate lock ordering with docs-domain transactions: domain lock first, then
  document lock, as established by `2026-06-27-rename-convergence-adr`.
- The parent locking, serializer, and rename primitives are accepted and covered by
  existing tests; no unstable dependency blocks implementation.

## Implementation

We will introduce a shared plan mutation transaction in the plan/core boundary. It will
derive the target document's ignored sentinel, materialize the runtime lock directory
for apply, acquire the per-document lock, then load and parse the current bytes before
invoking a typed mutation callback. Serialization guards, atomic replacement,
post-write verification, and cache invalidation remain inside the locked lifetime.

CLI step, phase, wave, epic, and tier mutations and MCP plan edits will delegate their
state transition to this owner while retaining presentation-specific messages and
envelopes. Dry runs will evaluate a current snapshot without materializing runtime
state and will remain explicitly non-reserving. Real cross-process regression coverage
will prove two concurrent production mutations to one plan both survive with distinct
canonical identifiers (`2026-08-13-plan-mutation-concurrency-reference`).

## Rationale

The shared per-document transaction is the only option that both closes the entire
lost-update window and makes the invariant structurally difficult to bypass without
freezing unrelated documents. It directly reuses the project's established edit-engine
lock granularity and rename-engine ordering rather than inventing a parallel mechanism
(`2026-08-13-plan-mutation-concurrency-research`).

## Consequences

- Concurrent VaultSpec writers targeting one plan serialize and preserve both changes.
- Mutations to different plans remain concurrent.
- CLI and MCP share one persistence invariant while keeping their public schemas.
- Apply may block behind another writer; on Windows the existing lock retries until it
  acquires rather than returning a spurious deadlock error.
- External tools that ignore the sentinel can still race; atomic replacement and
  post-write verification remain the fail-loud backstops.
- Dry-run output can become stale immediately after the command exits and does not
  reserve an identifier.
