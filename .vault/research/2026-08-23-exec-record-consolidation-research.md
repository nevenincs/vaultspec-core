---
tags:
  - '#research'
  - '#exec-record-consolidation'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v2'
body_hash: 'sha256:6cf65e022090f0a5c04141c01ed520698d467549dbfe6765b4753986eb67d27e'
related: []
---

# `exec-record-consolidation` research: `Execution-record corpus audit`

## Findings

Measured against the read-only production vault at
`aeat-worktrees/main/.vault` on 2026-08-23. All figures are counts of live
files on disk, not estimates.

### Corpus share

`.vault/exec/` holds 7,362 files and 17,929,131 bytes: 38% of the vault by
bytes and 66% of its files. The next largest directory, `audit/`, holds 1,291
files and 11.9 MB. Against this, `plan/` holds 220 files and 3.7 MB.

Layout is 205 plan-scoped subdirectories, maximum depth 2, one flat file per
Step.

### Per-file distribution

Across the 7,362 records: mean 2,435 bytes, p50 1,668, p75 3,021, p90 5,200,
p99 11,460, max 94,483. Lines: mean 45, p50 34, max 1,126.

### Step-to-record cardinality

The mapping is exactly 1:1 with plan Steps. `unstructured-document-ingestion`
has 306 Steps and 308 records; `import-centralization` 388 and 388;
`docstring-google-style` 994 and 994.

Byte-wise the record set dwarfs the plan it derives from:

| plan | Steps | plan KB | exec KB | ratio |
|---|---|---|---|---|
| unstructured-document-ingestion | 306 | 237 | 1,532 | 6.4x |
| profile-password-custody | 208 | 104 | 1,167 | 11.2x |
| cli-authority-verb-conformance | 287 | 80 | 885 | 11.0x |
| conformance-cli | 80 | 25 | 523 | 20.7x |
| live-pull-verification-sweep | 33 | 17 | 307 | 17.4x |

Reading one plan's execution history is therefore expensive:
`profile-password-custody` at 207 files and 1.17 MB costs roughly 292k tokens,
more than a single context window.

### Content composition

83.8% of body characters sit on lines naming no file at all; only 12.6% of
content lines mention any path. By section, the narrative sections dominate:
Outcome 34.9% of body bytes, Description 24.9%, Notes 22.8% - 82.6% combined.
The one mechanical, file-listing section, Scope, is 3.2%.

Frontmatter is a further 11.1% of all bytes (2.0 MB) and is machine-generated.

14.5% of all sections are empty: Notes 1,496 instances, Description 1,404,
Outcome 1,287. The template mandates four headings whether or not the Step has
anything to record under them. One sampled record,
`docstring-google-style-S87`, is 364 bytes with every body section empty: the
file is entirely scaffold.

### Consumers

No code path reads an execution record's body. `mcp_server/tools/orientation.py`
carries `canonical_id`, `display_path`, `checked`, and `record_stem`;
`cli/status_cmd.py` reports `exec_missing` and `exec_activity`;
`vaultcore/checks/body_sections.py` validates section names against the schema
registry. The machinery needs existence and a Step mapping. The prose is
write-only.

### Growth

| month | files | bytes | mean size |
|---|---|---|---|
| 2026-06 | 1,632 | 2.86 MB | 1,749 |
| 2026-07 | 3,382 | 6.35 MB | 1,877 |
| 2026-08 (23 days) | 2,288 | 8.40 MB | 3,671 |

August is roughly 100 records per day at double the previous mean size, and
accounts for nearly half the corpus in a partial month. Growth is unbounded on
both axes: count is 1:1 with Steps by construction, and size per record is
uncapped.

### Projection

A mechanical row-based record measures about 490 bytes against the 2,435-byte
mean, an 80% reduction. Consolidating a plan's records into one ledger compounds
this: `import-centralization` at 388 Steps goes from 659 KB across 388 files to
roughly 56 KB in one file, 91.5% smaller and 388 times fewer files.

## Sources

- Production corpus: `aeat-worktrees/main/.vault` (read-only reference), counted
  2026-08-23.
- Firmware under measurement: `builtins/templates/exec-step.md`,
  `builtins/templates/exec-summary.md`,
  `builtins/skills/vaultspec-execute/SKILL.md`,
  `builtins/rules/vaultspec.builtin.md`.
- Consumer trace: `mcp_server/tools/orientation.py`, `cli/status_cmd.py`,
  `plan/status.py`, `vaultcore/checks/body_sections.py`,
  `vaultcore/checks/exec_mapping.py`.
