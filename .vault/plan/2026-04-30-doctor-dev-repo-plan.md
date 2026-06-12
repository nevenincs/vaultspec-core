---
tags:
  - '#plan'
  - '#doctor-dev-repo'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-doctor-dev-repo-adr]]'
  - '[[2026-04-30-doctor-dev-repo-research]]'
---

# `doctor-dev-repo` `fix collect_framework_presence dev-repo handling` plan

Land the smallest production change required to stop `spec doctor`
from false-positiving on the vaultspec-core source repository, plus
two real-filesystem tests that lock the new behaviour and the
preserved consumer-corruption path.

## Proposed Changes

Modify `collect_framework_presence` in
`src/vaultspec_core/core/diagnosis/collectors.py`. After the
manifest-existence check fails, defer-import `_cached_is_dev_repo`
from `vaultspec_core.core.guards` and consult it with the resolved
target path. Return `FrameworkSignal.PRESENT` on a positive match,
otherwise retain the existing `FrameworkSignal.CORRUPTED` path. No
other production files change.

Add two test cases in
`src/vaultspec_core/tests/cli/test_collectors.py` under
`TestFrameworkPresence`:

- A dev-repo workspace built inline from `tmp_path` (real
  pyproject.toml with `name = "vaultspec-core"`, real
  `src/vaultspec_core/__init__.py`, real `.vaultspec/` directory,
  no `providers.json`), asserting `PRESENT`.
- A near-miss consumer workspace (real pyproject.toml with the
  matching name but no `src/vaultspec_core/__init__.py`),
  asserting `CORRUPTED`. The existing
  `test_corrupted_no_manifest` already covers the no-pyproject
  case; this new test locks the multi-signal contract.

## Tasks

- Apply the production change in `collectors.py` (deferred import of
  `_cached_is_dev_repo`, dev-repo branch returning `PRESENT`).
- Add two `TestFrameworkPresence` test methods using `tmp_path`
  (no mocks, no patches; real on-disk fixture).
- Run the targeted test module, then the full suite, then `ty`,
  `ruff`, `vault check all`, and `spec doctor` on this repo.
- Push the fix; the `spec-check` pre-commit and pre-push hook must
  pass naturally without `--no-verify` from this commit forward.
- Loop on gemini code review until two consecutive clean rounds.

## Parallelization

Single-file production change; no parallel tracks. Tests can be
written in the same commit as the fix because the production change
flips the assertion they would make.

## Verification

- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_collectors.py -v`
  passes, including the two new tests.
- `uv run --no-sync pytest` passes the full suite with no regressions.
- `uv run --no-sync ty check src/vaultspec_core` is clean.
- `uv run --no-sync ruff check` and
  `uv run --no-sync ruff format --check` are clean.
- `uv run --no-sync vaultspec-core vault check all` passes.
- `uv run --no-sync vaultspec-core spec doctor` reports the
  framework as `ok / present` on this repo.
- `uv run --no-sync prek run --all-files` passes.
- A subsequent `git commit` and `git push` on this branch succeed
  without `--no-verify`. This is the headline acceptance signal:
  if any push needs `--no-verify` after the fix lands, the fix is
  incomplete.
