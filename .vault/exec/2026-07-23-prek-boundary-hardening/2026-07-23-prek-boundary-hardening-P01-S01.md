---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S01'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# verify prek's config-discovery behavior when prek.toml and .pre-commit-config.yaml are both present (hard error vs warn vs silent precedence) against the current prek release, and record the observed contract in a reference document scaffolded through the owning verb

## Scope

- `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`

## Description

- Probe prek 0.4.10 (uvx, build b45e67100) in throwaway git repos
- Run prek list with only prek.toml, then with a co-present .pre-commit-config.yaml carrying a distinct local hook
- Record the observed contract in the feature reference document

## Outcome

Verified: with both configs present, prek resolves hooks exclusively from prek.toml, silently ignores the YAML (no warning, no error, exit 0). The exclusive-read assumption holds; a superseded YAML is untidy, not breaking, so advisory cleanup suffices.

Files: `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`

## Notes

Executed together with the schema probe of the sibling Step; both landed in one verification session and one reference document.
