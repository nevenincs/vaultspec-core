---
tags:
  - '#exec'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:44abe4b7d9a0a0562fe964f6b7ca2405bbffb69ae832b7227e4badc788f7663e'
related:
  - "[[2026-09-23-commit-gate-plan]]"
---

# `commit-gate` ledger

## Changes

- `S03` `M` `dev/init/plan.py`
- `S03` `A` `dev/tests/test_init_plan.py`
- `S03` `M` `justfile`
- `S03` `M` `dev/init/README.md`
- `S03` `M` `docs/framework.md`
- `S03` `verify:` `ty check` -> `pass`
- `S01` `M` `.vault/adr/2026-05-15-template-annotation-sanitization-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S04` `M` `src/vaultspec_core/core/prek_boundary.py`
- `S04` `M` `src/vaultspec_core/core/precommit.py`
- `S04` `M` `src/vaultspec_core/core/diagnosis/collectors_precommit.py`
- `S04` `M` `src/vaultspec_core/core/gitignore.py`
- `S04` `M` `src/vaultspec_core/core/uninstall.py`
- `S04` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S04` `A` `src/vaultspec_core/tests/cli/test_precommit_yml_config.py`
- `S04` `verify:` `ty check` -> `pass`
- `S05` `M` `src/vaultspec_core/core/git_artifacts.py`
- `S05` `M` `src/vaultspec_core/cli/root_doctor.py`
- `S05` `M` `src/vaultspec_core/core/commands.py`
- `S05` `M` `src/vaultspec_core/core/tests/test_commands.py`
- `S05` `M` `src/vaultspec_core/tests/cli/test_flow_bugs.py`
- `S05` `A` `src/vaultspec_core/tests/cli/test_provider_guard.py`
- `S05` `verify:` `ty check` -> `pass`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/staged.py`
- `S06` `M` `src/vaultspec_core/vaultcore/checks/encoding.py`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/tests/test_staged.py`
- `S06` `verify:` `ty check` -> `pass`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/staged.py`
- `S02` `A` `src/vaultspec_core/vaultcore/checks/tests/test_staged_gate.py`
- `S02` `verify:` `ty check` -> `pass`
- `S07` `A` `src/vaultspec_core/cli/root_commit_gate.py`
- `S07` `M` `src/vaultspec_core/cli/root.py`
- `S07` `M` `src/vaultspec_core/core/git_artifacts.py`
- `S07` `M` `docs/CLI.md`
- `S07` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S07` `A` `src/vaultspec_core/tests/cli/test_commit_gate_cli.py`
- `S07` `verify:` `ty check` -> `pass`

## Notes

- `S03` authorized by the user's direct request to fix just init; not governed by the proposed ADR
- `S05` full-suite run also hit test_rename_concurrency under -n auto; it passes 3/3 alone and is untouched by this Step
