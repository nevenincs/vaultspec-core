---
tags:
  - '#research'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:cf055abd04fa7999f18c41d8217725f7b869af20198c74d8725067e0cb05e054'
related: []
---

# `vault-exec-recovery` research: `Execution record recovery commands`

The execution-mapping validator correctly identifies malformed historical anchors but has no owning mutation surface. Evidence supports explicit, validating commands rather than a checker auto-fix: ten records have verified live Step targets, one references an explicitly retired Step, and six prose-era records cannot truthfully map to a formal Step.

## Findings

### Canonical Step IDs and display paths are intentionally distinct

`plan/parser.py` stores the canonical leaf identifier as `S##`, while plan display paths include phase and wave ancestry. `plan/commands/step_ops.py` already resolves either representation and rejects missing or ambiguous targets. In the affected RAG vault, ten execution records store a composite display path where the current validator requires the canonical leaf, and each parent plan exposes the exact live row.

### The remaining seven records need historical classification rather than a guessed relink

One record names a retired Step and must be preserved as an archived execution record. Six records describe prose-era waves whose current parent plan has no formal matching Step; removing their machine `step_id` accurately represents them as legacy-unmappable records, which the validator already skips. Neither case is a safe checker-side inference.

### Core has established atomic command and JSON patterns

`cli/plan_cmd.py` separates typed operation helpers from thin Typer wrappers, uses expected state and atomic writes, emits stable JSON envelopes, and treats dry runs and no-ops explicitly. `vault_cmd.py` owns document operations but has no `vault exec` group. A dedicated group can reuse plan target and Step-resolution helpers while preserving document body bytes and updating only machine-owned metadata.

## Sources

- `src/vaultspec_core/plan/parser.py`
- `src/vaultspec_core/plan/commands/step_ops.py`
- `src/vaultspec_core/cli/plan_cmd.py`
- `src/vaultspec_core/cli/vault_cmd.py`
- `src/vaultspec_core/vaultcore/checks/exec_mapping.py`
- `src/vaultspec_core/vaultcore/models.py`
- `2026-07-23-vault-check-validators-adr`
