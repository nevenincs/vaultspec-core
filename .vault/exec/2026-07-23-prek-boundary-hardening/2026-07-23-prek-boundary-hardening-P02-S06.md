---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S06'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# reshape the doctor precommit row and advisory text for the content-aware states - UNREFRESHABLE says hooks are stranded and names the migration verb, ORPHANED renders as benign info advising superseded-YAML removal - and update every status mapping carrying PrecommitSignal members

## Scope

- `src/vaultspec_core/cli/spec_cmd.py`

## Description

- Reshape the doctor precommit row: UNREFRESHABLE names spec precommit migrate; new ORPHANED row renders as benign dim info advising superseded-YAML removal via the gated flag
- Add UNREFRESHABLE to the doctor warning set: content-verified genuine stranding is now warn-level (the prior warn-only exemption predated content awareness and the in-workspace remediation)

## Outcome

Files: `src/vaultspec_core/cli/spec_cmd.py`

## Notes

The doctor exit-code semantics for UNREFRESHABLE changed from ignored to warning; the repo gate is unaffected because the canonical hook runs spec doctor --gate-errors.
