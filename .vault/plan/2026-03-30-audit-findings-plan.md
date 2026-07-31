---
tags:
  - '#plan'
  - '#audit-findings'
date: '2026-03-30'
modified: '2026-07-31'
body_hash: 'sha256:4ad2dfd8866f759dd0099311fe8dbb45d99eff886f0c5f42fd5550f4c0a6a966'
tier: L2
related:
  - '[[2026-03-27-cli-ambiguous-states-audit]]'
  - '[[2026-03-27-cli-ambiguous-states-resolver-adr]]'
  - '[[2026-03-27-cli-ambiguous-states-gitignore-adr]]'
  - '[[2026-03-28-cli-ambiguous-states-audit-fixes-plan]]'
  - '[[2026-03-27-cli-ambiguous-states-prior-art-research]]'
  - '[[2026-03-23-audit-fixes-research]]'
---

# `audit-findings` plan

### Phase `P01` - Data safety

Prevent data loss and destructive side effects across rmtree, mcp.json rewrite, gitignore flag, and uninstall ordering.

- [x] `P01.S01` - add rmtree_robust for symlink and NTFS-readonly-safe deletion and guard ensure_dir against writing inside symlink targets; `src/vaultspec_core/core/helpers.py`.
- [x] `P01.S02` - surgically remove only the vaultspec-core key from .mcp.json on uninstall and merge into an existing file on install; `src/vaultspec_core/core/mcps_native.py`.
- [x] `P01.S03` - fix the gitignore_managed flag to reflect a pre-existing managed block on idempotent reinstall; `src/vaultspec_core/core/provision.py`.
- [x] `P01.S04` - reorder uninstall to delete the vaultspec framework directory last, collecting per-deletion errors as best-effort teardown; `src/vaultspec_core/core/uninstall.py`.

### Phase `P02` - Error visibility

Surface sync, install, and hook errors to the user instead of silently swallowing them.

- [x] `P02.S05` - display SyncResult.errors in outcome rendering and set a non-zero exit code when errors are present; `src/vaultspec_core/cli/rendering_outcomes.py`.
- [x] `P02.S06` - propagate warnings through agent result merging; `src/vaultspec_core/core/agents.py`.
- [x] `P02.S07` - unify filesystem and framework error handling across CLI command entry points; `src/vaultspec_core/cli/_errors.py`.
- [x] `P02.S08` - elevate preflight and hook-trigger failure logging from debug to warning; `src/vaultspec_core/cli/root_preflight.py`.
- [x] `P02.S09` - log silent catch clauses across config generation, sync, and hook firing; `src/vaultspec_core/core/config_gen.py`.
- [x] `P02.S10` - propagate hook trigger failures into SyncResult.warnings; `src/vaultspec_core/hooks/engine.py`.
- [x] `P02.S11` - propagate unparseable-source-file skips from md, skill, and system-part collectors into SyncResult.warnings; `src/vaultspec_core/core/helpers.py`.
- [x] `P02.S12` - propagate include-resolution failures into the caller's warnings instead of only embedding an HTML comment; `src/vaultspec_core/protocol/providers/base.py`.

### Phase `P03` - Flag precedence and logic fixes

Fix flag precedence, guard clauses, fail-fast-to-raise conversions, and per-pass error isolation.

- [x] `P03.S13` - fix install --upgrade --dry-run flag precedence to show the upgrade-specific preview; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S14` - guard install --skip core when the vaultspec framework directory is absent; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S15` - wrap each sync pass and each install phase in its own try/except so one failure does not prevent the others; `src/vaultspec_core/core/sync.py`.
- [x] `P03.S16` - raise instead of silently returning a false negative on gitignore write failure, manifest corruption, and preflight repair failure; `src/vaultspec_core/core/gitignore.py`.

### Phase `P04` - Exception boundaries and production hardening

Wrap remaining CLI entry points in consistent exception handling and harden atomic writes.

