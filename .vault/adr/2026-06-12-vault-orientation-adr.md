---
tags:
  - '#adr'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-vault-orientation-research]]'
---

# `vault-orientation` adr: `vault status orientation surface` | (**status:** `accepted`)

## Problem Statement

An agent or developer landing in an unknown vaultspec-managed project has no single
command that answers: what work has been done, what is currently active, what changed
most recently, and how to trace one plan back through its steps, execution records, and
grounding documents. The primitives exist (document scan, graph API with bidirectional
edges, per-plan status with exec-record matching) but no rollup composes them, and the
enrolled bootstrap behaviour cannot be codified into firmware until the verb it names
actually ships. This ADR decides the orientation surface: verb grammar, recency
semantics, traceback mechanism, output contract, and the firmware mandate's sequencing.

## Considerations

- The surface is orientation, not auditing: descriptive, read-only, no artifact, no
  findings, no fix path. It precedes pipeline phase 1 and must be free to run.
- The grounding research catalogued the option space. Recency source: frontmatter date
  vs file mtime vs git history. Recency window: last-N-modified vs day window. Traceback
  mechanism: graph-based vs scan-based vs step-keyed enrichment. Surface shape: one verb
  with two modes vs rollup-only verb delegating drill-down.
- Exec records scaffolded through the CLI always carry `step_id:` frontmatter plus a
  `related:` link to the plan stem, so plan-to-record tracing can assume that minimum
  even when body prose quality varies.
- Performance: the vault in this repository holds ~700 documents and ~60 plans; the
  rollup must batch (parse plans once, index exec records once) rather than loop the
  existing single-plan status routine.
- Output must follow the established versioned JSON envelope and read-only outcome
  vocabulary so agents parse it like every other verb.

## Constraints

- Filesystem-inferred recency is unstable: file mtime does not survive `git clone`,
  and git history cannot be assumed present in every deployment. A recency source must
  either travel with the document or degrade gracefully and visibly.
- Step-level recency (which step row changed) has no stored signal at any layer; only
  document-level recency is implementable without content diffing or git blame. The
  decision must scope "last modified steps/waves/phases" to "within the last-modified
  plans" rather than promise per-row timestamps.
- Traceback fidelity depends on CLI-scaffolded linkage. Hand-written exec records
  missing `step_id:` or the plan link degrade the trace; the verb must report such
  records as unlinked rather than silently omit them.
- The firmware-reference-parity rule forbids naming unshipped verbs in firmware prose:
  the bootstrap mandate can only land with or after the verb, never before.

## Implementation

Decisions, stated as the option chosen and its shape:

- **D1 - Verb grammar: one verb, two modes.** `vaultspec-core vault status` with no
  argument renders the vault-wide rollup; `vaultspec-core vault status <target>` (a
  plan stem, plan path, or feature tag) renders the grounding trace for that target.
  Mirrors `git status` ergonomics; one command to teach the bootstrap mandate. The
  existing `vaultspec-core vault plan status` remains the deep single-plan validator
  and is unchanged.

- **D2 - Rollup content.** The no-argument mode reports: active features (non-archived,
  ordered by latest activity); plans in flight (plans with at least one open step) with
  open/closed step counts and completion percent; recently modified documents grouped
  by type; and totals echoing the existing stats. One trailing hint line points at
  `vaultspec-core spec doctor` for health, keeping orientation and conformance
  separate.

- **D3 - Recency source: a CLI-maintained `modified:` frontmatter stamp.** Documents
  gain a `modified:` frontmatter field (`yyyy-mm-dd`, same granularity as `date:`),
  set equal to `date:` at scaffold time and refreshed by every CLI verb that mutates
  the document: the plan structural and state mutators, `vault adr supersede`,
  `vault link add/remove`, the repair and fix paths, and `vault rule promote` on its
  source audit. The existing `date:` keeps creation semantics; `modified:` carries
  lifecycle semantics (created, revised, superseded, retired all refresh it). Recency
  in the status rollup reads `modified:` first and falls back to `date:`; raw file
  mtime is never presented as recency. Manual body-prose edits (the permitted edit
  path) are reconciled by `vault check all --fix`: when a document's content
  fingerprint is newer than its stamp, the fix path refreshes `modified:` - stamping
  stays CLI-owned while hand edits still surface. A schema migration backfills
  `modified:` from `date:` on existing documents. File mtime and git history are
  rejected as recency sources: mtime does not survive `git clone`, git cannot be
  assumed present, and both infer what the vault can simply record.

- **D3a - The stamp is schema-documented, not rule-codified.** The `modified:` field
  joins the frontmatter schema in the `vaultspec` rule's schema section, the shipped
  templates' FRONTMATTER RULES comments, and the curator's allowed-keys list, so the
  field is recognized everywhere frontmatter is validated. No standalone builtin rule
  ships for it: the CLI enforces the discipline, and a rule restating an
  implementation-enforced invariant is tautological context cost for agents.

