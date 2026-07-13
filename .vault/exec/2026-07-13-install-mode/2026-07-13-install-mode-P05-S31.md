---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S31'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Regenerate the CLI reference so the install --mode option and its help text appear in the generator-managed reference

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Run `spec reference generate`; the generator-owned command-inventory marker
  block was already in sync, since the install command inventory line carries no
  per-flag detail.
- Add the `--mode` option to the install command's hand-authored option list in
  the bundled reference and in the repo-facing reference, using the flag's own
  CLI help text (tool default via uvx, dependency via the project venv,
  auto-detected from pyproject.toml).
- Reflow both reference files through mdformat --wrap 88 and confirm
  `spec reference generate --check` reports both in sync.

## Outcome

Both `docs/CLI.md` and the bundled `cli.md` now document `install --mode` with
its default and behaviour, and the generator check passes because only the
hand-authored option regions outside the marker block were touched.

## Notes

The per-command option tables in the CLI reference are hand-authored regions,
not part of the single generator-owned command-inventory marker block, so the
generator alone does not surface a new flag there; the `--mode` row was added by
hand to the option lists (never inside the marker block) using the verb's own
help string as the source of truth.
