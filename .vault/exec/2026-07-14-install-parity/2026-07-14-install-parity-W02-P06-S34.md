---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S34'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add tests covering --mode tool, dependency, and dev for the rag package, the mixed core-dependency-rag-tool configuration, and the tokenized MCP definition's rendered launch shape

## Scope

- `src/vaultspec_rag/tests/test_install_provision.py`

## Description

- Add `src/vaultspec_rag/tests/test_install_mode.py` exercising the real
  install orchestration over the real filesystem with no mocks and no network
  (provisioning, torch, and the MCP extra all opted out).
- Cover the three explicit modes persisting rag's entry and rendering its own
  launch shape; detection mapping a rag project dependency to dependency mode
  and a rag dev-group entry to dev mode; the no-pyproject tool default; and the
  dependency-without-pyproject refusal.
- Cover the mixed core-dependency/rag-tool configuration asserting both entries
  are preserved and each renders at its own mode, plus a sibling-preservation
  test against a pre-seeded core declaration.
- Cover upgrade inference (explicit wins, persisted wins, legacy dependency and
  tool shapes), the tokenized builtin's rendered launch per mode, the advisory
  moment-of-choice (fires on fresh election, silent on persisted read and tool
  mode), and the `--local-only` marker orthogonality.

## Outcome

Twenty-one tests pass. They assert against real `.mcp.json` and
`.vaultspec/workspace.json` writes and the real report warnings, with expected
launch shapes derived from the ADR's Implementation section rather than copied
from a run.

## Notes

The full rag unit gate was run to confirm no regressions from the change. The
tests use rag's existing test idiom (the `WorkspaceFactory` equivalent is rag's
own `tmp_path` workspaces and config-reset fixtures modelled on
`test_install_provision.py`); no mocks, skips, or tautologies were introduced.
