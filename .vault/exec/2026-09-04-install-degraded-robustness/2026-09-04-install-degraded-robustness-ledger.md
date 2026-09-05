---
tags:
  - '#exec'
  - '#install-degraded-robustness'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:33b5f4765558f87900036769c009040747e389ab16883af3f6c66275fc6772fb'
related:
  - "[[2026-09-04-install-degraded-robustness-plan]]"
---

# `install-degraded-robustness` ledger

## Changes

- `S01` `M` `src/vaultspec_core/core/gitignore.py`
- `S02` `M` `src/vaultspec_core/core/gitignore.py`
- `S03` `M` `src/vaultspec_core/core/gitignore.py`
- `S03` `M` `src/vaultspec_core/core/git_artifacts.py`
- `S03` `M` `src/vaultspec_core/core/provision.py`
- `S04` `M` `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`
- `S04` `M` `src/vaultspec_core/tests/cli/test_gitignore.py`
- `S05` `M` `src/vaultspec_core/core/gitignore.py`
- `S06` `M` `src/vaultspec_core/core/gitignore.py`
- `S07` `M` `src/vaultspec_core/core/gitignore.py`
- `S07` `M` `src/vaultspec_core/core/gitattributes.py`
- `S08` `M` `src/vaultspec_core/tests/cli/test_gitignore.py`
- `S09` `M` `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`
- `S18` `M` `src/vaultspec_core/tests/cli/workspace_factory.py`
- `S18` `M` `src/vaultspec_core/tests/cli/test_audit_coverage.py`
- `S18` `M` `src/vaultspec_core/tests/cli/test_sync_conditions.py`
- `S10` `M` `src/vaultspec_core/core/provision.py`
- `S11` `M` `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`
- `S19` `M` `src/vaultspec_core/core/manifest.py`
- `S19` `M` `src/vaultspec_core/core/provider_sync.py`
- `S12` `M` `src/vaultspec_core/core/diagnosis/collectors_config.py`
- `S12` `M` `src/vaultspec_core/core/diagnosis/signals.py`
- `S13` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S14` `M` `src/vaultspec_core/tests/cli/test_doctor.py`
- `S14` `M` `src/vaultspec_core/tests/cli/test_collectors.py`
- `S14` `M` `src/vaultspec_core/tests/cli/test_signals.py`
- `S20` `M` `src/vaultspec_core/core/resolver_repo.py`
- `S15` `M` `docs/framework.md`
- `S16` `M` `docs/verification.md`
- `S21` `M` `src/vaultspec_core/core/provider_sync.py`
- `S22` `M` `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`
- `S23` `M` `src/vaultspec_core/core/diagnosis/collectors_config.py`
- `S24` `M` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S25` `M` `src/vaultspec_core/tests/cli/test_collectors.py`
- `S26` `M` `src/vaultspec_core/core/git_artifacts.py`
- `S27` `M` `src/vaultspec_core/core/provider_sync.py`
- `S28` `M` `src/vaultspec_core/core/uninstall.py`
- `S29` `M` `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`

## Notes

- `S17` verified the remaining gitignore claims in the CLI reference and the README
  against the changed behaviour and found no edit needed. The CLI reference already
  listed `.gitignore` among the conditions that raise the `doctor` exit code, which
  was true only of the corrupted state before `P04` and is true of every degraded
  state now; the README's claim that the install manages a block is unchanged. No
  path was touched, so the Step registers no row.
