---
tags:
  - '#audit'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-vault-exec-recovery-adr]]"
  - "[[2026-07-27-vault-exec-recovery-plan]]"
---

# `vault-exec-recovery` audit: `Execution recovery implementation`

## Scope

Reviewed the typed recovery helpers against the accepted recovery ADR, implementation plan, and their focused real-filesystem tests. The review covered mutation authority, parent-plan resolution, archive safety, line-ending and body preservation, and dry-run/no-op evidence.

## Findings

### parent-plan-ambiguity | high | First matching plan link gains mutation authority

`resolve_exec_parent_plan` returns the first related entry that happens to name a live parseable plan. A record carrying two live plan relations is therefore silently bound by ordering, although the ADR permits recovery only against the record's existing parent plan. Relinking, detaching, or retiring such a record can apply an operator action under the wrong plan's retired ledger or live Step set.

### related-path-escape | high | A related stem can escape the plan directory

The related-link stem is concatenated into a candidate filename without rejecting separators or proving the resolved candidate remains under the live plan directory. A crafted `[[../../...]]` relation can supply an external plan as recovery authority, defeating the vault-root confinement required for an explicit record repair.

### archive-destination-race | critical | Retirement can overwrite a concurrently created archive record

`retire_exec_record` tests that the destination is absent and then calls `os.replace`. A competing create between those operations is replaced on supported platforms, silently destroying an existing archive record. The archive move needs an exclusive no-replace destination protocol and containment checks for the archive path and its parents.

### cr-only-frontmatter | medium | Metadata mutation does not support classic-Mac line endings

The step-id replacement, removal, and insertion patterns rely on multiline anchors, which only recognize line starts after LF. A valid CR-only record accepted by the stamp helper cannot have its existing `step_id` located or its `modified` anchor found, so recovery fails despite the preservation contract covering line endings.

### recovery-boundary-coverage | medium | Focused tests omit safety and contract boundaries

The eight passing tests cover the ordinary CRLF paths, but do not prove rejection of multiple parent plans, escaped or symlinked parents and archive destinations, collision-safe retirement, CR-only records, or dry-run and no-op result contracts. Add real-filesystem regressions before exposing the helpers through the CLI.

### recovery-review-remediation | low | All review findings have verified fixes

The recovery resolver now rejects unsafe stems, symlinked inputs, and multiple live parent plans. Retirement reserves its destination with a no-replace hard link under the vault advisory lock; preview validates the same collision condition. The metadata parsing view supports CR-only records while writes retain original line endings. Seventeen focused real-file and CLI tests exercise these boundaries and pass.

## Recommendations

Retain the explicit command preconditions and strict `exec-mapping` validator. Apply only the previously verified RAG record set, then re-run `vault check exec-mapping` before treating the historical recovery as complete.

### recovery-precondition-race | critical | A stale validated context can mutate newly changed evidence

Each operation resolves and classifies the execution record before its eventual write or archive. `relink` and `detach` then read the path again and edit its current frontmatter without revalidating the claim, while `retire` takes the advisory lock only after classification. A concurrent Core edit can therefore change a dangling claim into a live claim between validation and mutation; the stale detach removes that live mapping, or stale retirement archives a record no longer tied to a retired Step. The record mutation must hold the common vault lock from read through apply and revalidate the record's immutable blob or full recovery preconditions inside that critical section.

### recovery-lock-absent-data | critical | Fresh vaults bypass the recovery critical section

The recovery context calls the shared advisory lock, but that helper deliberately yields without locking when the `.vault/data` parent does not already exist. The new threaded regression creates that directory before holding the lock, so it proves only the initialized-vault case. Two recovery processes in a fresh vault can still resolve and mutate concurrently, recreating the stale-precondition race. Ensure the common lock parent exists before any non-dry-run recovery resolution, or make the shared lock establish its parent with an explicitly safe dry-run policy, and add the same competing-mutation regression without pre-creating `.vault/data`.

### recovery-lock-remediation | low | Final review verified the recovery critical section

Applying recovery now creates the standard vault runtime lock directory, then takes the shared document lock before it resolves, classifies, and mutates a record. The real threaded regression begins with no runtime directory, proves the lock is established, blocks a competing recovery, and preserves a newly live mapping. Final independent review found no remaining release blocker; all eighteen focused real-file and CLI tests pass.
