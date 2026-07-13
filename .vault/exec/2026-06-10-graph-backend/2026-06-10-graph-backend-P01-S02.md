---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S02
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# raise the networkx dependency floor to 3.6

## Scope

- `pyproject.toml`

## Description

- Raised the networkx dependency floor in `pyproject.toml` from `>=3.4` to `>=3.6`.
- Ran `uv lock` to propagate the specifier change into `uv.lock`; the resolved networkx version was already >=3.6 so no package version changed.

## Outcome

The dependency specifier now matches the minimum version required for the deterministic `edges="edges"` wire key established in S01. All 58 graph tests pass.

## Notes

No incidents. The lock file update changed only the recorded specifier; the resolved package set is unchanged.
