---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S06'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add the --mode option to cmd_install accepting tool and dependency values and thread it through to install_run

## Scope

- `src/vaultspec_core/cli/root.py`
- `src/vaultspec_core/core/commands.py`

## Description

- Import `InstallMode` into `cli/root.py` and add a `--mode` typer option to
  `cmd_install`, typed as `InstallMode | None` so typer accepts exactly the
  `tool` and `dependency` values and auto-detects when omitted.
- Forward the resolved `mode` into the `install_run` call.
- Add a `mode` parameter to `install_run`, resolve the provisioning mode once at
  provision time (explicit request wins, default tool), and persist it in both
  the fresh-install and upgrade write paths.
- Add the `_persist_resolved_mode` helper that writes the committed
  `.vaultspec/workspace.json` declaration, preserves any existing floor
  constraint, and echoes the resolved mode and floor into the manifest.

## Outcome

The `install --mode tool|dependency` flag now flows through to `install_run`,
which persists the resolved mode to the committed workspace declaration and
mirrors it into the gitignored manifest. A smoke install writes
`install_mode: tool` to `workspace.json` and `resolved_mode: tool` to
`providers.json`. The Q5 precedence chain, pyproject detection, and conflict
refusal are layered onto this resolution in the following steps. Ruff and ty are
clean on both touched modules; the workspace-mode, ambiguous-states, and
manifest test suites pass (48 tests).

## Notes

The resolution here is intentionally trivial (explicit-or-default-tool); the
full precedence chain and loud refusal are wired in `S07` and `S08`. The
`_persist_resolved_mode` helper is introduced here and reused unchanged by the
later resolution wiring. `write_workspace_declaration` takes its own advisory
lock, so the helper is called outside the manifest lock and only mutates the
manifest dataclass in place for the caller to persist.
