---
tags:
  - '#adr'
  - '#mcp-read-only'
date: '2026-08-01'
modified: '2026-09-23'
body_schema: 'body-v1'
body_hash: 'sha256:95d8632e00a91742bb2992cc2472b058c68e8bd74eb9fed5abe86fb939cc162e'
related:
  - "[[2026-08-01-mcp-read-only-research]]"
  - "[[2026-07-09-mcp-tool-schema-adr]]"
  - '[[2026-09-23-typesafe-search-adr]]'
---

# `mcp-read-only` adr: `read-only MCP launch mode` | (**status:** `accepted`)

## Problem Statement

Orchestrated agents need the vault orientation surface without receiving any mutation capability. The accepted `mcp-tool-schema` design intentionally exposes both first-class write tools and the broadly capable `invoke` gateway; an explicit launch-time boundary is therefore required. The security and consumer requirement is grounded by `2026-08-01-mcp-read-only-research`.

## Considerations

- `2026-08-01-mcp-read-only-research` establishes that hiding a tool after it reaches the client does not satisfy the capability boundary.
- `2026-07-09-mcp-tool-schema-adr` assigns read-only semantics to orientation tools but deliberately retains mutation tools and `invoke` in the normal catalog.
- The consumer contract requires the default server surface to remain unchanged and the restricted surface to remain asserted at runtime.

## Considered options

**Client-side denylist.** Rejected: the server still advertises prohibited schemas and a client configuration error can re-expose them.

**Consumer-owned wrapper server.** Rejected: it forks the catalog and makes a consumer owner of this server's security policy.

**Server-owned `--read-only` registration mode.** Chosen: the server registers only a positively allowlisted orientation surface, so prohibited tools are absent from `tools/list` by construction.

## Constraints

- The normal launch must retain its complete existing catalog and behavior.
- Restricted mode may register only `status`, `find`, `discover`, and a validation-only `check` interface.
- Restricted `check` must neither advertise nor accept repair through `fix`.
- The mode is a stable runtime contract; no consumer version pin is required or substituted for surface assertion.
- Existing MCP bootstrap, transport, and registry ownership remain unchanged.

## Implementation

The launch parser accepts `--read-only` and passes its value to server construction. Tool registration selects a positive restricted registration set when enabled and preserves the normal set otherwise. The restricted `check` registration exposes validation only, while normal mode retains the existing repair-capable signature. Real MCP-session tests inspect advertised tool names and schemas in both modes, ensuring default parity and preventing new write tools from entering the restricted catalog accidentally.

**Amendment note, 2026-09-23**: `2026-09-23-typesafe-search-adr` adds `search` to the restricted allowlist. It mutates nothing locally; when a hosted-search credential is configured it sends vault text to the TypeSafe API, and the presence of the credential is the consent for that data flow.

## Rationale

A server-side positive allowlist is the only option that makes an unavailable capability unrepresentable to the client. It retains catalog ownership in this project, aligns with the existing tiered-tool decision, and gives consumers a small, stable surface that can be verified at connection time. `2026-08-01-mcp-read-only-research` establishes the security criterion; `2026-07-09-mcp-tool-schema-adr` supplies the current catalog classification.

## Consequences

Consumers can compose vault orientation with agent workflows without granting mutation authority. New tools are excluded from restricted mode until deliberately classified, which favors safety but creates an intentional maintenance obligation. `check --fix` remains available only to normal launches; callers needing repair must deliberately select that broader capability.
