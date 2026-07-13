---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S15
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add node, depth, and derived-edge toggles to the vault graph verb

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add `--node`, `--depth`, and a `--derived/--no-derived` toggle to the vault
  graph verb, threading them into the JSON `to_dict` call for ego scoping and
  derived-edge inclusion.
- Refuse an unknown `--node` stem in JSON mode with exit code 1 and a `failed`
  envelope carrying the message, reusing the canonical json envelope helper at
  schema version 2.
- Document the three flags and the v2 payload shape in the hand-authored
  option tables of the bundled reference and the human-facing CLI doc, outside
  the generator-managed markers.
- Run the reference generator (no managed-region drift), apply
  `install --upgrade` to refresh the installed bundled reference, and sync to
  propagate provider artifacts.

## Outcome

The vault graph verb now exposes ego scoping and the derived-edge toggle in
JSON mode; help text lists all three flags. The generator `--check` reports
both references in sync, and a missing node fails loudly with exit 1. The 95
graph and vault-CLI tests pass; ruff and ruff-format are clean.

## Notes

The reference generator reported no managed-region drift because the
command-inventory region is coarser than per-option granularity; the new flags
are documented in the hand-authored `vault graph` option tables outside the
markers, per the generated-reference-is-CLI-owned discipline. The installed
`.vaultspec/rules/reference/cli.md` is gitignored under this repo's older
install policy, so the tracked reference changes are the bundled builtin source
and the human-facing CLI doc.
