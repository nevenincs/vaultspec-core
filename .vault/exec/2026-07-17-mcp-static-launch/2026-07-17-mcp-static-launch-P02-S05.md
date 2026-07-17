---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Recognize the legacy bare uv run module launch as DEPENDENCY in the observed-shape matcher with a drift hint pointing at sync --force or install --upgrade

## Scope

- `src/vaultspec_core/core/diagnosis/collectors.py`

## Description

- Add a module-level `_legacy_dependency_args` helper that derives the
  pre-`--no-sync` dependency launch shape from the current renderer's args
  (the current args minus `--no-sync`), bounded to that one historical shape.
- Extend `_observed_mcp_mode`'s matching loop with a final legacy-shape check:
  `command == "uv"` and `args` equal to the derived legacy args maps to
  `InstallMode.DEPENDENCY`.
- Update the docstrings of both functions to state the legacy recognition and
  confirm the existing mismatch fix hint already points at
  `spec mcps sync --force` / `install --upgrade`, so no new signal type or
  hint text is introduced.

## Outcome

Deployed workspaces still carrying the pre-amendment `uv run python -m <module>` dependency launch (no `--no-sync`) are now inferred as
`InstallMode.DEPENDENCY` instead of `None`, so mode inference and the
mode-mismatch signal keep working through the migration window; the byte
difference against the current renderer surfaces as ordinary drift with the
pre-existing fix hint. Ruff, ruff format, and ty all pass on the changed file.

## Notes

None.
