---
tags:
  - '#audit'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:924839a7061d0868470bfd3ef54448ad0239f7b412510bdbaede00a8736b4dd3'
related:
  - "[[2026-06-28-curator-reframe-adr]]"
  - "[[2026-09-23-adr-crossref-adr]]"
  - "[[2026-09-08-framework-reword-adr]]"
---

# `skill-audit` audit: `Standalone curation scope and authority audit`

## Scope

Audit of the bundled `vaultspec-curate` skill, its reconciliation and status references,
`vaultspec-docs-curator` persona, and supporting status-check and cross-reference code.
The user requested review and implementation of findings without further control.
No vaultspec skill was invoked. This is a targeted framework audit, not a curation of
the entire project vault. Existing accepted decisions cover the repairs; no new plan
or costly architecture choice is required.

## Findings

### stale-authority | high | A quoting repair could overwrite a newer decision status

`src/vaultspec_core/vaultcore/checks/adr_status.py:97` previously reread the document
under its write lock but applied the token from an older snapshot. A real-filesystem
probe changed an accepted on-disk ADR back to proposed. Resolution: compare the current
marker with the observed status under the same lock; do not write when authority changed
or quoting is already correct. Regression cases protect accepted quoted/unquoted states
and an already-correct proposed state, including bytes and stamps.

### evidence-history | high | Boundary repairs could erase historical recommendations

The previous playbook authorized dropping a grounding record's conclusion whenever an
accepted ADR disagreed. Decision authority does not invalidate empirical findings or
historical options. Resolution: preserve dated recommendations, alternatives and
observations; clarify their historical role when necessary. Only redundant claims of
current authority with identical substance may be replaced by a source citation.
Conflicting observations remain findings. The skill, playbook and persona agree.

### status-ambiguity | high | Mechanical normalization could invent authority

The previous guidance grouped missing and unknown statuses with mechanically safe
normalizations. It also required mechanical cleanliness before completion. Resolution:
only established state can be normalized; unknown or conflicting authority is recorded
until evidence resolves it. No inference from code implementation or a nearby status
value establishes approval. Existing scoped authorization is reusable.

### status-detection | medium | Conflicting declarations and missing successors were invisible

The checker returned clean for a canonical accepted H1 followed by a legacy Rejected
status section, and for a superseded H1 with no successor metadata. Resolution:
`src/vaultspec_core/vaultcore/checks/adr_status.py:151` reports legacy sections even when
an H1 marker exists; the checker also reports the reverse supersession mismatch.
Both remain warnings, with no inferred status or relationship repair. Diagnostic advice
no longer prescribes replaying supersession to repair an ambiguous historical chain.

### scope-and-termination | medium | Repeated global cleanup defeated bounded curation

The skill, persona and playbook repeated full-vault repair, code-index provisioning,
mandatory delegation and rescan-until-clean instructions. These could expand a scoped
review and prevent termination on unrelated findings. Resolution: standalone user-started
maintenance, optional delegation with one owner, read-only structural diagnosis, scoped
authorized repairs, one affected-scope verification, and explicit partial checkpoints.
RAG unavailability uses existing fallback rather than an indexing prerequisite.

### recall-and-cost | medium | Inventory and hosted coverage could be overstated

The prescribed listing returned 50 of this vault's 134 ADRs, with `next_offset: 50`;
following that cursor returned the remaining 84. The old workflow omitted pagination,
repeated the same hosted refusal procedures in three places, and conflated sweeps with
semantic review. Resolution: follow listing pagination, use one default hosted batch
unless a larger budget is assigned, continue only within that budget, preserve the
backend's cursor, and record input clipping, omitted verdicts and unscored sources.
No extra paid refusal probes or sweeps solely to recover omitted reply rows are mandated.
Graph supersession is read from node frontmatter, not inferred from ordinary links.

### retired-sources | medium | Automatic sweeps spent requests on deprecated decisions

`src/vaultspec_core/crossref/_service.py:75` excluded superseded and rejected sources
but included deprecated ones despite the canonical retirement semantics. Resolution:
automatic selectors exclude all three. Explicit names still allow historical-source
review, and candidates retain all statuses. Parameterized real transport tests cover
retirement, cursor counts, isolation and explicit inclusion. CLI, MCP and references
describe non-retired sources including proposals without implying proposals govern.

### instruction-duplication | low | The persona repeated the whole reconciliation method

The four bundled guidance files contained 4,674 whitespace-delimited words. The revised
set contains 2,227 before Markdown table formatting, a 52.4 percent reduction. The skill
owns workflow, the playbook owns comparison and repair rules, the taxonomy explains the
core enum, and the persona owns assignment and return behavior. This measures wording,
not runtime token savings or improved agent accuracy.

## Recommendations

Keep standalone curation and ADR authoring as separate entry points with shared decision
authority. Use reported coverage to plan a continuation, not as a fresh approval gate.
Preserve empirical and historical evidence while reconciling claims of current authority.
No new service, hook, persona, or automatic pipeline gate is warranted by this audit.

## Validation

Seven regression cases failed before the code fixes; the focused status/service suite
then passed all 43 tests. The covering run passed 151 tests across status checking,
repair locking, enum behavior, cross-reference corpus/service/sweep safety, CLI, MCP,
context budgets and test-quality guards. The 18 lightweight repository guards passed.
Ruff, type checking, Markdown lint and generated-reference checks passed. No paid model
spike was repeated: these defects have deterministic local reproductions. Broader agent
productivity and semantic conflict accuracy remain unmeasured.
