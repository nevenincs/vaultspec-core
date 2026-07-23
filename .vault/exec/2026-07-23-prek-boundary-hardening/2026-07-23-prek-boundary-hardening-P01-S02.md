---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S02'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# verify prek's TOML schema for local system hooks, confirm the delimited managed-block rendering shape is expressible in it (falling back to a round-trip TOML writer decision only if it is not), and record the schema in the same reference document

## Scope

- `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`

## Description

- Emit prek sample-config --format toml to capture the canonical TOML shape
- Validate the full vaultspec canonical hook field set (id, name, entry, types, always_run, language, pass_filenames) as repos/repos.hooks array-of-tables via prek validate-config and prek list
- Record the verified schema and the managed-block viability finding in the feature reference document

## Outcome

Verified: local system hooks render as nested array-of-tables and the whole vaultspec hook set is expressible as a self-contained block appendable at EOF, so no round-trip TOML writer is needed; tomllib covers the read side.

Files: `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`

## Notes

Fallback decision (round-trip TOML writer) not needed; managed-block rendering confirmed viable.
