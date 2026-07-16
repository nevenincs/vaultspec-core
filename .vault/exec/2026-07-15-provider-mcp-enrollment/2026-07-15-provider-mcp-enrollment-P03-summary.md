---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# `provider-mcp-enrollment` `P03` summary

Phase P03 proves provider-native enrollment through real reconciliation, installed host
CLIs, and the corrective atomic-writer release gate.

- Modified: `tests/test_mcps.py`
- Modified: `tests/test_commands.py`
- Modified: `tests/cli/test_mcp_hosts.py`
- Modified: `docs/MCP.md`
- Modified: `src/vaultspec_core/core/helpers.py`
- Modified: `src/vaultspec_core/core/gitignore.py`
- Modified: `src/vaultspec_core/core/gitattributes.py`
- Modified: `src/vaultspec_core/core/tests/test_resource_rename.py`
- Modified: `src/vaultspec_core/tests/cli/test_gitignore.py`
- Modified: `src/vaultspec_core/tests/cli/test_gitattributes.py`
- Modified: `src/vaultspec_core/tests/cli/test_sync_parse.py`
- Created: `src/vaultspec_core/core/tests/test_atomic_write.py`

## Description

Claude and Codex recognize project-scoped native enrollment, broader scopes remain
explicit, and selective companion lifecycle operations preserve Core ownership. The
corrective step centralizes all text and binary managed-file writes on an exclusively
created, unpredictable, identity-checked sibling file and removes the non-atomic
Windows fallback. Real-filesystem topology tests, 1,773 selected unit tests, repository
static checks, and a formal review pass establish readiness for package and installed
host smoke gates. The built source and wheel artifacts passed isolated smoke, and a
wheel-installed project was recognized by both real host CLIs.
