---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# `mcp-static-launch` `P03` summary

All three closing steps done. The static-execution contract is stated in
the MCP doc and the CLI reference, the rag-side half of the contract is
tracked as rag issue 231, and the full gate set ran green: 1778 unit tests
(CI-matching gate), 321 repo-root tests, ruff, ty (changed files clean;
nine pre-existing baseline diagnostics untouched), prek hooks on every
commit, and a live dogfood of the re-rendered provider configs with real
stdio handshakes.

- Modified: `docs/MCP.md`, `docs/CLI.md`, `src/vaultspec_core/builtins/reference/cli.md`
- Created: `.vault/audit/2026-07-17-mcp-static-launch-audit.md`, rag issue 231

## Description

Close the feature: document the contract users rely on, hand the sibling
its bounded work without release-coupling core to it, and prove the whole
set with the CI-matching gates plus over-the-wire verification of the
deployed launch commands.
