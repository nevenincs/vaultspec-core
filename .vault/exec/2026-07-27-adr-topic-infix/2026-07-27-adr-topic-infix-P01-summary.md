---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:d04e26b81c2dae8d4756edf4a20d0507e7d24f84c360a8ed20516b115dd15d0a'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# `adr-topic-infix` `P01` summary

The shared creator, CLI, and MCP now converge on ADR, audit, reference, and research
as the topic-infix types. Plan and exec behavior remains excluded and unchanged.

- Modified: `src/vaultspec_core/vaultcore/hydration.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

Completed P01.S01 through P01.S03. Each transport keeps its existing validation and
delegates filename construction to the shared creator.