- [x] `P04.S17` - unify exception handling across resource, vault, and spec CLI commands through a single error handler; `src/vaultspec_core/cli/_errors.py`.
- [x] `P04.S18` - clean up the temporary bootstrap directory in a finally block after tool-config bootstrap completes; `src/vaultspec_core/core/provision.py`.
- [x] `P04.S19` - harden atomic_write with exclusive temp-file creation, binary-mode writes, and finally-block temp cleanup; `src/vaultspec_core/core/helpers.py`.
- [x] `P04.S20` - make gitignore block writes atomic; `src/vaultspec_core/core/gitignore.py`.
- [x] `P04.S21` - handle TOCTOU deletion races and TagError during managed markdown block sync; `src/vaultspec_core/core/sync.py`.
- [x] `P04.S22` - distinguish unreadable-due-to-permission from missing in diagnosis collectors; `src/vaultspec_core/core/diagnosis/collectors_config.py`.
- [x] `P04.S23` - validate provider directories exist on disk before counting them as sharing a directory during uninstall; `src/vaultspec_core/core/manifest.py`.

### Phase `P05` - Test coverage gap closure

Close the untested-scenario catalog from the audit with real-filesystem tests.

- [x] `P05.S24` - add tests for rmtree_robust covering symlinked directories, Windows read-only files, and partial failures; `src/vaultspec_core/tests/cli/test_audit_coverage.py`.
- [x] `P05.S25` - add tests for surgical .mcp.json removal preserving user entries and merging into an existing file; `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`.
- [x] `P05.S26` - add tests for SyncResult.errors display and exit code; `src/vaultspec_core/tests/cli/test_rendering.py`.
- [x] `P05.S27` - add tests for the untested install/sync/uninstall flag-combination and lifecycle-chain scenarios cataloged in the audit; `src/vaultspec_core/tests/cli/test_install_conditions.py`.

### Phase `P06` - Security and path safety

Add path containment validation, a content-ownership prune heuristic, and a unified exception hierarchy.

- [x] `P06.S28` - validate that resolved tool directories stay within the workspace root before any write or delete operation; `src/vaultspec_core/core/types.py`.
- [x] `P06.S29` - add a content-ownership heuristic so sync --force prune only removes vaultspec-managed markdown files; `src/vaultspec_core/core/sync.py`.
- [x] `P06.S30` - unify the exception hierarchy so TagError, WorkspaceError, and RelatedResolutionError inherit from VaultSpecError; `src/vaultspec_core/core/exceptions.py`.

### Phase `P07` - Systemic filesystem hardening

Migrate remaining raw writes to atomic_write, add backup-before-write, and add manifest locking and include-cycle guards.

- [x] `P07.S31` - migrate config, manifest, and gitignore writes that matter for crash-safety to atomic_write; `src/vaultspec_core/core/helpers.py`.
- [x] `P07.S32` - add backup-before-write to vault document auto-fix checks so a failed write leaves a recoverable .bak; `src/vaultspec_core/vaultcore/checks/links.py`.
- [x] `P07.S33` - add advisory locking around the manifest read-modify-write cycle; `src/vaultspec_core/core/manifest.py`.
- [x] `P07.S34` - add a circular-include guard to include resolution so a cycle emits a warning instead of recursing; `src/vaultspec_core/protocol/providers/base.py`.

### Phase `P08` - Completeness and UX polish

Close remaining dead-signal, messaging, and count-accuracy gaps surfaced by the audit.

- [x] `P08.S35` - implement ProviderDirSignal.MIXED detection for provider directories containing unrecognized content; `src/vaultspec_core/core/diagnosis/collectors_provider.py`.
- [x] `P08.S36` - emit a clear error when doctor is run against a nonexistent target directory; `src/vaultspec_core/cli/root_doctor.py`.
- [x] `P08.S37` - add thread-safety to the config singleton for concurrent MCP server requests; `src/vaultspec_core/config/config.py`.
- [x] `P08.S38` - warn when a skill directory is missing its SKILL.md entrypoint during sync; `src/vaultspec_core/core/skills.py`.
- [x] `P08.S39` - surface a ranking-unavailable note in the find MCP tool response when the vault graph fails to load; `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `P08.S40` - track errored files in SyncResult counts and skip incrementing the skipped counter on shared-directory double-sync; `src/vaultspec_core/core/types.py`.
