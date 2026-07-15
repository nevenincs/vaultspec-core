---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S08'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Add isolated Codex and Claude CLI acceptance and update MCP operator guidance

## Scope

- `tests/cli/test_mcp_hosts.py and docs/MCP.md`

## Description

- Exercise project, user, and local enrollment through installed Claude Code and Codex CLI binaries with isolated host state.
- Verify provider-owned Claude approval and Codex trust behavior without claiming runtime connectivity.
- Reject unsupported Codex local scope without falling back to or mutating user configuration.
- Correct Claude local project-key rendering for Windows paths.
- Document canonical definitions, provider-native targets, ownership, scope support, force, prune, dry-run, uninstall, and the `vaultspec-rag[mcp]` tool spec.
- Keep MCP mutation commands outside the MCP gateway catalogue.

## Outcome

Claude Code 2.1.210 and Codex CLI 0.144.4 passed all three real-host acceptance tests. Both hosts recognized isolated project and user enrollment. Claude recognized local enrollment after Core normalized its `~/.claude.json` project key to the host's forward-slash absolute-path convention; Codex local scope failed explicitly and left user configuration untouched. Claude reported its native pending-approval state for project enrollment, while the isolated Codex project used the host's trust configuration. The generated CLI reference, operator guide, Ruff, Ty, and MCP gateway catalogue tests pass.

## Notes

Enrollment status is deliberately configuration-only. Host approval, trust, executable availability, and server process health remain provider-owned runtime concerns.