- **D3b - Lenient stamp parsing, canonical normalization.** Because body-prose hand
  edits are permitted, no assurance exists that a hand-touched `modified:` (or `date:`)
  value stays canonically formatted. Every consumer of the stamp - `vault check`,
  `vault check all --fix`, `vaultspec-core spec doctor`, the backfill migration, and
  the status rollup's recency sort - parses dates leniently (ISO variants, full
  timestamps, common orderings), and the fix path rewrites whatever it parsed back to
  the canonical quoted `yyyy-mm-dd` form. A value no parser recognizes is flagged as a
  check finding, never silently dropped, and the status rollup falls back to `date:`
  for that document.

- **D4 - Recency window: last-N default, day-window flag.** The rollup shows the last
  10 modified documents by default (`--limit N` adjusts). A `--since <days>` flag
  switches to a day-window query. Count default because it always returns something in
  low-activity repos; window flag because "what happened since I left" is the second
  most common orientation question.

- **D5 - Traceback mechanism: graph-backed, simply rendered.** The targeted mode uses
  the graph API internally (the target plan node's incoming edges yield its exec
  records; outgoing `related:` edges yield grounding documents grouped by doc type) but
  the graph never leaks into the output: no edge lists, no metrics, no node-link JSON.
  The rendering is a flat orientation listing - each plan step (canonical id, display
  path, open or closed) mapped to its exec-record stem, or "no record" for open steps,
  or "unlinked" for records that reference the plan without a resolvable step id,
  followed by the grounding stems grouped by type. Exec records are keyed by their
  `step_id:` frontmatter. A feature-tag target renders the same trace for every plan
  under the feature. The contract: simple command in, simple response out - the
  response orients, links, and grants discovery; the agent reads the named files with
  its own tools.

- **D6 - Batched status core.** A new backend helper enumerates all plans in one pass,
  parses each once, and builds a single exec-record index keyed by feature and step id;
  the existing single-plan status routine is refactored to consume the shared core
  rather than re-scanning per call.

- **D7 - Output contract: stems plus hints, no graph surface.** Human output is a
  compact rendering ordered: in-flight plans first, then recent changes, then totals.
  Every listed document renders as a stem the agent can open directly with file-read
  tools. Deeper inspection is delegated through advisory hint lines (the established
  hints mechanism): the rollup hints at the targeted mode and at
  `vaultspec-core spec doctor`; the targeted mode hints at
  `vaultspec-core vault graph` for full graph exploration and at
  `vaultspec-core vault plan status` for deep single-plan validation. `--json` emits
  the versioned envelope with `unchanged` outcome semantics and carries the same hints
  field.

- **D8 - Firmware bootstrap mandate ships with the verb.** The same change that ships
  the status verb adds the enrolled behaviour to the always-on firmware: before
  starting work in a vaultspec-managed project with no session context, run
  `vaultspec-core vault status` and read the in-flight plans it names. The mandate
  lives in the framework rule and system fragment, phrased as the zeroth move
  (orientation), explicitly not a pipeline phase and producing no artifact.

## Rationale

The grounding research showed every load-bearing primitive already exists - the graph's
bidirectional edges make traceback a composition problem, not a storage problem - so
the design composes rather than introduces storage - with one deliberate exception:
the `modified:` stamp. Recency is the one fact the vault cannot compose because
nothing records it; mtime and git both infer it unstably, while a CLI-maintained
frontmatter stamp travels with the document through clones, archives, and provider
syncs, and turns lifecycle events (supersede, revise, retire) into queryable data. One
verb with two modes was chosen over delegated drill-down because the bootstrap mandate
must be teachable in one sentence to an agent with zero context. Graph-backed
traceback was chosen over extending the scan-based status routine because it yields
indirect grounding links for free and keeps one traversal code path - while the
simple-output contract keeps the graph an implementation detail: orientation output is
stems and hints, and the agent's own file tools do the reading.

## Consequences

- Agents gain a single, cheap, read-only entry point; the unknown-project cold start
  stops depending on tribal knowledge.
- The batched status core (D6) removes the per-call rescan cost from any future caller,
  benefiting the existing single-plan verb too.
- The `modified:` stamp is a vault-wide schema change: templates, the frontmatter
  schema in the `vaultspec` rule, the curator's allowed-keys list, every mutating CLI
  verb, and a backfill migration all move in one release. Day granularity keeps the
  stamp diff-friendly but means same-day ordering falls back to document order.
- Stamp freshness depends on the CLI-owned mutation discipline already mandated;
  body-prose edits surface through the `vault check all --fix` reconciliation rather
  than in real time.
- Step-to-record mapping makes missing or unlinked exec records visible in routine
  orientation output, which will surface scaffolding-discipline drift earlier than
  audits currently do - mildly noisy at first in vaults with hand-written records.
- Two status verbs coexist (vault-wide and single-plan); the names are consistent in
  scope but documentation must state the distinction once.

## Codification candidates

- **Rule slug:** `orientation-before-work`. **Rule:** Before starting work in a
  vaultspec-managed project you have no session context for, run
  `vaultspec-core vault status` and read the in-flight plans it names before invoking
  any pipeline skill. (Gated on D8: codify only in or after the change that ships the
  verb, per the firmware-reference-parity rule.)

- The `modified:` stamp discipline is deliberately NOT a codification candidate. The
  CLI sets, refreshes, normalizes, and repairs the stamp; a builtin rule restating
  what the implementation enforces would be tautological context cost. Schema
  documentation (templates, the `vaultspec` rule's schema section) suffices.
