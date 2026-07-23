---
tags:
  - '#research'
  - '#vault-check-validators'
date: '2026-07-23'
modified: '2026-07-23'
related: []
---

# `vault-check-validators` research: `two missing vault-check validators`

Two gaps in the `vault check` suite were originally scoped as Phase 3 of the
stalled `vault-api` plan and never implemented. The first: no checker confirms
that an execution record maps back to a live Step row in its parent plan, so a
retired id, renamed plan, or typo in an exec record reports clean. The second:
no checker confirms a document body carries the sections its template mandates,
so an ADR missing `Consequences` passes every check. This document grounds both
in the real checker architecture, the exec/plan/template data structures, and
frames the design space the ADR must settle. The evidence favors two sibling
read-only checkers sharing one integration seam; the ADR decides names,
severity, template-derivation mechanics, and the edge-case policy.

## Findings

### The checker contract is a uniform, snapshot-fed function returning `CheckResult`

Every checker is a module-level function that returns a
`CheckResult(check_name=..., supports_fix=bool)` carrying a list of
`CheckDiagnostic(path, message, severity, fixable, fix_description)`
(`src/vaultspec_core/vaultcore/checks/_base.py:46-64`). Severity is one of
`Severity.ERROR | WARNING | INFO` (`_base.py:38-43`); the exit code and the
`--fix` machinery read `fixed_count` and the severity tallies. Checkers are
registered by being called in order inside `run_all_checks`
(`src/vaultspec_core/vaultcore/checks/__init__.py:74-210`), which builds one
`VaultGraph` and its `to_snapshot()` once and threads either the `graph` or the
`snapshot` into each checker, refreshing the graph only after a mutating checker
reports `fixed_count` (`__init__.py:130-134`). A new checker is added by
importing it, appending it to both the non-fix and fix branches, and adding it
to `__all__`. Read-only checkers (`check_encoding`, `check_feature_rename_integrity`)
run identically in both branches (`__init__.py:191,209`), which is the precedent
both new checkers follow.

### The snapshot is `path -> (DocumentMetadata, body)`; `step_id` is not yet parsed

`VaultSnapshot` is `dict[Path, tuple[DocumentMetadata, str]]` (`_base.py:20-24`),
the body being the post-frontmatter text. `check_features` and
`check_modified_stamp` consume it directly. Crucially, the vaultcore parser does
NOT surface `step_id`: `parse_vault_metadata` populates `date`, `modified`,
`superseded_by`, `archived`, `tags`, `related`, etc. (`parser.py:177-194`) but has
no `step_id` branch, and `DocumentMetadata` (`models.py:295`) has no such field.
The dict-returning `parse_frontmatter(content) -> (dict, body)` (`parser.py:91`)
does expose arbitrary keys including `step_id`. So the exec checker either reads
`step_id` via `parse_frontmatter` per exec doc, or the model gains a first-class
`step_id` field. The exec template confirms the two anchoring fields:
`step_id: '{step_id}'` in frontmatter and the parent plan as a
`related: ['[[{plan_stem}]]']` wiki-link (`.vaultspec/templates/exec-step.md`),
both machine-filled by `vaultspec-core vault add exec`.

### Exec-to-plan back-mapping (#233) has a ready data path via `parse_plan`

A plan document parses to a `Plan` model exposing every live Step id and every
retired id: `Plan.steps[].canonical_id` (`src/vaultspec_core/plan/parser.py:61`,
`138-178`) and `Plan.retired_step_ids: set[str]` (`parser.py:176`), the latter
persisted in a hidden comment ledger so retirement survives round-trips. The
`Step.canonical_id` is the leaf `S##`. `parse_plan(source)` accepts a path or
text (`parser.py:209`). So #233 resolves, per exec record: the parent plan (from
the `related:` plan-stem link, or by locating `.vault/plan/<stem>.md`), then
`parse_plan` it, then classify `step_id` as live (in `canonical_id` set),
retired (in `retired_step_ids` -> finding), or absent (dangling -> finding);
a missing plan file is its own finding. `get_doc_type` (`scanner.py:111`)
classifies exec docs by their `.vault/exec/` location.

### Archived parents are the sharp #233 edge: the scanner hides `_archive`

`scan_vault` skips any path containing `_archive` (`scanner.py:70`), so the graph
and snapshot never contain an archived plan. A naive "plan not in snapshot ->
missing" rule would therefore misreport every exec record whose plan was archived
(the expected, benign steady state) as a dangling defect. #233 must probe
`.vault/_archive/plan/<stem>.md` on disk before emitting a missing-plan finding,
distinguishing an archived parent (expected; INFO or silent) from a truly-absent
one (defect). Archived exec records themselves are already out of scope because
the scanner hides them.

### Legacy exec records without `step_id` are unmappable, not defective

Exec records created before the `step_id` field existed carry no canonical id to
resolve. The checker cannot back-map them and must skip them (no finding, or at
most INFO) rather than flag absence as a dangling reference; flagging would flood
legacy corpora. This mirrors how `check_modified_stamp` treats a fresh-clone
signature as a systemic condition to suppress rather than a per-doc defect
(`checks/modified_stamp.py`).

### Template-mandated sections (#234) are derivable H2 headings, per doc type

