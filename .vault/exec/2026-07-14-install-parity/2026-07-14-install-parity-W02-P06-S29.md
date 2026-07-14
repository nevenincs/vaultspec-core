---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S29'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a --mode tool|dependency|dev option to handle_install and forward it to install_run

## Scope

- `src/vaultspec_rag/cli/_install.py`

## Description

- Add a `--mode tool|dependency|dev` option to `handle_install` in
  `src/vaultspec_rag/cli/_install.py`, typed as core's `InstallMode` enum and
  defaulting to `None`.
- Copy core's `cmd_install` `--mode` help text verbatim so the two CLIs read
  identically for the P07 side-by-side parity review.
- Forward the resolved flag to `install_run` through the new `mode` keyword.

## Outcome

Rag's `install --help` now surfaces the same three-placement vocabulary
(`tool` / `dependency` / `dev`) as vaultspec-core, with byte-identical help
text. The flag is a thin pass-through; resolution, refusal, and the advisory
land downstream in `install_run`.

## Notes

Refusal for impossible combinations (dependency or dev mode with no
`pyproject.toml`) is raised inside core's resolver and surfaces at the CLI edge
through the existing `except Exception` install-failure handler; no new
error-handling branch was needed here.
