---
tags:
  - '#research'
  - '#mcp-read-only'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:4a708c953d339b627a5d3d229390791d265e7685af294785aba0ab1f775bfa1d'
related:
  - "[[2026-07-09-mcp-tool-schema-adr]]"
  - "[[2026-07-09-mcp-tool-schema-reference]]"
---

# `mcp-read-only` research: capability-scoped MCP launch

Issue #300 asks whether `vaultspec-mcp` can provide vault grounding to orchestrated agents without exposing a mutation capability. The evidence supports a server-owned launch mode that omits mutation tools from `tools/list`; the remaining design question for an ADR is the exact treatment of `check`, whose normal `fix` option writes to the vault.

## Findings

### The advertised tool catalog is the relevant security boundary

Issue #300 records an observed containment failure in which a write-capable server, reachable through user-global configuration, scaffolded real vault documents despite a filesystem deny. A client-side permission filter therefore does not meet the stated requirement: models must not receive the schema of capabilities they are prohibited from using. The existing accepted MCP-schema decision defines both first-class mutation tools and a broadly capable `invoke` gateway, so tool annotations alone cannot remove those capabilities from discovery. The ADR must decide a launch-time registration boundary rather than a client-side denylist. https://github.com/nevenincs/vaultspec-core/issues/300 `.vault/adr/2026-07-09-mcp-tool-schema-adr.md`

### The read-only catalog is deliberately small and should be allowlisted

The issue names `status`, `find`, and `discover` as orientation-only operations, and proposes validation through `check`; it expressly excludes `create`, `edit`, `plan_progress`, `plan_edit`, and `invoke`. The accepted schema ADR independently marks `status`, `find`, and `discover` read-only and idempotent, while `invoke` is destructive because it reaches the long-tail command catalog. A positive allowlist means a future mutating tool remains absent until it is deliberately classified, rather than becoming visible by default. `.vault/adr/2026-07-09-mcp-tool-schema-adr.md` https://github.com/nevenincs/vaultspec-core/issues/300

### `check` needs a read-only signature, not only a safe default

The accepted schema ADR describes `check` as read-only only when `fix` is false; `fix` makes it mutating. A server that advertises the usual `check(fix: bool)` handler under `--read-only` would still offer a write path and its schema to the client. The read-only mode therefore needs a check registration that neither advertises nor accepts `fix`, while the normal launch retains the complete handler unchanged. This is the one interface refinement the ADR must make explicit. `.vault/adr/2026-07-09-mcp-tool-schema-adr.md` https://github.com/nevenincs/vaultspec-core/issues/300

### The default server interface is a compatibility requirement

The issue requires the flag to be a stable consumer contract and requires default launch behavior to remain unchanged. The existing static-launch decision retains `app.py` bootstrap and the console script as the MCP entry point, so the new option should be parsed at that existing boundary and passed into tool registration. Tests must inspect a real server's advertised list for both modes, asserting exact read-only membership and default equivalence; unit tests of a hand-maintained name list alone would not prove the wire-visible contract. `.vault/reference/2026-07-09-mcp-tool-schema-reference.md` `.vault/adr/2026-07-17-mcp-static-launch-adr.md` https://github.com/nevenincs/vaultspec-core/issues/300

## Sources

- https://github.com/nevenincs/vaultspec-core/issues/300
- `.vault/adr/2026-07-09-mcp-tool-schema-adr.md`
- `.vault/reference/2026-07-09-mcp-tool-schema-reference.md`
- `.vault/adr/2026-07-17-mcp-static-launch-adr.md`
