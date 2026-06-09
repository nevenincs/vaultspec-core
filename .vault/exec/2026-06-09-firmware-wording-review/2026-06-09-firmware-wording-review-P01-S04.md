---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
step_id: S04
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# correct the Verify-phase artifact cell from the exec review path to the canonical audit address .vault/audit/yyyy-mm-dd-feature-audit.md (D2)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Change the pipeline-table Verify artifact cell in `src/vaultspec_core/builtins/system/03-vaultspec.md` from the exec review path to the abbreviated canonical audit address, matching the column style of the sibling rows
- Run mdformat on the edited file

## Outcome

The Verify phase now points at the audit directory (full canonical address `.vault/audit/yyyy-mm-dd-{feature}-audit.md`), implementing ADR decision D2. Table layout intact; the abbreviated cell form matches every other Artifact cell in the table.

## Notes

None.
