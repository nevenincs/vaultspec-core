---
tags:
  - '#plan'
  - '#mcp-testing'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:a3608b722a90ecd0a0ca02e89917398592a0db0190c98e9e73d9d10ebb0dc76a'
tier: L2
related:
  - '[[2026-02-22-mcp-testing-adr]]'
  - '[[2026-02-22-mcp-testing-research]]'
---

# `mcp-testing` plan

### Phase `P01` - Session fixtures and transport

Establish in-memory MCP client-session fixtures over the stdio/in-process transport for protocol-level testing.

- [x] `P01.S01` - build client-session fixtures over the in-memory MCP transport; `src/vaultspec_core/mcp_server/tests/conftest.py`.

### Phase `P02` - Protocol handshake and catalog discovery

Verify session initialization, capability negotiation, and tool/catalog discovery over the wire.

- [x] `P02.S02` - cover session handshake and tool catalog discovery; `src/vaultspec_core/mcp_server/tests/test_catalog.py`.
- [x] `P02.S03` - cover tool-surface parity between the registry and the live server; `src/vaultspec_core/mcp_server/tests/test_tool_surface.py`.

### Phase `P03` - Hot-tool round-trip coverage

Exercise the nine hot-path MCP tools end-to-end through a live client session.

- [x] `P03.S04` - round-trip the orientation, discovery, and plan hot tools through a live session; `src/vaultspec_core/mcp_server/tests/test_orientation_tools.py`.
- [x] `P03.S05` - round-trip the create, edit, and find hot tools through a live session; `src/vaultspec_core/mcp_server/tests/test_create_tool.py`.
- [x] `P03.S06` - round-trip the discover/invoke gateway tools through a live session; `src/vaultspec_core/mcp_server/tests/test_gateway.py`.

### Phase `P04` - Error propagation and concurrency

Verify error surfaces for invalid calls and safety under concurrent and isolated sessions.

- [x] `P04.S07` - verify concurrent and isolated session safety, including context-budget and watchdog behavior; `src/vaultspec_core/mcp_server/tests/test_isolation.py`.
