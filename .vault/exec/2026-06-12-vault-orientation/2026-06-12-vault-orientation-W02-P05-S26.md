---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S26
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the orientation rollup module computing active features, plans in flight, recency ordering, and the graph-backed step-keyed grounding trace

## Scope

- `src/vaultspec_core/vaultcore/orientation.py`

## Description

- Add `orientation.py` as a pure data layer with no printing and no Typer dependency.
- Add `compute_rollup` returning a `Rollup` of active features ordered by latest activity, plans in flight ordered most-recently-modified first with open/closed counts and completion percent, recent documents grouped by type honouring `limit` and `since_days`, and totals reused verbatim from `get_stats`.
- Add `compute_trace` returning a `GroundingTrace`: each plan's steps mapped to their execution-record stem (or `None` for open steps without a record), an explicit unlinked bucket for exec records that reference the plan without a resolvable step id, and grounding documents grouped by type from the plan's graph neighbours.
- Implement recency per decision D3b: lenient parse `modified`, fall back to `date`, then the filename date prefix; an undateable document sorts last via a `date.min` sentinel and never crashes.
- Use `VaultGraph` and the `ExecRecordIndex` internally; expose only dataclasses of stems and scalars, with no networkx types or edge lists.
- Implement target resolution precedence exact plan stem, plan path, feature tag; raise `TargetResolutionError` carrying near-matches for an ambiguous or unknown target.

## Outcome

- A smoke run against the live vault returns the in-flight orientation plan with correct open and closed counts, maps every step to its record stem, groups grounding into adr and research, and raises the typed error for an unknown target.
- Ruff format, ruff check, and ty check all pass on the new module.

## Notes

- The rollup consumes the batched `collect_all_statuses` core from the prior step, so the in-flight scan parses each plan once against one shared exec-record index.
- Audit documents are included in the grounding group set alongside adr, research, reference, and prior plans, since an audit is legitimate grounding context for a plan.
