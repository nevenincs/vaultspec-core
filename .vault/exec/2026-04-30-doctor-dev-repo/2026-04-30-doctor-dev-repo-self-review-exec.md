---
tags:
  - '#exec'
  - '#doctor-dev-repo'
date: '2026-04-30'
related:
  - '[[2026-04-30-doctor-dev-repo-plan]]'
  - '[[2026-04-30-doctor-dev-repo-adr]]'
  - '[[2026-04-30-doctor-dev-repo-research]]'
---

# `doctor-dev-repo` `self-review`

Self-review of the GitHub issue #93 fix landed on branch
`fix/93-doctor-dev-repo`.

- Modified: `src/vaultspec_core/core/diagnosis/collectors.py`
- Modified: `src/vaultspec_core/tests/cli/test_collectors.py`
- Created: `.vault/research/2026-04-30-doctor-dev-repo-research.md`
- Created: `.vault/adr/2026-04-30-doctor-dev-repo-adr.md`
- Created: `.vault/plan/2026-04-30-doctor-dev-repo-plan.md`
- Created: `.vault/doctor-dev-repo.index.md`

## Description

`collect_framework_presence` now defers an import of
`_cached_is_dev_repo` from `vaultspec_core.core.guards` and consults
the resolved target path after the manifest-existence check fails.
On a positive multi-signal dev-repo match the collector returns
`FrameworkSignal.PRESENT`; otherwise the original
`FrameworkSignal.CORRUPTED` return is preserved verbatim. No
`FrameworkSignal` enum members were added or renamed, and no
downstream consumer (`spec_cmd.py` rendering, `resolver.py`
gating, `diagnosis.py` orchestrator branching) needed to change.

The deferred-import pattern matches the rest of the module, which
documents in its top-of-file docstring that imports from `core.*`
are deferred inside function bodies to prevent cycles. The
`_cached_is_dev_repo` wrapper is memoized via `functools.lru_cache`
upstream, so collecting framework presence twice in a single
`spec doctor` run does not re-parse `pyproject.toml`.

## Tests

Two new test methods were added to
`TestFrameworkPresence` in
`src/vaultspec_core/tests/cli/test_collectors.py`:

- `test_dev_repo_present_without_manifest` builds a real-on-disk
  dev-repo workspace from `tmp_path` (pyproject with
  `name = "vaultspec-core"`, the canonical
  `src/vaultspec_core/__init__.py` layout, and an empty
  `.vaultspec/` directory) and asserts `PRESENT`. The
  `_cached_is_dev_repo` LRU cache is cleared before and after the
  assertion so neighbouring tests cannot mask a regression by
  pre-warming the cache against the real source repo.
- `test_consumer_pyproject_match_alone_still_corrupted` builds a
  pyproject-only workspace (no package source layout) and asserts
  `CORRUPTED`. This locks the multi-signal contract: a hand-crafted
  pyproject naming `vaultspec-core` cannot trigger the dev-repo
  branch on its own.

Both tests use the real filesystem; no mocks, patches, stubs, or
skips. The pre-existing `test_corrupted_no_manifest` continues to
assert `CORRUPTED` because its workspace has no `pyproject.toml`
at all, and that path is unchanged.

## Quality gates

- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_collectors.py::TestFrameworkPresence -v`
  - 7 passed in 0.16s
- `uv run --no-sync pytest`
  - 1377 passed, 8 pre-existing failures unrelated to issue #93
    (`tests/test_mcp_config.py` requires a `.mcp.json` not tracked
    in the repo; `test_agents_render.py::TestGeminiCliLoadsRenderedAgents`
    fails the same way on `main`).
- `uv run --no-sync ty check src/vaultspec_core` -> all checks
  passed
- `uv run --no-sync ruff check` and `ruff format --check` -> clean
- `uv run --no-sync vaultspec-core vault check all` -> clean
- `uv run --no-sync vaultspec-core spec doctor` -> framework: ok /
  `.vaultspec/` present; exit 0
- `uv run --no-sync prek run --all-files` -> the issue-#93-relevant
  hooks (`Vault Doctor (Fix)`, `Vault Doctor (Check)`) pass; the
  remaining `mdformat`, `pymarkdown`, `block-manual-changelog`
  failures are pre-existing CHANGELOG.md baseline issues untouched
  by this branch.

## Acceptance test

The headline acceptance test for this fix is the absence of
`--no-verify`. The bootstrap commit (`chore(#93): bootstrap research stub for doctor dev-repo fix`) used `--no-verify` once because it
necessarily lands before the fix. Every commit and push thereafter
on this branch (the `fix(#93): ...` commit and any review-loop
commits) must pass the spec-check pre-commit and pre-push hook
naturally. The `fix(#93): ...` commit was created and pushed
without `--no-verify`; both the pre-commit and pre-push runs of
`Vault Doctor (Check)` reported `Passed`.

## Audit sweep

Grepping `FrameworkSignal\.CORRUPTED` across the repository
confirmed the remaining production sites do not produce the signal
on a dev-repo path: the two surviving `CORRUPTED` returns in
`collectors.py` are downstream of the manifest existing but
failing to parse or omitting the `installed` key (the dev repo
hits neither because it has no `providers.json` to begin with).
The `spec_cmd.py`, `diagnosis.py`, and `resolver.py` references
only consume the signal for rendering, exit-code mapping, and
resolver branching; none of them produce it. The
`test_resolver.py` references feed the signal directly into
resolver tests and are unaffected by the collector contract
change.
