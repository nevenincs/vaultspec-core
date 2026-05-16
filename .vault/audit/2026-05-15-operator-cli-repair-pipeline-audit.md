---
tags:
  - '#audit'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-research]]'
---

# `operator-cli-repair-pipeline` audit: `current codebase status and risks`

## Scope

Audit of the current vault-content CLI recovery surface after direct operator
feedback. Scope includes `vaultspec-core vault check all`,
`vaultspec-core vault check all --fix`, `vaultspec-core vault feature index`,
the current check runner, generated index lifecycle, migration boundary, output
contract, and Windows/path handling risks.

## Findings

### High severity: repair pipeline state can go stale inside one run

`src/vaultspec_core/vaultcore/checks/__init__.py` builds one `VaultGraph` and
one snapshot, then dispatches all checks. When `fix=True`, early checks may
rename or rewrite files while later checks still consult pre-fix graph state.
This makes a second pass operationally likely and should be surfaced or
designed away in a repair pipeline.

### High severity: case-only path repair is under-specified

`src/vaultspec_core/vaultcore/resolve.py` lowercases stem lookup keys, while
`src/vaultspec_core/vaultcore/checks/structure.py` performs exact and
lowercase rewrite lookups. That mixed model is useful but not enough for
Windows and case-insensitive Git worktrees. Case-only rename behavior needs an
explicit transaction strategy and tests.

### Medium severity: `--fix` is partial but sounds global

`src/vaultspec_core/cli/vault_cmd.py` rejects `--fix` for unsupported
individual checks, while `check all --fix` quietly applies only supported
mutations. Operators need a per-check mutation summary and a manual-work
bucket.

### Medium severity: generated indexes are outside the repair loop

`src/vaultspec_core/vaultcore/index.py` generates feature indexes, while
`src/vaultspec_core/migrations/m_0_1_17_index_subfolder.py` owns index
relocation. This separation is correct, but the CLI does not connect it to
repair guidance. Operators are left to know when to run
`vaultspec-core vault feature index`.

### Medium severity: output is accurate but not root-cause oriented

`src/vaultspec_core/cli/vault_cmd.py` renders check totals and individual
diagnostics, but it does not group symptoms by root cause, show phase results,
list changed files, or identify mandatory follow-up commands.

### Low severity: historical docs can mislead implementation planning

Existing doctor-suite docs are useful as precedent, but their older module
names and command assumptions should not be copied directly into the current
codebase.

## Recommendations

Create a dedicated vault repair pipeline that keeps diagnostics, mechanical
fixes, generated artifact refreshes, and authorial gaps distinct.

The design should:

- Run a preflight phase and report lazy migration status.
- Plan safe mechanical fixes before applying them.
- Use platform-aware rename primitives for case-only changes.
- Rebuild or explicitly queue generated indexes after link-relevant mutations.
- Reconstruct graph/snapshot state after mutation.
- Emit human output grouped by root cause and JSON output grouped by phase.
- Separate manual traceability work from mechanical repairs.
- Add real-behavior tests for Windows/path assumptions, index lifecycle,
  post-fix validation, and output language.
