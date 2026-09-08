---
tags:
  - '#audit'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:423fd6339c940246303e6976e9ca317341182055dfd94bd3d1c737f391763df9'
related:
  - "[[2026-09-08-framework-reword-plan]]"
---

# `framework-reword` audit: `Cohesive framework review`

## Scope

Independent read-only Astra review of the integrated framework against `2026-09-08-framework-reword-adr` and the four-Step L1 plan. Covered routing metadata, rules, skills, personas, templates, creation, validation and repair, ADR transitions, execution, delegation, resume, and review. Initial implementation review covered commits 072a8ee8 and af390ddf plus the working implementation. The unrelated session's review and completion claims were discarded under explicit user instruction.

## Findings

### decision-free-validation | high | The owning plan checker still required a relationship

Initial result: REVISION REQUIRED. `src/vaultspec_core/plan/checks/frontmatter_check.py` emitted PLAN002 for plans with Steps and no related links, contradicting the decision-free route. The schema-only scenario missed this second gate.

### historical-status-repair | high | The instructed historical repair command did not perform the repair

Initial result: REVISION REQUIRED. The curation references directed historical supersession drift to adr-status --fix, but that check only normalized quoting. Replaying an old transition to an intermediate successor now correctly fails when that successor is no longer accepted.

### discovery-contract | medium | CLI discovery repeated obsolete prerequisites

The schema command help and generated references still required Research for every ADR and an ADR for every plan, and the handbook advertised automatic semantic-link repair.

### integrated-rereview | low | All reported findings resolved; Astra review PASS

Independent Astra re-review returned PASS with no remaining findings. PLAN002 was removed, with full collect_all regression coverage for decision-free L1-L4 plans. Historical repair now requires inspection of reciprocal recorded edges and an owning body edit, without changing acceptance or creating a transition. CLI help and generated references describe evidence alternatives, optional plan ADR links, and detection-only semantic checks. Supporting approval instructions, persona blockers, and routing hints now defer to the shared contract. The reviewer verified the corrected integrated paths read-only; test execution and final bundle synchronization remain executor verification, not claims made by the reviewer.

### execution-verification | low | Verification complete with a Windows stress-test caveat

The broader lifecycle, plan, and MCP run completed with 1,108 passed and one failure: PermissionError reading the temporary document in the unchanged test_concurrent_edit_survives_a_fix_pass, before its lost-update assertion. The same test passed all 300 iterations on an isolated rerun without changing code or weakening assertions. This is a non-reproduced file-access failure, not a claim that the broad run was entirely green. Two existing warnings concern synchronous tests carrying asyncio marks.

The separate seed/reference guard run passed 18 tests; rendering passed 49 tests; focused full-plan-check and supersession tests passed 43 tests. Ruff, Ty, CLI reference generation checks, provider checks, skill validation, and feature vault checks passed. Installed Markdown bundles were byte-compared with canonical sources and all matched. No unrelated session scratch or implementation-review audit remains.

## Recommendations

Remove the obsolete plan-link requirement and test the full checker at every tier. Describe the existing owning body-edit route for confirmed historical supersession drift. Regenerate discovery references from corrected CLI help and state the compatibility-only behavior of the fix flag. Re-review the integrated corrections before completion.
