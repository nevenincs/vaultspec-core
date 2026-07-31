---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:305325bda4b100d58ee01f063118647e3d2c51022a691c2382322aaa15569a6a'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p1-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p2-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p3-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p4-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p5-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P6 plan: Integration, Pre-commit Hooks, MCP Tool, and Docs

## Steps

### Phase `P01` - Integration, pre-commit, MCP, and docs

Run the full check suite against the project vault, wire the vault-fix pre-commit hook, expose the check MCP tool, and update reference documentation.

- [x] `P01.S01` - add the full-suite integration test asserting every checker runs without exception against the project vault; `src/vaultspec_core/vaultcore/checks/tests/test_run_all.py`.
- [x] `P01.S02` - wire the vault-fix pre-commit hook running vault check all --fix; `.pre-commit-config.yaml`.
- [x] `P01.S03` - expose the check suite as the check MCP orientation tool with fix support; `src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `P01.S04` - update the CLI reference documentation to describe every vault check subcommand in place of vault audit; `.vaultspec/reference/cli.md`.
