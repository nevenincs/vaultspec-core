---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Add warn-only doctor advisories for unrefreshable prek.toml hooks and stale static companion seeds with remediation hints

## Scope

- `src/vaultspec_core/core/diagnosis`

## Description

- Add the UNREFRESHABLE precommit signal: with prek.toml present and the
  YAML hook set not canonical, the doctor names the manual-transplant
  remediation instead of the false install --upgrade hint.
- Add the stale-seed collector and doctor row: package-bundled builtin MCP
  definitions still in a static pre-mode shape are reported with the
  owning-installer remediation.
- Wire both through the diagnosis dataclass and the doctor renderer.

## Outcome

The two convergence holes core cannot fix itself are now visible in the
surface operators read, each with an honest remediation.

## Notes

Deliberate exit-code policy: both advisories render as warnings but do not
fail the doctor. Their remediation lives outside the workspace, and a
failing doctor blocks every markdown commit via the bundled spec-check
hook with no in-workspace remedy - the wedge class the provider-dir
host-native-file fix already closed once. For prek.toml workspaces this
strictly improves on the previous behavior, which failed the doctor with a
remediation that could not work.
