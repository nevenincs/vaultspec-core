---
tags:
  - '#exec'
  - '#cli-simplification-ux'
date: '2026-05-26'
modified: '2026-05-26'
step_id: W02.P04-P06
related:
  - '[[2026-05-17-cli-simplification-ux-plan]]'
---

# `cli-simplification-ux` `W02.P04-P06`

- Agent: Claude Sonnet 4.6 (Thinking), high effort

- Session id: 13236da6-3f2b-47b4-a4d2-a5d0d896b754

- Modified/Added:

  - `src/vaultspec_core/vaultcore/models.py`
  - `src/vaultspec_core/vaultcore/query.py`
  - `src/vaultspec_core/graph/api.py`
  - `src/vaultspec_core/cli/vault_cmd.py`
  - `src/vaultspec_core/cli/spec_cmd.py`
  - `src/vaultspec_core/cli/config_cmd.py` (Added)
  - `src/vaultspec_core/core/local_config.py` (Added)
  - `src/vaultspec_core/vaultcore/checks/rename_integrity.py` (Added)
  - `src/vaultspec_core/tests/cli/test_config_editor_safety.py` (Added)
  - `.vaultspec/CLI.md`

## Description

### Phase `W02.P04` - Memory-lifecycle verbs

- Add `supersedes`, `superseded_by`, `derived_from`, `promoted_to`, `archived` fields to `VaultMetadata` dataclass with ISO date validation for `archived` (S11)
- Implement `archive_feature` in `query.py`: validate tag exists, enumerate feature documents from `.vault/`, move files to `.vault/_archive/<feature>/`, compute cross-feature incoming `related:` link warnings, support `--dry-run` preview (S14)
- Implement `unarchive_feature` in `query.py`: reverse move from `_archive/<feature>/` back to original directories, prune empty archive subdirectories, support `--dry-run` (S14)
- Harden `VaultGraph` in `api.py` to resolve node targets inside `.vault/_archive/` and suppress dangling-link records for archived documents (S14)
- Implement `cmd_feature_archive` in `vault_cmd.py` with `--dry-run`, `--force`, `--json` flags; raise `VaultSpecError` on nonexistent or ambiguous feature tag (S14)
- Implement `cmd_feature_unarchive` in `vault_cmd.py` with `--dry-run`, `--force`, `--json` flags (S14)
- Document `vault adr supersede --by` command and `vault feature unarchive` in `.vaultspec/CLI.md` to satisfy handbook-drift tests (S13)
- Align `test_archive_nonexistent_feature` to assert `VaultSpecError` on missing tag, replacing the earlier zero-count assertion (S14)

### Phase `W02.P05` - Atomic rename invariant

- Implement atomic resource rename in `spec_cmd.py` rewriting both filename and frontmatter together for rules, skills, and agents (S16)
- Add `vault check rename-integrity` in `rename_integrity.py` supporting both filename-wins (`--fix`) and frontmatter-wins (`--fix-frontmatter-wins`) (S17)
- Add comprehensive integration tests and verify check order in `test_vault_repair.py` (S17)

### Phase `W02.P06` - Spec edit safety

- Add `vaultspec-core config` command group with get, set, unset, list against `.vaultspec/config.toml` (S19)
- Implement editor resolution precedence ladder (flag -> config -> VAULTSPEC_EDITOR -> VISUAL -> EDITOR -> vi -> error) (S20)
- Wrap editor subprocess invocation to translate exit codes honestly: exit code 2 (unresolved editor), 3 (subprocess failure), 4 (user cancellation / exit 130) (S21)
- Add extensive safety, precedence, and exit code tests in `test_config_editor_safety.py` (S19, S20, S21)

## Verification

- Run and pass the 1,993-test suite cleanly (including `test_cli_handbook_drift`, `test_cli_language_contract`, `test_config_editor_safety`, and `rename` command suite).
- All Ruff linting (`ruff check`) and formatting (`ruff format --check`) checks are fully green and compliant with zero exceptions or skips.
