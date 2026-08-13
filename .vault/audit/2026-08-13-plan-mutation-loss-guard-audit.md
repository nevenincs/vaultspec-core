---
tags:
  - '#audit'
  - '#plan-mutation-loss-guard'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:85465885012a5daeb936d50b4a19585a4343ea0688bd35fd19e56393b9812b65'
related:
  - "[[2026-06-05-plan-serializer-fixes-adr]]"
---

# `plan-mutation-loss-guard` audit: `Issue 305 implementation review`

## Scope

Reviewed the shared plan write guard, the Phase renumber call site, and real CLI regression coverage for issue 305. The review checked fail-closed handling of malformed hierarchy, active-item multiplicity, legitimate retirement, duplicate repair, and renumber operations, MCP inheritance of the shared guard, actionable errors, and source-file immutability after refusal.

## Findings

### duplicate-identifier-multiplicity | high | Resolved before delivery

The first implementation compared active identifiers as sets, allowing one occurrence of a duplicated identifier to disappear without detection. The guard now counts occurrences and reports the exact lost identifier and count. A regression removes one of two live `S01` rows and proves an undeclared loss is refused without changing the file, while the established display-path-targeted duplicate removal remains available as an explicit repair.

## Recommendations

No open implementation findings remain. Keep the `PLAN010` and `PLAN070` source-structure refusal and multiplicity-aware active-item invariant in the shared write guard so CLI and MCP mutations retain the same protection. Preserve real-behavior regression coverage for malformed headings, independent active-item loss, duplicate occurrence loss and repair, and legitimate Phase renumbering.
