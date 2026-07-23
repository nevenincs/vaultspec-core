---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S11'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add the operator-invoked migration verb under a new spec precommit command group (avoiding the taken spec hooks namespace): transplant canonical hooks into prek.toml, idempotent when hooks are already present, previewable with --dry-run, never deleting the YAML on its own

## Scope

- `src/vaultspec_core/cli/spec_cmd.py`

## Description

- Implement migrate_hooks_to_prek: idempotent transplant with managed-block replace-or-append, refusal states no_prek_config / unparseable / conflicting, dry-run preview
- Add the spec precommit command group with the migrate verb (--dry-run, --remove-yaml, --json), exit 0 on migrated/unchanged and 1 on refusals

## Outcome

Verified end-to-end against prek 0.4.10: migrated config validates via prek validate-config and all hooks resolve via prek list. Files: `src/vaultspec_core/core/prek_boundary.py`, `src/vaultspec_core/cli/spec_cmd.py`
