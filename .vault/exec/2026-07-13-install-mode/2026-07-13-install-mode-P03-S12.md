---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S12'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Introduce mode placeholder tokens in the builtin MCP definition command and args fields, keeping the seeded builtin snapshot mode-neutral for drift-detection hashing

## Scope

- `src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json`

## Description

- Replace the hardcoded dependency-mode launch (`command` `uv`, `args` `run python -m ...`) with two sentinel placeholder tokens: a scalar command token and a single-element args token.
- Choose a token shape that cannot collide with any real command name or argument value so substitution is unambiguous and idempotent.
- Mirror the identical token content into the repository's own seeded copy under `.vaultspec/mcps/` so the source builtin and its seeded copy stay byte-for-byte identical.

## Outcome

The builtin MCP definition is now mode-neutral. Its `command` field holds the sentinel `@@VAULTSPEC_INSTALL_MODE_COMMAND@@` and its `args` field holds `["@@VAULTSPEC_INSTALL_MODE_ARGS@@"]`. Neither token can appear as a legitimate JSON value, so the downstream renderer can detect and substitute them without risk of matching real content. Because the seeded copy carries the same bytes, the `BuiltinVersionSignal` snapshot comparison (which hashes the seeded copy against the source builtin) sees no drift. Mode-specific substitution is deferred entirely to the collection step; the seeded artifacts never carry a mode.

## Notes

The tokens are only ever read by the collection-and-render path, never executed. A workspace's launch config (`.mcp.json`) always receives the substituted concrete command, so no MCP client ever sees a token. This repository's committed `.mcp.json` is unchanged by this step; it is regenerated with the byte-identical dependency-mode form once the renderer lands.
