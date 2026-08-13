---
tags:
  - '#exec'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:82f52e57631c8f428989a78f90151b1ed16a399ac1cc61cbcacccd038257e6df'
step_id: 'S04'
related:
  - "[[2026-08-13-plan-mutation-concurrency-plan]]"
---

# Run strict ratchets, remediate review findings, and complete PR and issue delivery

## Scope

- `repository quality gates and GitHub pull request`

## Description

- Upgrade the lockfile and synchronize every dependency group.
- Add the current NetworkX stub distribution and align deserialization narrowing so
  latest Ty and strict BasedPyright agree without pins or suppressions.
- Fix workspace-hint locality drift exposed by the broad suite.
- Audit the complete concurrency change and record a PASS with no findings.
- Run the configured lint, broad, repair, harness, repository-health, and vault gates.

## Outcome

The implementation and codebase drift fixes are complete. Repository-wide strict
typing reports zero errors and zero warnings. The broad package suite passes 3,629
tests; repair, harness, and repository-health lanes pass. PR publication, hosted CI,
merge, and issue closure remain the delivery tail of this step.

## Notes

An initial attempt to constrain Ty was reverted before delivery. The authoritative
environment was rebuilt with `uv lock --upgrade` and `uv sync --all-groups --upgrade`.
The first broad run exposed one deterministic workspace discovery failure; production
resolver ordering was corrected and the complete broad lane then passed.
