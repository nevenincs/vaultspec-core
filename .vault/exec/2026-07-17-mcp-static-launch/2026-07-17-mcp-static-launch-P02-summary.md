---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# `mcp-static-launch` `P02` summary

All three implementation steps closed and independently reviewed. The
dependency-mode branch of the single launch comparator gained the no-sync
guard, the observed-shape matcher learned the bounded legacy shape, and
every launch-shape assertion moved through the comparator with new coverage
for the legacy and adversarial shapes. Review verdict: pass after one high
finding (decision-record stems in source comments) was resolved by
rewording; details in the feature audit.

- Modified: `src/vaultspec_core/core/mcps.py`, `src/vaultspec_core/core/diagnosis/collectors.py`, `src/vaultspec_core/tests/cli/test_collectors.py`, `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`

## Description

Land the decision's core amendment: a rendered dependency or dev launch is
now a static execution, the doctor keeps honest mode inference on
pre-refresh workspaces, and the test suites pin the guarded shape once as
the anti-tautology anchor while deriving everything else through the
renderer.
