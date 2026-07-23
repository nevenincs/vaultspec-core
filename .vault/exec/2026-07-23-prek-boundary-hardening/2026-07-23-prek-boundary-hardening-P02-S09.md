---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S09'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add real-filesystem tests proving the predicate-routed scaffold short-circuit and uninstall behavior remain unchanged for existing prek workspaces

## Scope

- `src/vaultspec_core/tests/cli/test_flow_bugs.py`

## Description

- Extend TestPrekShortCircuit with the healthy-prek variant: hooks already in prek.toml short-circuit with info, never the stranded warning
- Add TestUninstallUnderPrek: full install, then prek.toml adoption, then forced uninstall still strips vaultspec hook residue from the YAML

## Outcome

Files: `src/vaultspec_core/tests/cli/test_flow_bugs.py`
