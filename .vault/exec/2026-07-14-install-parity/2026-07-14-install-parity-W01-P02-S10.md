---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S10'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Accept dev as a valid --mode token for cmd_install and update its help text to document all three provisioning modes

## Scope

- `src/vaultspec_core/cli/root.py`

## Description

- Update the `cmd_install` `--mode` help text to document all three provisioning modes, naming the DEV mode as the default dev dependency group that renders like dependency but does not ship in built distributions.

## Outcome

The `--mode` option now advertises `tool|dependency|dev` in its metavar (already accepted, since the typed `InstallMode` enum gained DEV in P01) and its help text spells out the leak distinction the three modes encode: tool launches via uvx and never enters the project's dependencies, dependency is a runtime project dependency that ships downstream, and dev is the default dev group that renders identically to dependency but does not leak into built distributions. No token-parsing change was needed because typer derives the accepted values from the enum; only the operator-facing help required updating. Scoped `ruff` and `ty` clean; 18 install-flow unit tests pass and the rendered `--help` confirms the three-token metavar and the new wording.

## Notes

None.
