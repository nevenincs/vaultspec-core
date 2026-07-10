---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S22'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the report renderers writing records.jsonl as the full CallRecord stream and report.md as the seven metric families, both aggregates and hashes only with no raw command bodies

## Scope

- `statistic/report/render.py`
- `tests/statistic/test_report.py`

## Description

- Add the record-stream writer that serializes each call record as one JSON line.
- Retain the command only as its hash in the stream, never any raw command text.
- Add the Markdown report renderer as a pure function over records and the inventory.
- Render all seven metric families as aggregates, hashes, verb paths, tags, and counts.
- Add a home-path redactor as a defensive guard against any surfaced path field.
- Assert the round-trip, the seven sections, key aggregates, the findings guard, the
  no-home-path contract, and on-disk persistence.

## Outcome

The report layer writes the full record stream for re-analysis and an aggregate-only
Markdown report for humans. The renderer reads no clock and touches no filesystem, so
its output is byte-stable for a fixed input. No raw command body or home path can reach
the report by construction. Seven report tests pass and both modules are lint and type
clean.

## Notes

The renderer does not surface any path field today; the home-path redactor is a
defensive guard for future edits, and is asserted directly.
