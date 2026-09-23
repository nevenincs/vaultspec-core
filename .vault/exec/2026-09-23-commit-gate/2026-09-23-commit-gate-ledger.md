---
tags:
  - '#exec'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:1caa65310801ef123a4151d1b7edd048ed5a7aa08ca8ddae6d4f257d6a42a477'
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
- `S08` `M` `src/vaultspec_core/core/enums.py`
- `S08` `M` `src/vaultspec_core/core/precommit.py`
- `S08` `M` `src/vaultspec_core/core/diagnosis/collectors_precommit.py`
- `S08` `M` `.pre-commit-config.yaml`
- `S08` `M` `dev/guards/test_automation_contracts.py`
- `S08` `M` `src/vaultspec_core/core/tests/test_commands.py`
- `S08` `M` `src/vaultspec_core/tests/cli/test_convergence_advisories.py`
- `S08` `M` `src/vaultspec_core/tests/cli/test_flow_bugs.py`
- `S08` `M` `src/vaultspec_core/tests/cli/test_precommit_hook_set.py`
- `S08` `M` `src/vaultspec_core/tests/cli/test_signals.py`
- `S08` `verify:` `ty check` -> `pass`
- `S09` `M` `docs/framework.md`
- `S09` `M` `docs/CLI.md`
- `S09` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S09` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S09` `verify:` `vaultspec-core commit-gate (30k corpus, 5 docs, 0.81s)` -> `pass`
- `S04` `M` `src/vaultspec_core/tests/cli/test_precommit_opt_out.py`
- `S04` `M` `src/vaultspec_core/tests/cli/test_precommit_yml_config.py`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/tests/test_staged_gate.py`
- `S05` `M` `src/vaultspec_core/tests/cli/test_provider_guard.py`
- `S03` `D` `dev/init/hooks.py`
- `S03` `M` `dev/init/__main__.py`
- `S03` `M` `dev/init/contract.py`
- `S07` `M` `src/vaultspec_core/cli/root_commit_gate.py`
- `S07` `M` `src/vaultspec_core/tests/cli/test_commit_gate_cli.py`
- `S08` `M` `src/vaultspec_core/vaultcore/checks/structure.py`
- `S08` `M` `src/vaultspec_core/core/diagnosis/collectors_provider.py`
- `S08` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S08` `verify:` `pytest doctor and checks` -> `pass`
- `S09` `M` `src/vaultspec_core/core/resolver_repo.py`
- `S09` `M` `src/vaultspec_core/tests/cli/test_precommit_hook_set.py`
- `S09` `verify:` `ty check` -> `pass`

## Notes

- `S03` authorized by the user's direct request to fix just init; not governed by the proposed ADR
- `S05` full-suite run also hit test_rename_concurrency under -n auto; it passes 3/3 alone and is untouched by this Step
- `S08` test_rename_concurrency failed intermittently under -n auto in full runs; it passes alone and exercises rename/edit locks this Step does not touch
- `S09` the deployed .vaultspec/reference mirror is left for the next release carry-forward, matching how it has been refreshed from the packaged builtins after each release
