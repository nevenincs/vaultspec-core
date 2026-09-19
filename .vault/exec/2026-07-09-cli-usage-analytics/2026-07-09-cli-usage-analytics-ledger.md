---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:86e81e7ae907fc3006f8ea248a8cc8c8160331f731ac3f291af6e25940b651a0'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# `cli-usage-analytics` ledger

## Changes

- `S15` `T` `statistic/metrics/hotspots.py`
- `S15` `T` `tests/statistic/test_metrics.py`
- `S16` `T` `statistic/metrics/ngrams.py`
- `S16` `T` `tests/statistic/test_metrics.py`
- `S17` `T` `statistic/metrics/features.py`
- `S17` `T` `tests/statistic/test_metrics.py`
- `S18` `T` `statistic/metrics/feature_tags.py`
- `S18` `T` `tests/statistic/test_metrics.py`
- `S19` `T` `statistic/metrics/misses.py`
- `S19` `T` `tests/statistic/test_metrics.py`
- `S20` `T` `statistic/metrics/surface.py`
- `S20` `T` `tests/statistic/test_metrics.py`
- `S21` `T` `statistic/metrics/cost.py`
- `S21` `T` `tests/statistic/test_metrics.py`
- `S22` `T` `statistic/report/render.py`
- `S22` `T` `tests/statistic/test_report.py`
- `S23` `T` `statistic/__main__.py`
- `S23` `T` `tests/statistic/test_main.py`
- `S24` `T` `statistic/out/records.jsonl`
- `S24` `T` `statistic/out/report.md`
- `S01` `A` `statistic/__init__.py`
- `S01` `A` `statistic/parsers/__init__.py`
- `S01` `A` `statistic/normalize/__init__.py`
- `S01` `A` `statistic/metrics/__init__.py`
- `S01` `A` `statistic/report/__init__.py`
- `S02` `M` `statistic/normalize/models.py`
- `S03` `M` `statistic/normalize/exit_status.py`
- `S04` `M` `statistic/parsers/base.py`
- `S05` `A` `.gitignore`
- `S05` `A` `tests/statistic/test_packaging_exclusion.py`
- `S06` `A` `statistic/metrics/capability.py`
- `S07` `M` `tests/statistic/fixtures/cli_reference.md`
- `S07` `M` `tests/statistic/test_capability.py`
- `S08` `A` `statistic/normalize/tokenize.py`
- `S09` `A` `statistic/normalize/extract.py`
- `S10` `A` `tests/statistic/test_normalize.py`
- `S11` `A` `statistic/parsers/claude.py`
- `S12` `A` `statistic/parsers/codex.py`
- `S13` `M` `tests/statistic/fixtures/claude`
- `S13` `M` `tests/statistic/test_claude_source.py`
- `S14` `M` `tests/statistic/fixtures/codex`
- `S14` `M` `tests/statistic/test_codex_source.py`
- `S15` `A` `statistic/metrics/hotspots.py`
- `S15` `A` `tests/statistic/test_metrics.py`
- `S16` `A` `statistic/metrics/ngrams.py`
- `S16` `A` `tests/statistic/test_metrics.py`
- `S17` `A` `statistic/metrics/features.py`
- `S17` `A` `tests/statistic/test_metrics.py`
- `S18` `A` `statistic/metrics/feature_tags.py`
- `S18` `A` `tests/statistic/test_metrics.py`
- `S19` `A` `statistic/metrics/misses.py`
- `S19` `A` `tests/statistic/test_metrics.py`
- `S20` `A` `statistic/metrics/surface.py`
- `S20` `A` `tests/statistic/test_metrics.py`
- `S21` `A` `statistic/metrics/cost.py`
- `S21` `A` `tests/statistic/test_metrics.py`
- `S22` `A` `statistic/report/render.py`
- `S22` `A` `tests/statistic/test_report.py`
- `S23` `A` `statistic/__main__.py`
- `S23` `A` `tests/statistic/test_main.py`
- `S24` `M` `statistic/out/records.jsonl`
- `S24` `M` `statistic/out/report.md`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
