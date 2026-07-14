---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S31'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Replace the static command and args with core's sentinel tokens, rendering through render_launch_for_mode with package='vaultspec-rag' and module='vaultspec_rag.server' for module-invocation exe-lock parity

## Scope

- `src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`

## Description

- Replace the static `command`/`args` in
  `src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json` with core's
  sentinel tokens.
- Add the `_vaultspec_mode_package` (`vaultspec-rag`) and
  `_vaultspec_mode_module` (`vaultspec_rag.server`) metadata keys so core's
  renderer produces rag's own `uv run` / `uvx --from` launch.

## Outcome

Core's `render_mcp_definition_for_mode` substitutes the tokens into
`uv run python -m vaultspec_rag.server` for dependency and dev modes and
`uvx --from vaultspec-rag python -m vaultspec_rag.server` for tool mode, with
the metadata keys stripped from the rendered entry. The previous launch used the
`vaultspec-search-mcp` console script; the tokenized form uses the equivalent
module invocation for exe-lock parity with core.

## Notes

`python -m vaultspec_rag.server` was verified to start the MCP server: the
`server` package already ships a `__main__` module delegating to the same
`main` the `vaultspec-search-mcp` console script binds, so no new `__main__`
guard was needed. `python -m vaultspec_rag.server --help` prints the daemon
usage and exits cleanly.
