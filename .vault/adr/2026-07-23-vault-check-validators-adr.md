---
tags:
  - '#adr'
  - '#vault-check-validators'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - "[[2026-07-23-vault-check-validators-research]]"
---

# `vault-check-validators` adr: `two read-only vault-check validators` | (**status:** `accepted`)

## Problem Statement

The `vault check` suite has two blind spots, both traced in
`2026-07-23-vault-check-validators-research` and both descended from the
unimplemented Phase 3 of the `vault-api` plan. An execution record can declare a
`step_id` and parent plan that resolve to nothing - a retired id, a renamed plan,
or a typo - and the vault reports clean (#233). A document body can be missing a
section its template mandates - an ADR with no `Consequences`, a plan with no
`Verification` - and every current checker passes it (#234). Both are silent
integrity gaps in the corpus the whole pipeline depends on, and both need a
decision now on checker shape, severity, and edge-case policy before any code is
written.

## Considerations

- Both validators plug into one integration seam: `run_all_checks` registration,
  `CheckResult`/`CheckDiagnostic` emission, snapshot/graph threading, feature
  filtering (`2026-07-23-vault-check-validators-research`).
- The plan parser already exposes live and retired Step ids
  (`Plan.steps[].canonical_id`, `Plan.retired_step_ids`), so #233 needs no new
  parsing infrastructure.
- The shipped templates already carry per-type `##` section sets and resolve
  through one existing seam (`get_template_path`), so #234 can keep templates as
  the single source of truth with no hardcoded list.
- The scanner hides `_archive`, which is both a benefit (archived docs are out of
  scope for free) and the sharpest #233 trap (an archived parent plan looks
  "missing" unless probed on disk).
- Neither gap has an unambiguous auto-repair, unlike `check_schema`'s
  add-a-`related:`-link fix.

## Considered options

- **One ADR, two read-only checkers (chosen).** Both validators share every
  integration concern and descend from the same plan phase; one ADR decides both,
  landing as two checker functions. Cons: a single record covers two behaviors -
  mitigated by delineating the two decisions explicitly below.
- **Two separate ADRs.** Rejected: duplicates the identical integration,
  severity, registration, and test-strategy reasoning across two records that
  would have to cross-reference each other constantly; fragments one coherent
  decision.
- **Extend an existing checker** (fold back-mapping into `check_features`,
  headings into `check_schema`). Rejected: `check_features` is feature-level
  presence and `check_schema` is cross-reference edges
  (`2026-07-23-vault-check-validators-research`); overloading either blurs a clean
  single-responsibility surface and complicates their existing `--fix` paths.
- **Make either checker `--fix`-capable.** Rejected: no safe unambiguous repair
  exists (the correct `step_id` target is unknown; a section's position/ordering/
  content is the author's). A fix that inserts an empty heading adds noise without
  resolving the defect.
- **#234 from a hardcoded section list.** Rejected by the issue and the research:
  the templates must stay the single source of truth so the two never drift.

## Constraints

- No new dependencies; both checkers use existing modules (`plan.parser`,
  `vaultcore.hydration`, `vaultcore.parser`, the graph/snapshot). No frontier or
  maturity risk.
- Parent-feature stability: #233 depends on `Plan.retired_step_ids` and
  `parse_plan`, which are mature and covered by the plan test suite; #234 depends
  on `_TEMPLATE_NAMES` and `get_template_path`, mature since the templates
  shipped. Both are stable seams, not in-flight features.
- No-Crash policy: a missing/unreadable template, an unparseable plan, or a legacy
  exec record without `step_id` must degrade to a skip or a finding, never an
  exception that aborts `vault check all`.

## Implementation

Two new modules under `src/vaultspec_core/vaultcore/checks/`, each a read-only
`CheckResult`-returning function, both registered in `run_all_checks` (identical
call in the fix and non-fix branches, following the `check_encoding` precedent)
and added to `__all__`.

**`step_id` becomes a first-class field.** `step_id` is added to
`DocumentMetadata` and parsed by a one-line branch beside `modified` and
`archived`, so exec back-mapping reads it from the snapshot rather than
re-parsing each file. This is the ratified decision, not an option.

**Checker one - `exec-mapping` (#233).** Iterates snapshot documents of type
`exec` (via `get_doc_type`), skipping generated indexes. For each, reads the
first-class `step_id` and the parent-plan reference. The parent plan is resolved
from the exec record's `related:` plan-stem link, falling back to locating
`.vault/plan/<stem>.md`. It then `parse_plan`s the plan and classifies:
`step_id` present in the live `canonical_id` set -> clean; present only in
`retired_step_ids` -> WARNING (references a retired Step); absent entirely ->
WARNING (dangling Step id); parent plan file absent from `.vault/plan/` ->
before flagging, probe `.vault/_archive/plan/<stem>.md`: if the plan is archived,
treat as expected (silent, no finding); if truly gone, WARNING. An exec record
with no `step_id` (legacy, pre-field) is skipped, not flagged. An unparseable
plan yields a single WARNING against that plan rather than a crash.

**Checker two - `body-sections` (#234).** For each snapshot document whose
`DocType` is in `_TEMPLATE_NAMES` (excluding `index`, which is generated), loads
the corresponding template via `get_template_path`, extracts the ordered set of
`##` headings from the template body as the required sections (no hardcoding),
and verifies the document body contains each required heading with real authored
content up to the next `##` or EOF. Absent heading -> finding; present-but-empty
heading -> finding. A section holding only a scaffold hint-comment (an HTML
comment block) or only an unreplaced `{placeholder}` counts as **empty** ->
finding, so a scaffolded-but-unauthored document does not pass. Author-added
extra sections are ignored. Exec documents select between `exec-step.md` and
`exec-summary.md` by the summary-filename convention. A missing or unreadable
template for a type degrades to a skip (no finding), never a crash.

Severity: both checkers emit **WARNING** for their defects (ratified). Both are
read-only (`supports_fix=False`, ratified); each finding's `fix_description`
names the manual remedy (correct or retire the `step_id`; add or fill the named
section).

## Rationale

WARNING, not ERROR, because both defects are corpus-hygiene signals that the
existing large vault and legacy records would surface in volume, and an ERROR
fails the doctor exit code and can gate commits (mirroring the #236 reasoning that
warning-level lag must not deadlock). `check_features` sets the precedent of
WARNING for structural-completeness gaps
(`2026-07-23-vault-check-validators-research`), whereas `check_schema` reserves
ERROR for a hard missing-grounding edge with an auto-fix. Read-only wins because
neither defect has a safe unambiguous repair, and an inserted empty section or a
guessed `step_id` would degrade signal. One ADR wins because the two validators
are one integration decision with two leaves, exactly as `references.py` already
co-locates two sibling checkers. Deriving #234's sections from the templates wins
on the single-source-of-truth criterion the issue makes binding: any future
template edit updates the contract with zero checker change.

## Consequences

Gains: every exec record is provably anchored to a live Step, and every document
body is provably section-complete against its template, closing two silent
integrity gaps and completing the stalled `vault-api` Phase 3. The template-derived
approach means #234 never drifts from the templates.

Difficulties and pitfalls: the first `vault check` run on an established vault may
surface a burst of pre-existing WARNINGs (legacy docs missing newer sections, old
exec records) - acceptable as advisory and non-blocking, but the plan must note
it so it is not mistaken for a regression. The `_archive` probe in #233 is the
one correctness-critical edge; its regression test is mandatory. Plans are the
tier-conditional #234 case - the four plan H2s are present at every tier, so
heading-presence holds; implementation must confirm `Parallelization` is genuinely
required at `L1` rather than tier-gated. Empty-section detection treats a
hint-comment-only or `{placeholder}`-only required section as empty (ratified), so
it is robust to the scaffold comments a fresh document carries before authoring
and cannot be satisfied by an unedited scaffold.
