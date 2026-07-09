---
generated: true
tags:
  - '#index'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - '[[2026-07-09-cli-usage-analytics-P05-S15]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S16]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S17]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S18]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S19]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S20]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S21]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S22]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S23]]'
  - '[[2026-07-09-cli-usage-analytics-P05-S24]]'
  - '[[2026-07-09-cli-usage-analytics-adr]]'
  - '[[2026-07-09-cli-usage-analytics-plan]]'
  - '[[2026-07-09-cli-usage-analytics-research]]'
---

# `cli-usage-analytics` feature index

Auto-generated index of all documents tagged with `#cli-usage-analytics`.

## Documents

### adr

- `2026-07-09-cli-usage-analytics-adr` - `cli-usage-analytics` adr: dev-only transcript analytics module for empirical CLI usage grounding | (**status:** `accepted`)

### exec

- `2026-07-09-cli-usage-analytics-P05-S15` - Implement the verb-hotspots metric as a pure function counting each (verb, subcommand) leaf over the CallRecord stream
- `2026-07-09-cli-usage-analytics-P05-S16` - Implement the command-and-flag n-gram metric as a pure function over the canonical flag and token sequence
- `2026-07-09-cli-usage-analytics-P05-S17` - Implement the features-utilized metric as a pure function intersecting distinct (verb, subcommand) pairs with the capability inventory
- `2026-07-09-cli-usage-analytics-P05-S18` - Implement the feature-tag-usage metric as a pure function distributing --feature and -f values
- `2026-07-09-cli-usage-analytics-P05-S19` - Implement the tool-call-misses metric as a pure function sequencing records by retry_key to separate corrected retries and genuine misses from by-design non-zero exits
- `2026-07-09-cli-usage-analytics-P05-S20` - Implement the overuse-and-dead-surface metric as a pure function comparing observed counts against the declared-capability denominator
- `2026-07-09-cli-usage-analytics-P05-S21` - Implement the token-and-turn-cost-per-class metric as a pure function grouping cost by verb class
- `2026-07-09-cli-usage-analytics-P05-S22` - Implement the report renderers writing records.jsonl as the full CallRecord stream and report.md as the seven metric families, both aggregates and hashes only with no raw command bodies
- `2026-07-09-cli-usage-analytics-P05-S23` - Implement the python -m statistic entrypoint wiring source discovery, normalization, metrics, and report rendering into the full pipeline
- `2026-07-09-cli-usage-analytics-P05-S24` - Run python -m statistic over the operator in-window corpus and verify it emits the real records.jsonl and report.md into gitignored statistic/out/

### plan

- `2026-07-09-cli-usage-analytics-plan` - `cli-usage-analytics` plan

### research

- `2026-07-09-cli-usage-analytics-research` - `cli-usage-analytics` research: transcript tool-call analytics grounding
