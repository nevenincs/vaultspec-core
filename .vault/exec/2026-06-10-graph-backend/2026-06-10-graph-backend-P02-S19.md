---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S19
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# regenerate the bundled CLI reference and propagate provider sync

## Scope

- `.vaultspec/rules/reference/cli.md`

## Description

- Run the reference generator authoritatively: it reports both references
  already up to date because the vault-graph flag step already regenerated and
  propagated them.
- Run the full sync: every provider target is up to date, no artifacts change.
- Confirm the generator `--check` exits zero with no drift on either the
  bundled reference or the human-facing CLI doc.

## Outcome

The bundled CLI reference and human-facing doc are authoritatively in sync with
the live Typer surface: the generator regen is a clean no-op, sync reports all
targets unchanged, and `--check` exits zero. No residual provider-artifact
propagation remained to commit.

## Notes

This step was a no-op confirmation because the vault-graph flag step already
ran the generator, applied the install upgrade, and synced the references in
the same commit that introduced the flags. The closing pass verifies no drift
slipped in afterwards.
