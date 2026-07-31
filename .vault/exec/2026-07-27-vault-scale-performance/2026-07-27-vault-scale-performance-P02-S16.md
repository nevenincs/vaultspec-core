---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:9e93d2a523eb1cd90a57afa621e32bead0e5e99c0d0b89337fb10c3845626a87'
step_id: 'S16'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# add the single-ingress enforcement test that fails any check touching disk after ingress

## Scope

- `src/vaultspec_core/vaultcore/checks/tests/test_single_ingress.py`

## Description

- Add the enforcement test that deletes the corpus after ingress and
  asserts the calculate phase reproduces its baseline diagnostics
  exactly, plus an encoding-facts survival case.

## Outcome

Both tests pass; the scale gate's read budget independently
corroborates the one-read-per-document contract.

## Notes

Archive probes and workspace-resource reads are outside the scanned
corpus by design and unaffected by the lockdown.
