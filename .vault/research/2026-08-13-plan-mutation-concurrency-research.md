---
tags:
  - '#research'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:32a3281ab80fd9cd8a7c35ff9db50e92263370560d9b0a8525ef47a5fa444724'
related:
  - "[[2026-08-13-plan-mutation-concurrency-reference]]"
  - "[[2026-06-05-plan-serializer-fixes-adr]]"
---

# `plan-mutation-concurrency` research: `concurrency-safe plan mutation`

Issue 296 asks how plan mutation verbs can prevent concurrency from turning a
successful-looking command into a lost update. Atomic replacement and post-write
verification already close partial-write and immediate silent-no-op failures, but the
load and write remain outside any common lock. The evidence favors one per-document
transaction boundary shared by CLI and MCP; the ADR must settle that ownership and the
dry-run contract.

## Findings

### Atomic replacement does not prevent a lost update

The current save helpers atomically replace the destination and verify the written
model, but both CLI and MCP load before any lock. Two mutations can therefore derive
from the same original bytes and both verify successfully in sequence while the latter
replacement loses the former. The exact boundaries and existing analogues are mapped
in `2026-08-13-plan-mutation-concurrency-reference`; the already-accepted serializer
guard remains complementary rather than sufficient (`2026-06-05-plan-serializer-fixes-adr`).

### Per-document locking is the narrowest complete boundary

The mutation touches one plan file, so the lock must begin before its read and end
after write verification. Reusing the existing ignored per-document sentinel avoids
visible sibling lock files and permits unrelated plans to mutate concurrently. A
docs-domain lock would also be correct but would unnecessarily serialize independent
documents and overlap the broader rename/archive transaction contract
(`2026-06-27-rename-convergence-adr`).

### The transaction should be shared below presentation surfaces

A lock inside the existing save helper begins too late. Per-command locking is
complete only if every present and future verb remembers the same lifecycle, and it
leaves the MCP duplicate free to drift. A shared plan-layer mutation transaction can
take a typed mutation callback, perform load and parse under the lock, apply the
callback, and delegate persistence verification; CLI and MCP retain their respective
result envelopes. This option has more refactoring cost than wrapping each handler but
establishes one enforceable owner.

### Optimistic conflict detection alone changes rather than fixes the contract

Requiring callers to provide a blob hash would detect stale writers but would make
ordinary CLI mutations fail under benign contention and require a retry protocol.
The issue concerns framework-owned verbs that can safely serialize short local
critical sections, so conflict-only behavior is weaker than preventing the lost update.
Blob hashes remain useful for remote or long-lived edit clients, as the generic edit
engine demonstrates.

### Dry runs are previews, not reservations

Holding an OS lock after a dry-run process exits is impossible without a separate
lease service. A dry run should evaluate one current snapshot, create no lock runtime
directory solely for preview, and promise no reservation. Apply must create the
ignored sentinel parent and re-read under lock. This matches the accepted point-in-time
archive preview semantics (`2026-07-31-archive-semantics-adr`).

### Verification must prove real cross-process behavior and preserve ratchets

The regression should launch real production mutation entry points against one
temporary plan and assert both independent changes persist with unique canonical IDs.
No fake, mock, stub, patch, monkeypatch, skip, xfail, or duplicated business logic is
needed. Focused concurrency coverage must be followed by the repository's strict lint,
type, test, documentation, and drift gates; a focused green run alone cannot establish
closure.

### Bounds

This research does not attempt to coordinate external editors that ignore VaultSpec's
sentinel, nor to turn dry-run into a reservation. It does not require transaction
rollback across multiple plans because each verb targets one plan. Windows process
behavior remains the primary reported environment and must be exercised directly.

## Sources

- `src/vaultspec_core/core/helpers.py:84`
- `src/vaultspec_core/core/helpers.py:325`
- `src/vaultspec_core/cli/plan_cmd_shared.py:121`
- `src/vaultspec_core/cli/plan_cmd_phase.py:54`
- `src/vaultspec_core/cli/plan_cmd_step.py:52`
- `src/vaultspec_core/mcp_server/tools/plan.py:185`
- `src/vaultspec_core/mcp_server/tools/plan.py:200`
- `src/vaultspec_core/mcp_server/tools/plan.py:464`
- `src/vaultspec_core/vaultcore/edit_engine.py:333`
- `src/vaultspec_core/vaultcore/edit_engine.py:713`
- `src/vaultspec_core/vaultcore/rename_engine.py:91`
- `src/vaultspec_core/vaultcore/rename_engine.py:153`
- `src/vaultspec_core/vaultcore/batch_archive.py:152`
- `src/vaultspec_core/tests/plan/test_write_verification.py:48`
- GitHub issue 296: `https://github.com/nevenincs/vaultspec-core/issues/296`
