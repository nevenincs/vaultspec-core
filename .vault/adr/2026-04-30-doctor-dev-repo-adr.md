---
tags:
  - '#adr'
  - '#doctor-dev-repo'
date: '2026-04-30'
related:
  - '[[2026-04-30-doctor-dev-repo-research]]'
  - '[[2026-04-30-doctor-dev-repo-plan]]'
---

# `doctor-dev-repo` adr: `consult is_dev_repo in collect_framework_presence` | (**status:** `accepted`)

## Problem Statement

`collect_framework_presence` declares the framework `CORRUPTED` whenever
`.vaultspec/providers.json` is absent. The vaultspec-core source
repository never carries that file (it is an install artifact
generated on consumer projects), so `spec doctor` and the
`spec-check` pre-commit / pre-push hook fail on every commit and push
to this repo. Contributors are forced to use `--no-verify`. We need
the diagnosis to recognise the source repo as a legitimately present
framework while still catching consumer projects whose installs are
genuinely broken.

## Considerations

- A robust dev-repo detector already exists at
  `src/vaultspec_core/core/guards.py:37` (`is_dev_repo`) with a
  memoized `_cached_is_dev_repo` wrapper. It requires both a
  `pyproject.toml` declaring `name = "vaultspec-core"` AND the
  package source layout at `src/vaultspec_core/__init__.py`, which
  cannot collide with consumer projects without a deliberate fork.
- The only callsites of `collect_framework_presence` are the
  diagnose orchestrator and the test module. No new enum value is
  needed if we route the dev repo through `FrameworkSignal.PRESENT`,
  which is semantically correct: the framework directory IS the
  canonical source of truth on the dev repo.
- The existing `collect_gitignore_state` already calls
  `is_dev_repo` for an analogous reason (#88), so the precedent is
  in the codebase.

## Constraints

- Must not regress consumer-side detection: a project that ships
  `.vaultspec/` without `providers.json` and is not the
  vaultspec-core source repo must still report `CORRUPTED`.
- Must not change the `FrameworkSignal` enum surface; downstream
  consumers (`spec_cmd.py` rendering, `resolver.py`) already handle
  `PRESENT` correctly.
- Must keep the cost low: `spec doctor` may collect framework
  presence twice during a single run, so the dev-repo check must be
  memoized.

## Implementation

In `collect_framework_presence`, after the manifest-existence check
fails, import `_cached_is_dev_repo` from
`vaultspec_core.core.guards` and consult it with the resolved target
path. On a positive match return `FrameworkSignal.PRESENT`; on a
negative match retain the existing `FrameworkSignal.CORRUPTED`
return. The import is deferred inside the function body to honour
the module's documented "imports from `core.*` modules are deferred
inside function bodies to prevent import cycles" rule (see the
collector module docstring).

Add two test cases in `src/vaultspec_core/tests/cli/test_collectors.py`
under `TestFrameworkPresence`:

- A dev-repo workspace built inline via `tmp_path` (pyproject with
  `name = "vaultspec-core"` plus `src/vaultspec_core/__init__.py`
  plus an empty `.vaultspec/` directory), asserting `PRESENT`.
- A near-miss workspace (correct pyproject but no package source
  layout), asserting `CORRUPTED`. This locks the boundary against
  hand-crafted-pyproject false negatives on consumer projects.

The existing `test_corrupted_no_manifest` continues to assert
`CORRUPTED` because its workspace has no `pyproject.toml` at all.

## Rationale

Reusing `is_dev_repo` is the smallest, most obvious change. It
shares the dev-repo detection contract with `guard_dev_repo` and
`collect_gitignore_state`, so behaviour stays consistent across
diagnosis and write-guarding code paths. Adding a new
`FrameworkSignal.DEV_REPO` member would force every consumer of the
enum (status renderer, resolver, exit-code mapping) to handle a new
case for no semantic gain, since the desired outcome is exactly
"PRESENT" everywhere.

## Consequences

- `spec doctor` exits clean on the source repo, which means the
  `spec-check` pre-commit / pre-push hook stops false-positiving and
  contributors can drop `--no-verify`.
- A consumer project that adopts the vaultspec-core source layout
  wholesale (forking, not consuming) would also pass the dev-repo
  test. That is a legitimate dev-repo state and the right answer
  for that case too.
- The dev-repo signal becomes a tacit invariant of three diagnosis
  collectors. Any future change to `is_dev_repo` semantics needs to
  consider all three callers.
