---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S24'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Run python -m statistic over the operator in-window corpus and verify it emits the real records.jsonl and report.md into gitignored statistic/out/

## Scope

- `statistic/out/records.jsonl`
- `statistic/out/report.md`

## Description

- Run the pipeline module over the operator corpora with the default thirty-day window.
- Discover both home-derived roots and normalize every in-window invocation.
- Emit the full record stream and the aggregate-only report into the output directory.
- Confirm both artifacts are gitignored and never staged.
- Fix a normalization bug the real corpus surfaced in single-line loop unrolling.

## Outcome

The run analyzed 19588 records, 11116 from Claude and 8472 from Codex, over the last
thirty days, and wrote both the record stream and the report into the gitignored output
directory. A version-control ignore check confirms neither artifact is tracked. The
report grounds the MCP overhaul empirically: the plan-step-check and vault-add verbs
dominate the hotspots, roughly a third of the declared surface is dead, the genuine
miss rate is under eight percent once by-design findings and venv noise are excluded,
and the vault verb class dominates token cost.

## Notes

The real corpus surfaced a normalization defect: a single-line loop whose items are
backslash Windows paths raised a regex-replacement escape error, because the item was
used as a substitution template. The fix substitutes each item through a callable
replacement so backslashes are inserted verbatim, with a regression test added. Codex
per-call token cost stayed unattributed in this run because the cumulative snapshots do
not bracket individual calls in the sampled rollouts; the report labels cost as
directional, and this is an accepted adapter-side limitation rather than a metric
defect.
