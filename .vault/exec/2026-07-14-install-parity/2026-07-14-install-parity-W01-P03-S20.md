---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S20'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add renderer and doctor tests covering TOOL, DEPENDENCY, and DEV for the core package plus a mixed configuration where a companion package's entry differs, asserting no cross-package branch

## Scope

- `src/vaultspec_core/tests/cli/test_collectors.py`

## Description

- Cover the generalized launch comparator across all three modes for both core
  and a companion package, asserting dev renders byte-identically to dependency.
- Cover the MCP definition renderer: core token substitution per mode, dev equal
  to dependency, a companion package's own package/module substituted and its
  metadata keys stripped, user definitions passed through, and the input left
  unmutated.
- Cover hook-entry rendering per mode, asserting dev entries and prefix equal
  dependency's and tool renders the uvx prefix.
- Cover per-package `resolve_render_mode`, including a sibling-only file bridging
  the absent package to dependency and dev resolving to dev (not its render
  alias).
- Add the flag-1 regression: a dev declaration against dependency-shaped
  artifacts is CLEAN, plus a mixed core-tool/rag-tool configuration where each
  package diagnoses independently.
- Cover per-package version-floor collection and the `diagnose` per-package map
  (populated per declared package, empty with no declaration).
- Add the flag-2 end-to-end CliRunner test: `install --mode dev` succeeds,
  renders dependency-shaped MCP and hook artifacts, persists mode `dev`, and the
  doctor reports clean with a dev label; plus a doctor multi-package-rows test
  asserting one install-mode row per package and a companion floor row driving
  the error exit code.

## Outcome

27 new tests across eight classes, all passing, and the full `test_collectors`
suite (99 tests) is green with `ty check` clean. The flag-1 false-mismatch and
flag-2 install-dev KeyError regressions both have dedicated coverage, and the
mixed-package and doctor-row cases exercise the cross-configuration path the ADR
requires.

## Notes

The dev-mode installs list vaultspec-core in the pyproject so the explicit
`--mode dev` request has a manifest to declare a placement in (a dev-mode
request with no pyproject at all is refused by design, not by this phase).
