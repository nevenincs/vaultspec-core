---
tags:
  - '#plan'
  - '#diagnosis-surface-parity'
date: '2026-06-28'
modified: '2026-06-28'
tier: L2
related:
  - '[[2026-06-28-diagnosis-surface-parity-adr]]'
  - '[[2026-06-28-diagnosis-surface-parity-audit]]'
  - '[[2026-06-28-diagnosis-surface-parity-research]]'
---

<!-- RETIRED: P05, S12, S13 -->

# `diagnosis-surface-parity` plan

## Description

Restore single-comparator parity across install, sync, and spec doctor per the sibling
ADR. Each phase fixes one instance of the same root pattern - one decision made by
divergent code - surfaced in the sibling audit.

## Steps

### Phase `P01` - Single comparator for content integrity

Rebuild collect_content_integrity as a view over the canonical sync renderer: compare expected rendered content to the destination and emit DIVERGED on mismatch, restoring conformance to the ambiguous-states resolver ADR.

- [x] `P01.S01` - Extract a shared expected-content renderer the collector can call without writing, reusing the apply_file_sync rendering path; `src/vaultspec_core/core/sync.py`.
- [x] `P01.S02` - Rebuild collect_content_integrity to compare rendered expected content to destination, emitting DIVERGED on mismatch and CLEAN on match; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [x] `P01.S03` - Wire DIVERGED through the doctor presentation and exit-code mapping so content drift is reported; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P01.S04` - Add a real-workspace test asserting doctor and sync agree on a content-drifted provider file; `src/vaultspec_core/tests/cli/`.

### Phase `P02` - Orphan-snapshot pruning owner

Give orphan-snapshot pruning a single owner in the snapshot module so retiring a builtin returns builtin_version to clean and the snapshot tree tracks the live builtin set.

- [x] `P02.S05` - Add prune_orphan_snapshots to the snapshot module removing snapshots whose live builtin no longer exists; `src/vaultspec_core/core/revert.py`.
- [x] `P02.S06` - Invoke orphan pruning from the install snapshot refresh path so builtin_version recovers; `src/vaultspec_core/core/commands.py`.
- [x] `P02.S07` - Add a test retiring a builtin and asserting builtin_version returns to clean after prune; `src/vaultspec_core/tests/cli/`.

### Phase `P03` - Centralise provider-file registry

Make one registry the shared source of truth for files that may live in a provider directory, read by both the MCP writer and the doctor foreign-file detector; cover mcp_config.json and its lock sibling.

- [x] `P03.S08` - Read the shared ToolConfig mcp_config_file in the foreign-file detector and accept lock byproducts; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [x] `P03.S09` - Add a test asserting a freshly synced antigravity provider dir is COMPLETE not MIXED; `src/vaultspec_core/tests/cli/`.

### Phase `P04` - Per-file install dry-run granularity

Bring install --dry-run to the same per-file granularity as sync so the preview no longer understates provider blast radius.

- [x] `P04.S10` - Render install --dry-run provider work per file via the sync sources instead of per directory; `src/vaultspec_core/core/commands.py`.
- [x] `P04.S11` - Add a test asserting install --dry-run lists individual provider files; `src/vaultspec_core/tests/cli/`.

## Parallelization

P01 through P04 are independent; each is self-contained with its own real-workspace test
and was executed in sequence.

## Verification

Full unit gate green (1558 passed), spec doctor clean, lint suite and vault check all
green.
