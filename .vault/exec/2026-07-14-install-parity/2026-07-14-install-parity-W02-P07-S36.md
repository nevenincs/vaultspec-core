---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S36'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Document the --mode flag, the three provisioning modes, and the shared per-package workspace.json declaration in the installation guide

## Scope

- `docs/installation.md`

## Description

- Add a `Choose a provisioning mode` section to the installation guide covering
  the `--mode` flag and the three placements: `tool` (standalone, launched
  through `uvx`, the default), `dependency` (a runtime project dependency
  launched through `uv run`, ships in published distributions), and `dev` (the
  default development dependency group, launched like `dependency` but recorded as
  development-only).
- Document the no-flag detection path: a runtime dependency resolves to
  `dependency`, a default dev-group entry to `dev`, everything else to the `tool`
  default; an explicit `dependency` or `dev` with no project config is refused
  rather than guessed.
- Document the shared per-package `workspace.json` declaration and that each
  package records its own mode there, so a mixed workspace keeps both choices
  side by side; document that `--mode` and `--local-only` are independent axes.
- Extend the verify section to describe the `server doctor` provisioning block
  that names the declared mode, whether the deployed server matches it, and
  whether the running core meets the declared floor, with the warning-versus-error
  weighting and the re-run remedy.

## Outcome

The installation guide now explains the provisioning-mode choice in connected,
usage-focused prose with no em dashes and no internal or dev metadata. `mdformat`
and `pymarkdown` are clean on the file. Committed to the `vaultspec-rag`
repository on `feature/install-parity`.

## Notes

The markdown commit surfaced the double-commit prek gotcha: the `vault check all --fix` hook (which runs on any markdown-staged commit) bumps `modified:` stamps
across pre-existing drifted vault documents from several unrelated features,
failing the commit with "files were modified by this hook". The vault-stamp
normalization was committed separately as a `chore(vault)` commit so the doc
commit could land clean.
