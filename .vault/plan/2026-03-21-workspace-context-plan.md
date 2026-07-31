---
tags:
  - '#plan'
  - '#workspace-context'
date: '2026-03-21'
modified: '2026-07-31'
body_hash: 'sha256:dca6652e9ff86338bfa589eef9cd615566ac7a937639fa355bf3e00484624c8b'
tier: L2
related:
  - '[[2026-03-21-workspace-context-adr]]'
  - '[[2026-03-21-workspace-context-research]]'
---

# workspace-context plan

## Steps

### Phase `P01` - define WorkspaceContext

replace the 9 mutable globals with a frozen context object backed by a ContextVar

- [x] `P01.S01` - add the frozen WorkspaceContext dataclass, the module-level ContextVar, and the get_context accessor, then delete the 9 bare globals; `src/vaultspec_core/core/types.py`.

### Phase `P02` - migrate consumers to the context accessor

move every caller off the bare globals and onto get_context()

- [x] `P02.S02` - replace every direct global reference with get_context() across all source files and test fixtures; `src/vaultspec_core`.

### Phase `P03` - eliminate swap-and-restore in sync_provider

replace the swap-and-restore race with an isolated context snapshot per call

- [x] `P03.S03` - replace the swap-and-restore pattern in sync_provider with contextvars.copy_context().run(...); `src/vaultspec_core/core/provider_sync.py`.

### Phase `P04` - fix \_ensure_tool_configs and entry points

stop touching real workspace paths for tool-config resolution and assign context at every entry point

- [x] `P04.S04` - use a temp directory instead of the real workspace in \_ensure_tool_configs and set context via init_paths at every entry point; `src/vaultspec_core/core/commands.py`.

### Phase `P05` - per-request context isolation in the MCP handler

give every MCP request its own isolated context snapshot

- [x] `P05.S05` - wrap each MCP request handler invocation in contextvars.copy_context().run(...) for per-request isolation; `src/vaultspec_core/mcp_server/isolation.py`.
