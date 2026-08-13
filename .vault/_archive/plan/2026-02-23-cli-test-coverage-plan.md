---
tags:
  - '#plan'
  - '#cli-test-coverage'
date: '2026-02-23'
modified: '2026-07-31'
body_hash: 'sha256:6329caff544627aaa0b6b70852eed6687f6e38746eb0c2b4b6808c261b66d83c'
tier: L2
related:
  - '[[2026-02-22-cli-ecosystem-factoring-adr]]'
  - '[[2026-03-23-cli-test-coverage-research]]'
---

# cli-test-coverage plan

## Steps

### Phase `P01` - Unified router tests

Cover the top-level CLI router: help, version, and namespace routing.

- [x] `P01.S01` - cover the unified CLI router help, version, and namespace routing; `src/vaultspec_core/tests/cli/test_main_cli.py`.

### Phase `P02` - Spec resource management tests

Cover the spec resource-group commands: help text, argument parsing, and dispatch routing.

- [x] `P02.S02` - cover spec resource-group help text, functional behavior, and dispatch routing; `src/vaultspec_core/tests/cli/test_spec_cli.py`.

### Phase `P03` - Agent dispatch CLI tests

Cover argument parsing and validation for agent-dispatch CLI commands.

- [ ] `P03.S03` - cover argument parsing and validation for agent-dispatch CLI commands; `src/vaultspec_core/tests/cli/test_integration.py`.

### Phase `P04` - Team lifecycle CLI tests

Cover the team lifecycle CLI commands, including message and spawn.

- [ ] `P04.S04` - cover team lifecycle message and spawn command argument parsing and validation; `src/vaultspec_core/tests/cli/test_integration.py`.
