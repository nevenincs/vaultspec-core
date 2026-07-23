---
tags:
  - '#plan'
  - '#vault-check-validators'
date: '2026-07-23'
modified: '2026-07-23'
tier: L2
related:
  - '[[2026-07-23-vault-check-validators-adr]]'
  - '[[2026-07-23-vault-check-validators-research]]'
---

# `vault-check-validators` plan

## Description

Implement the two read-only `vault check` validators decided in the accepted
ADR: `exec-mapping` (#233), which confirms every execution record maps back to a
live Step in its parent plan, and `body-sections` (#234), which confirms every
document body carries the sections its template mandates. Both emit WARNING, both
are read-only, and both wire into `run_all_checks` behind one integration seam.
The work proceeds in dependency order: the `step_id` frontmatter field first
(P01), then each checker with its tests (P02, P03), then suite registration
(P04). Note for execution and review: the first `vault check` run against the
established vault will surface a burst of pre-existing WARNINGs (legacy documents
missing newer sections, older exec records) - this is the expected, non-blocking
steady state the ADR anticipated, not a regression introduced by these checkers.

## Steps

### Phase `P01` - step_id first-class field

Make the originating Step id a parsed frontmatter field so exec back-mapping reads it from the snapshot.

- [x] `P01.S01` - Add a step_id field to DocumentMetadata and parse it in parse_vault_metadata beside modified and archived; `src/vaultspec_core/vaultcore/models.py, src/vaultspec_core/vaultcore/parser.py`.
- [x] `P01.S02` - Add a unit test asserting step_id parses from exec-record frontmatter and is None when absent; `src/vaultspec_core/vaultcore/tests/test_parser.py`.

### Phase `P02` - exec-mapping checker (#233)

Validate every execution record maps back to a live Step in its parent plan, distinguishing archived parents from dangling references.

- [x] `P02.S03` - Implement the exec-mapping checker classifying each exec record step_id as live, retired, or dangling against its parse_plan-resolved parent plan, resolving the plan from the related link with a plan-stem filename fallback under the plan directory and skipping legacy records that carry no step_id; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.
- [x] `P02.S04` - Add the archived-parent probe so a parent plan found under .vault/\_archive/plan/ yields no finding while a truly-absent plan yields a warning; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.
- [x] `P02.S05` - Degrade an unparseable parent plan to a single warning against that plan rather than raising, honouring the no-crash policy; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.
- [x] `P02.S06` - Add real-filesystem tests for valid mapping, retired step id, dangling step id, and truly-missing parent plan; `src/vaultspec_core/vaultcore/checks/tests/test_exec_mapping.py`.
- [x] `P02.S07` - Add the mandatory archived-parent regression test asserting an exec record whose plan is archived produces no finding; `src/vaultspec_core/vaultcore/checks/tests/test_exec_mapping.py`.
- [x] `P02.S08` - Add a test that an unparseable parent plan degrades to a warning and does not crash the checker; `src/vaultspec_core/vaultcore/checks/tests/test_exec_mapping.py`.

### Phase `P03` - body-sections checker (#234)

Validate every document body carries the sections its template mandates, treating comment-only or placeholder-only sections as empty.

- [x] `P03.S09` - Implement the body-sections checker deriving required sections from each document type's template via get_template_path and \_TEMPLATE_NAMES, flagging any required heading that is absent or holds only a hint comment or unreplaced placeholder, and selecting the exec-step or exec-summary template by the summary-filename convention; `src/vaultspec_core/vaultcore/checks/body_sections.py`.
- [x] `P03.S10` - Degrade a missing or unreadable template for a document type to a skip with no finding rather than raising; `src/vaultspec_core/vaultcore/checks/body_sections.py`.
- [x] `P03.S11` - Add real-filesystem tests covering present, absent, and empty required sections for the adr, plan, research, reference, audit, and exec document types; `src/vaultspec_core/vaultcore/checks/tests/test_body_sections.py`.
- [x] `P03.S12` - Add a tier-conditional test asserting the four plan sections are required across plan tiers; `src/vaultspec_core/vaultcore/checks/tests/test_body_sections.py`.
- [x] `P03.S13` - Add an empty-section detection test asserting a comment-only section and a placeholder-only section are each flagged as empty; `src/vaultspec_core/vaultcore/checks/tests/test_body_sections.py`.

### Phase `P04` - registration and suite integration

Wire both checkers into the run_all_checks suite read-only and confirm they surface through the aggregate check.

- [x] `P04.S14` - Register both checkers in run_all_checks in the fix and non-fix branches following the read-only check_encoding precedent and add them to __all__; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P04.S15` - Add an integration test asserting both checkers appear in run_all_checks output and report fixed_count zero in the fix branch; `src/vaultspec_core/vaultcore/checks/tests/test_run_all.py`.

## Parallelization

P01 must land first: both checkers and their tests depend on the `step_id`
field. P02 (exec-mapping) and P03 (body-sections) are independent of each other
and may be executed in parallel once P01 is closed. Within P02 and P03 the
implementation Steps precede their test Steps. P04 (registration) is last: it
depends on both checker modules existing, and its integration test depends on
both being registered.

## Verification

The plan is complete when every Step is closed. Each checker is verified by its
own real-filesystem tests (no doubles): exec-mapping proves the valid, retired,
dangling, and truly-missing-plan classifications plus the mandatory
archived-parent probe and the unparseable-plan degradation; body-sections proves
present, absent, and empty-section detection across every document type, the
tier-conditional plan sections, and comment-only or placeholder-only sections
reading as empty. Both checkers must surface in `run_all_checks` with
`fixed_count` zero (read-only). The full suite (`pytest src/vaultspec_core`), the
repo-root tree (`pytest tests`), `ruff check`, `ruff format --check`, and `ty`
must all pass, and a `vaultspec-code-review` audit signs off before close.
