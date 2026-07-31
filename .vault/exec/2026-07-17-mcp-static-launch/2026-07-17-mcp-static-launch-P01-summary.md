---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:ae5d4657bd96308c0a07b94bb383f4631fbcb6ba4fcbea930e7dc27ab246a08e'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# `mcp-static-launch` `P01` summary

All three recovery steps closed. The incident-corrupted environment was
restored with explicit dev actions only, the stale pre-parity rag seed was
replaced by the tokenized mode-neutral definition, rag's placement was
declared dev in the committed workspace map, and both MCP servers verified a
real stdio initialize handshake before any code changed.

- Created: feature branch and draft PR 224
- Modified: `.vaultspec/mcps/vaultspec-rag.builtin.json`, `.vaultspec/workspace.json`, `pyproject.toml`, `uv.lock`

## Description

Restore the workspace the connect-time sync incident broke and stage the
tracking surfaces. The venv was repaired with an explicit uv sync (the two
lock-holding processes had already exited), the rag re-enrollment refreshed
the exe-form seed, and the rag installer's runtime-dependency placement leak
was caught and reverted here, feeding the rag-side issue.
