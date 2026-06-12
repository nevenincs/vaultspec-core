---
tags:
  - '#research'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
related: []
---

# `vault-orientation` research: `rich status and grounding cli`

Research grounding a planned orientation surface: a rich status and grounding CLI
(working verb name `vaultspec-core vault status`) that lets an agent or developer
landing in an unknown vaultspec-managed project answer four questions without prior
context: what work has been done, what is currently active, what changed most recently,
and - for one chosen plan - which steps, execution records, and grounding documents
(ADR, research, reference) belong to it. The feature is conceptually distinct from
auditing: it is descriptive orientation (`git status`), not conformance judgment
(`vault check`) and not implementation review (the Verify phase). This research surveys
the existing backend capability and frames the design options the ADR must decide.

## Findings

### Existing backend capability

The backend already holds most of the ingredients:

- **Document scan layer** (`vaultcore/query.py`): `list_documents` filters by type,
  feature, and date; `list_feature_details` returns per-feature doc counts, types,
  `earliest_date`, and `has_plan`; `get_stats` backs `vault stats`.

- **Graph API** (`graph/api.py`): `VaultGraph` builds a `networkx.DiGraph` from body
  wiki-links and `related:` frontmatter. Nodes carry doc type, feature, date, tags, raw
  frontmatter, and - decisively - `in_links` as well as `out_links`, so reverse
  traversal (plan to its referencing exec records) works today. `ego_subgraph` is a
  ready-made primitive for the single-plan grounding view, and a fingerprint cache
  (`graph/cache.py`) makes repeated builds cheap.

- **Plan introspection** (`plan/parser.py`, `plan/status.py`, `plan/query.py`):
  `parse_plan` yields the full Wave/Phase/Step tree with canonical ids, display paths,
  and checked state; `collect_status` computes per-plan completion and already performs
  the reverse exec-record lookup (`exec_missing_ids` matches exec `step_id:` frontmatter
  against checked steps); `query_steps` filters step rows by container scope and
  open/closed state.

- **Exec linkage is dual and machine-precise**: `vault add exec` writes both
  `step_id: 'S##'` frontmatter and a `related:` wiki-link to the parent plan stem. The
  minimum-linkage assumption holds: as long as records are scaffolded through the CLI,
  the plan-to-record graph is constructible regardless of body prose quality.

- **Archive state is positional**: archived features live under `.vault/_archive/`;
  "active" is derivable as not-archived plus has-a-plan-with-open-steps, but nothing
  computes it today.

- **Output conventions are settled**: `cli/rendering.py` provides the versioned
  `--json` envelope every verb uses; read-only verbs report the `unchanged` outcome.

### Gaps the feature must close

- **No recency signal on documents.** Models carry only the frontmatter `date:`
  (creation-day semantics). File mtime exists in the graph cache fingerprint manifest
  but is not exposed as a query API. Sub-document recency (which step changed last) does
  not exist at all.

- **No cross-plan enumeration API.** `collect_status` is single-plan and re-scans exec
  documents per call; a naive all-plans loop is O(plans x exec files). A batched helper
  (parse all plans once, index exec `step_id:` once) is needed.

- **No rollups**: nothing computes plans-in-flight, open-step counts across the vault,
  per-phase/per-wave completion, or per-feature latest activity.

- **Traceback is ad hoc**: plan-to-exec reverse lookup exists twice (feature-scoped
  scan in `plan/status.py`; graph `in_links` by stem) but there is no first-class API
  keyed by the Step canonical id, and graph neighbours are not classified by doc type
  for a grounding view.

### Design option space for "recent"

The ADR must decide what "recent" means. Candidate semantics:

- **Frontmatter date (status quo)**: zero new code; day granularity; creation-time
  semantics, so a long-running plan edited daily never surfaces as recent. Insufficient
  alone.

- **File mtime at scan time**: stat each file during the vault scan (or reuse the graph
  cache fingerprint, which already records mtime). Cheap, no new persistence, captures
  edits. Fragile across `git clone` and fresh checkouts (mtime resets to checkout time)
  and bulk reformat commits.

- **Git history**: `git log` per path gives true last-change time and survives clones.
  Requires a git repo and subprocess calls; slower; the vault is not guaranteed to be
  git-tracked in every deployment.

- **Window shape**: independent of the source signal, recency can be presented as a
  time window ("last N days") or as a count ("last N modified"). A count is stable in
  low-activity repos (always returns something) and bounded in high-activity ones; a
  time window answers "what happened since I left" better. These compose: a count
  default with an optional window flag.

### Design option space for traceback / grounding

- **Graph-based** (preferred candidate): compose the graph's incoming and outgoing
  edges filtered and grouped by doc type: the plan node's incoming exec records, plus
  outgoing `related:` edges to ADR / research / reference. Single code path, already
  cached, handles arbitrary linkage depth.

- **Scan-based**: extend `collect_status` to return the exec-record paths it already
  matches by step id, and read the plan's own `related:` frontmatter for grounding
  documents. Simpler, no graph dependency, but duplicates traversal logic and misses
  documents linked indirectly.

- **Step-level mapping**: either approach can be enriched to key exec records by
  `step_id:` so the output maps each step to its record path; the parse layer already
  exposes both sides.

### Surface shape candidates

- One verb, two modes: `vault status` (vault-wide rollup) and a targeted form taking a
  plan or feature (single-target grounding trace). Mirrors `git status` ergonomics.
- Two verbs: a rollup-only `vault status`, with drill-down delegated to the existing
  `vault plan status` and `vault graph` verbs. No new drill-down code, but the agent
  must learn three commands and stitch output.
- Placement: top-level under `vault` (orientation is vault-scoped, not plan-scoped);
  the existing `vault plan status` remains the deep single-plan validator.

### Firmware implication (codification follows implementation)

The enrolled behaviour - "task in an unknown project: run the orientation verb first" -
must be an always-on rule mandate, not a skill, because an agent without project context
cannot be expected to select a skill. Codifying that mandate is gated on the verb
shipping; the firmware-reference-parity rule forbids naming unshipped verbs in firmware
prose. Sequence: implement the verb, then codify the bootstrap mandate in the same
release.

### Recommendation

Build the rollup as a new read-only `vault status` verb composing existing layers
(batched plan parse plus the `collect_status` core plus the graph for grounding), source
recency from file mtime with frontmatter date as fallback, present recency as
last-N-modified by default with an optional day-window flag, and ship the firmware
bootstrap mandate in the same change that ships the verb. Decide the exact output
contract, recency semantics, and verb grammar in the ADR.