Each shipped template carries a fixed set of `##` section headings that
constitute its body contract. Enumerated from `src/vaultspec_core/builtins/templates/`:
adr -> Problem Statement, Considerations, Considered options, Constraints,
Implementation, Rationale, Consequences (`adr.md:51-90`); plan -> Description,
Steps, Parallelization, Verification (`plan.md:102-172`); research -> Findings,
Sources (`research.md:42-51`); reference -> Summary (`reference.md:37`); audit ->
Scope, Findings, Recommendations (`audit.md:32-47`); exec-step -> Description,
Outcome, Notes (`exec-step.md:47-53`); exec-summary -> Description
(`exec-summary.md:45`); index -> Documents (`index.md:27`, auto-generated, out of
scope). The H1 lines carry placeholders (`# {feature} adr: {title}`) but the H2
section titles are literal, so a template-driven checker derives the required set
by extracting `##` headings from the template body with no hardcoding.

### #234 reuses the existing template-resolution seam

Templates resolve at runtime from `root_dir / framework_dir / "templates"` (i.e.
`.vaultspec/templates/`) via `get_template_path` (`hydration.py:553-593`), and the
`DocType -> filename` map already exists as `_TEMPLATE_NAMES`
(`hydration.py:33-41`), with exec's second template (`exec-summary.md`) handled by
a `summary` selector (`hydration.py:52`). #234 reuses this map and resolution so
the templates remain the single source of truth. A missing or unreadable template
(uninstalled or corrupted `.vaultspec/`) must degrade gracefully (skip that doc
type, optional INFO), never crash - consistent with the "No-Crash" policy.

### #234 must detect empty sections, not just absent headings

The acceptance criterion is "absent OR empty." A present `## Consequences` with no
prose before the next heading is still a defect. So the checker parses the doc
body into heading-delimited sections and, for each required heading, verifies both
presence and non-whitespace content up to the next `##` (or EOF). Author-added
extra sections are tolerated; only the absence or emptiness of a required section
is a finding. Plans are the tier-conditional case: the four plan H2s are present
at every tier (only their content shape varies), so heading-presence still holds,
but the ADR should confirm whether `Parallelization` is required at `L1`.

### Nearest analogues confirm the shape and that neither gap is covered

`check_features` (`features.py:67`) is feature-level presence (exec-without-plan,
plan-without-ADR) - not per-record step resolution. `check_schema`
(`references.py:217`) enforces cross-reference edges (ADR grounded by research,
plan governed by ADR) - it inspects `related:` links, never Step ids or body
headings. `check_structure` (`structure.py:338`) enforces directory and filename
conventions only. Both new checkers are genuinely new surface. `check_schema`
also demonstrates the read-only-vs-fix boundary: it offers `--fix` only because a
missing `related:` link has an unambiguous auto-repair (add the wiki-link). No such
unambiguous repair exists for a dangling `step_id` (the correct target is unknown)
or a missing body section (position, ordering, and content are the author's), so
both new checkers are read-only, which the ADR should ratify.

### One integration seam, two validators: a single ADR is the natural unit

Both validators share every integration concern - registration in
`run_all_checks`, `CheckResult`/`CheckDiagnostic` emission, snapshot/graph
consumption, feature filtering, read-only status, archived-doc handling, and a
real-filesystem per-doc-type test strategy - and both descend from the same
Phase 3 of the `vault-api` plan. They differ only in data source (plan parser vs
templates) and locus (cross-document vs in-document). The codebase already
co-locates sibling checkers in one module (`references.py` holds both
`check_references` and `check_schema`). The evidence favors one ADR deciding both,
with two clearly-delineated validator decisions, over two ADRs duplicating the
integration boilerplate; the ADR should confirm this and may still land them as
two separate checker functions/modules.

## Sources

- `src/vaultspec_core/vaultcore/checks/_base.py:20,38-64` - `CheckResult`,
  `CheckDiagnostic`, `Severity`, `VaultSnapshot` contract.
- `src/vaultspec_core/vaultcore/checks/__init__.py:74-210` - `run_all_checks`
  registration, graph/snapshot threading, read-only checker precedent.
- `src/vaultspec_core/vaultcore/checks/features.py:67,122-154` - feature-level
  presence checker (nearest analogue, not back-mapping).
- `src/vaultspec_core/vaultcore/checks/references.py:217-425` - `check_schema`
  cross-reference rules and `--fix` boundary.
- `src/vaultspec_core/vaultcore/checks/structure.py:338` - structure/filename
  checker (no heading logic).
- `src/vaultspec_core/vaultcore/parser.py:91,177-194` - `parse_frontmatter` dict
  vs `parse_vault_metadata`; no `step_id` branch.
- `src/vaultspec_core/vaultcore/models.py:295` - `DocumentMetadata` fields.
- `src/vaultspec_core/plan/parser.py:61,176,209` - `Step.canonical_id`,
  `Plan.retired_step_ids`, `parse_plan`.
- `src/vaultspec_core/vaultcore/scanner.py:70,111` - `_archive` exclusion,
  `get_doc_type`.
- `src/vaultspec_core/vaultcore/hydration.py:33-41,52,553-593` - `_TEMPLATE_NAMES`,
  exec-summary selector, `get_template_path` resolution.
- `.vaultspec/templates/` (adr.md:51-90, plan.md:102-172, research.md:42-51,
  reference.md:37, audit.md:32-47, exec-step.md:47-53, exec-summary.md:45,
  index.md:27) - the per-type required H2 section sets.
- Issues #233, #234; provenance `.vault/plan/2026-02-08-vault-api-plan.md`
  Phase 3.
