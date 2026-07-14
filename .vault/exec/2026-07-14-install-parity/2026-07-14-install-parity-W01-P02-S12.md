---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S12'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add DEV precedence and dev-group detection tests covering both packages and the mixed dependency-plus-dev-group configuration

## Scope

- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add `TestDetectionTaxonomy` exercising `detect_package_evidence` directly across the full leak-boundary taxonomy: project dependencies and optional dependencies as RUNTIME, the default dev group and the legacy `tool.uv.dev-dependencies` list as DEV, a named non-default group and absence as NONE, runtime outranking dev when a package sits in both, PEP 503 underscore spellings, and the lenient missing-or-malformed-file path.
- Add a package-parameter case asserting a companion distribution (`vaultspec-rag`) classifies on its own placement independently of `vaultspec-core` in the same manifest.
- Add `TestDevPrecedence` covering DEV entering the resolution chain: detected dev group resolves to DEV, detected optional dependency resolves to DEPENDENCY, a named group falls through to TOOL, a persisted DEV outranks runtime detection, an explicit DEV is permitted ahead of a manifest that does not yet list the package and overrides persisted and detected values, and the package parameter resolves each of a mixed core-dependency / rag-dev configuration from its own entry.
- Add `TestDevRefusal` asserting explicit DEV without a `pyproject.toml` raises with a mode-named message and a fallback hint.

## Outcome

The detection taxonomy and the DEV precedence path are now covered from the specification rather than from observed output: every expected value derives from the ADR's leak-boundary rules (optional dependencies leak and so are runtime; only the default dev group is dev; named groups are out of scope). The mixed-configuration case the ADR's Constraints require is exercised in both directions, at the detection layer and at the resolution layer, confirming that each package reads only its own placement and its own declared entry with no cross-package branch. The refusal extension is pinned so the DEV mode cannot silently fall back to tool mode when no manifest exists to declare the placement in. All 55 `test_workspace_mode.py` unit tests pass; `ruff` and `ty` are clean. No test doubles, skips, or tautologies: every assertion runs against a real `pyproject.toml` and a real `workspace.json` on the filesystem factory.

## Notes

None.
