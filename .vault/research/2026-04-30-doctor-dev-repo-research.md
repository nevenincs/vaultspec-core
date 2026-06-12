---
tags:
  - '#research'
  - '#doctor-dev-repo'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-doctor-dev-repo-adr]]'
  - '[[2026-04-30-doctor-dev-repo-plan]]'
---

# `doctor-dev-repo` research: `spec doctor false positive on source repo`

GitHub issue #93 reports that `spec doctor` and the `spec-check`
pre-commit / pre-push hook fail on every commit and push to the
vaultspec-core source repository. The diagnosis classifies the
framework as `CORRUPTED`, which forces contributors to use
`--no-verify` to land any change. PR #92 hit this repeatedly. This
research confirms the root cause, lists every callsite that depends on
`collect_framework_presence`, and inventories the test fixtures that
construct `.vaultspec/` without `providers.json`.

## Findings

### Root cause

`collect_framework_presence` in `src/vaultspec_core/core/diagnosis/collectors.py`
returns `FrameworkSignal.CORRUPTED` whenever `.vaultspec/` exists but
`.vaultspec/providers.json` does not. `providers.json` is an install
artifact written by `install_run` on consumer projects. The source
repository ships `.vaultspec/` as its canonical content and never
generates `providers.json`, so the corruption signal fires
unconditionally.

Reproduction on a fresh worktree: `uv run --no-sync vaultspec-core spec doctor` -> `framework: error / .vaultspec/ corrupted manifest`. The
exit status is non-zero, so the `spec-check` hook entry
`uv run --no-sync vaultspec-core spec doctor` blocks every commit.

### Callsites of `collect_framework_presence`

- `src/vaultspec_core/core/diagnosis/collectors.py:63` - definition.
- `src/vaultspec_core/core/diagnosis/diagnosis.py:103` - the orchestrator
  invokes it once per `diagnose()` call. The orchestrator branches on
  `FrameworkSignal.CORRUPTED` at line 143 to skip content-integrity
  collection, but otherwise passes the signal through to the caller.
- `src/vaultspec_core/cli/spec_cmd.py:1236, 1242, 1438` - status
  rendering and error gating in `spec doctor`.
- `src/vaultspec_core/core/resolver.py:208` - resolver branches when
  the framework is corrupted.

### Existing dev-repo guard

`src/vaultspec_core/core/guards.py:37` already defines
`is_dev_repo(root)` with multi-signal detection. The function requires
both:

- `pyproject.toml` parses with `[project].name == "vaultspec-core"`.
- `src/vaultspec_core/__init__.py` exists at the canonical layout.

A consumer that ships a stale `pyproject.toml` declaring
`name = "vaultspec-core"` cannot trigger the guard without also
materialising the package source layout, which would be a deliberate
fork. The guard ships a memoized wrapper `_cached_is_dev_repo(root_str)`
already used by `guard_dev_repo` and `collect_gitignore_state`.

### Test fixtures that build `.vaultspec/` without `providers.json`

Direct construction in `src/vaultspec_core/tests/cli/test_collectors.py`:

- `TestFrameworkPresence.test_corrupted_no_manifest` - creates an
  empty `.vaultspec/` and asserts `CORRUPTED`. Genuinely a
  consumer-shaped corrupted install (no `pyproject.toml`).
- `TestFrameworkPresence.test_corrupted_invalid_json` - creates
  `.vaultspec/providers.json` with invalid JSON. Unaffected by the
  fix (manifest path exists, decode fails downstream).
- `TestFrameworkPresence.test_corrupted_no_installed_key` - creates
  `.vaultspec/providers.json` with valid JSON but no `installed`
  key. Unaffected by the fix.
- `TestBuiltinVersionState.test_no_snapshots` - creates `.vaultspec/`
  without `providers.json` but does not invoke
  `collect_framework_presence`.

The `WorkspaceFactory` always installs through the real `install_run`,
which writes `providers.json`, so factory-built workspaces never hit
the bug naturally.

### Constraints on the fix

- Must not regress consumer corruption detection: a non-source-repo
  workspace with `.vaultspec/` and no `providers.json` must still
  report `CORRUPTED`.
- Must not introduce a new `FrameworkSignal` member; the issue body
  explicitly states the dev repo IS present, so reusing
  `FrameworkSignal.PRESENT` matches the semantics and avoids a
  cascade through every consumer of the enum (status renderer,
  resolver, exit-code mapping).
- Must memoize the dev-repo check to keep `spec doctor` cheap on
  workspaces that hit the framework path twice (orchestrator +
  status rendering).

### Conclusion

Reuse `_cached_is_dev_repo` from `guards.py` inside
`collect_framework_presence` after the manifest-existence check fails.
Returns `FrameworkSignal.PRESENT` when the workspace passes the
multi-signal dev-repo test, otherwise falls through to the existing
`FrameworkSignal.CORRUPTED` path. Add two tests: one inline
dev-repo workspace asserting `PRESENT`, one consumer-shaped
workspace re-asserting `CORRUPTED` (the existing
`test_corrupted_no_manifest` already covers this; we add an
explicit pyproject-bearing-but-not-vaultspec case to lock the
boundary).
