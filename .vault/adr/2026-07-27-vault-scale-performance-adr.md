---
tags:
  - '#adr'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
related:
  - "[[2026-07-27-vault-scale-performance-audit]]"
  - '[[2026-06-10-graph-backend-adr]]'
  - '[[2026-06-13-vault-graph-ref-adr]]'
  - '[[2026-06-12-vault-orientation-adr]]'
  - '[[2026-06-13-cli-output-standardization-adr]]'
  - '[[2026-07-23-vault-check-validators-adr]]'
---

# `vault-scale-performance` adr: `large-vault performance architecture` | (**status:** `accepted`)

## Problem Statement

At one order of magnitude past the graph design envelope, the read-side verbs
degrade superlinearly: on a 12k-document production corpus, `vault graph`,
`doctor`, and `vault check all` are minute-class commands, and one documented
remediation path arms a further ~90s regression
(`2026-07-27-vault-scale-performance-audit`). The audit shows the causes are not
scattered inefficiencies but a small set of recurring architectural patterns: a
metrics API that conflates cheap counts with expensive analysis, a check pipeline
that re-ingests a corpus it already holds in memory, cache validation that costs
more than the cache saves, workspace-global facts recomputed per document, and
render surfaces with no volume policy. Each validated fix is behaviour-preserving,
so what needs deciding is not whether to fix them but which standing positions
prevent the same classes of defect from recurring. The prior graph decision
(`2026-06-10-graph-backend-adr`) explicitly scoped its performance posture to
roughly 5,000 documents; production corpora have outgrown that scope, and its
fingerprint-cache design has drifted in implementation. This record extends the
performance architecture to the measured 12k-document scale and resolves the
drift.

## Considerations

- Every optimization named in the grounding audit was validated byte-identical to
  baseline output, so these are architectural positions over proven refactors,
  not speculative rewrites (`2026-07-27-vault-scale-performance-audit`).
- `2026-06-10-graph-backend-adr` specified the fingerprint cache keyed on
  `(st_size, st_mtime_ns)`; the shipped `fingerprint_vault` hashes every file
  unconditionally. The implementation drifted stricter and slower than the
  accepted design; this record must resolve the divergence explicitly rather than
  leave two contradictory authorities standing.
- `2026-06-13-vault-graph-ref-adr` codified that ref-scoped reads bypass the
  worktree cache entirely; any cache policy decided here must leave that boundary
  untouched.
- `2026-06-12-vault-orientation-adr` decision D6 already mandates a batched
  status core (one plan pass, one exec index); the corpus-rescan behaviour the
  audit measures is drift from that decision, not a gap in it.
- `2026-06-13-cli-output-standardization-adr` already rules that truncation must
  be fixed and marked and that `--json` is the machine contract; a report volume
  policy extends that contract rather than inventing a new one.
- `2026-07-23-vault-check-validators-adr` ratified `step_id` as a first-class
  snapshot field precisely so checkers read the snapshot instead of re-parsing
  files; the single-ingress contract generalizes that ratified direction to the
  whole check suite.
- The no-mock testing mandate and the never-commit-fixtures rule constrain how a
  scale regression gate can be built; `vaultspec_core.testing.synthetic` is the
  canonical generator for synthetic corpora.
- Filesystem mtime resolution varies by platform: nanosecond on NTFS and ext4,
  two seconds on FAT-class filesystems. Any stat-trusting cache policy must state
  its residual risk in those terms.

## Considered options

- **Cache validation.** (a) Hash-always status quo: strongest soundness, but the
  validation costs more than the cache saves at scale, and it contradicts the
  accepted stat-keyed design. Rejected. (b) Pure stat-trust, never hash: cheapest,
  but silently wrong for a same-size edit inside one mtime tick with no bounded
  mitigation. Rejected. (c) Stat-trust with a racily-clean window - trust
  size+mtime, hash only files whose mtime falls within the cache-write tick - the
  resolution proven by git for the identical problem. Chosen. (d) Drop the cache:
  simplest, but forfeits the warm path entirely just as corpus scale makes it
  matter most. Rejected.
- **Metrics API.** (a) Leave `metrics()` conflated and patch `render_tree` to
  count directly: fixes one caller, leaves the trap armed for the next. Rejected.
  (b) Memoize `metrics()`: hides the cost on repeat calls but the first caller
  still pays O(V\*E) for three numbers. Rejected. (c) Split descriptive counts
  from graph-theoretic analysis into separate surfaces, analysis strictly opt-in.
  Chosen.
- **Check pipeline.** (a) Fix each offending checker ad hoc: addresses today's
  five, does nothing to stop the sixth. Rejected. (b) Parallelize the check suite:
  spends cores to mask redundant work and multiplies the I/O storm. Rejected.
  (c) A single-ingress contract - every checker consumes the shared snapshot,
  enforced structurally and by test. Chosen.
- **Workspace-global reads.** (a) Memoize the baseline ledger as a one-off patch:
  fixes the instance, not the class. Rejected. (b) A standing run-scope rule for
  all per-workspace facts, with the ledger as its first application. Chosen.
- **Scale regression gate.** (a) No gate: the audit is proof these regressions
  land silently. Rejected. (b) Wall-clock CI thresholds on a large corpus: flaky
  across runners and slow to execute. Rejected. (c) Complexity budgets asserted
  as operation counts and scaling ratios over generated synthetic corpora under
  a dedicated marker. Chosen.
- **Report volume.** (a) Leave unbounded: 4.3MB of terminal output at scale.
  Rejected. (b) Page interactively: breaks the LLM-first output contract.
  Rejected. (c) Fixed caps with marked truncation and aggregates, full detail
  under `--json`. Chosen.
- **Native acceleration.** (a) A dedicated C calculation engine: rejected -
  it duplicates actively-evolving semantics (parsers, checkers, the
  racily-clean rule) into a second implementation that must stay
  byte-identical, breaks the pure-Python distribution story, and its
  wall-clock advantage over the accepted architecture plus deferred
  incremental work falls below human-perceptible CLI latency. (b) Native
  leaf libraries behind existing seams: the libyaml-backed frontmatter
  loader (already shipped on the parse hot path with a pure-Python
  fallback) and a C-backed graph library for the opt-in analysis surface,
  each falling back to the pure implementation when the wheel is absent.
  Chosen.

## Constraints

- Behaviour preservation is the hard boundary: every change under this record
  must keep verb output byte-identical for the human surface and
  schema-identical for `--json`, except where a decision below explicitly
  changes a surface (report caps, opt-in analysis) - those follow the codified
  json-schema-version-discipline rule (bump the schema version, ship the
  contract test in the same change).
- Parent features are stable: the graph cache module, the snapshot and hydration
  seam, the plan parser, and the output contract are all mature, shipped, and
  test-covered. No frontier risk; the only dependency added is the D8
  analysis library, a mature binary-wheel package guarded by a pure-Python
  fallback so no platform loses functionality.
- The CLI startup floor of 0.45s bounds the attainable minimum for any verb.
- Ref-scoped reads must remain cache-off and migration-free per the codified
  ref-scoped-reads-bypass-worktree-cache rule; the cache policy here applies to
  working-tree reads only.
- The racily-clean window is only sound if every cache write records its own
  timestamp with the same resolution as the filesystem it guards; on
  coarse-resolution filesystems the window, and therefore the re-hash set,
  grows accordingly.
- The scale gate depends on `vaultspec_core.testing.synthetic` generating
  corpora at test time; corpus fixtures are never committed.
- The snapshot must gain raw bytes for the encoding fold-in without doubling
  resident memory; carrying bytes and lazily decoding, or carrying both for the
  ingress pass only, is an implementation choice the plan must settle within
  this contract.

## Implementation

Seven decisions, each a standing position.

**D1 - Cache validation adopts the racily-clean rule.** The cache manifest keys
on `(st_size, st_mtime_ns)` per file, as the accepted graph design specified. A
file whose size and mtime match the manifest is trusted without hashing, except
files whose mtime falls within the manifest-write tick, which are content-hashed
before being trusted. A fingerprint mismatch still falls back to a full rebuild,
never a partial trust. The residual risk accepted: a same-size edit that lands
in the same mtime tick as the cache write and bypasses the mutating verbs is
served stale until the next touch; on nanosecond-resolution filesystems (NTFS,
ext4) that window is vanishingly small, and on coarse-resolution filesystems the
racily-clean re-hash set covers it by construction. A full-hash validation path
remains available as an explicit deep-verification option for doctor-class
diagnostics, not as the default.

**D2 - Descriptive counts and graph analysis are separate API surfaces.** The
graph API exposes cheap descriptive counts (documents, links, features) as a
surface that is O(V+E) or better and safe to call from any render path.
Graph-theoretic analysis (centrality, link prediction, node-size hints) moves
behind an explicitly named opt-in surface that no render or title path calls
implicitly. The wire envelope carries analysis only where its consumer contract
requires it, and any envelope shape change rides the schema-version discipline.
The enforcement is structural: after the split, the expensive surface has no
callers outside the paths that explicitly requested analysis, and a test asserts
the render paths complete without invoking it.

**D3 - The check pipeline has a single-ingress contract.** Ingress reads each
document exactly once and produces the shared snapshot; the calculate phase runs
entirely from it. The snapshot carries what checks actually need: decoded
content, raw bytes (so the encoding check folds into the one read instead of a
sixth pass), the frontmatter fields already ratified as first-class, and the
per-file metadata (size, path-derived type) that today's checks re-stat for.
Every checker signature takes the snapshot; registration of a checker that does
not is a contract violation. Enforcement is by test: the check suite runs once
against a corpus that is made unreadable after ingress, and any checker that
touches disk in the calculate phase fails loudly. Within-check redundancy falls
under the same contract: per-record loops memoize per-run parses (the plan
step-id case) instead of re-deriving them.

**D4 - Workspace-global facts are read once per run.** Any fact scoped to the
workspace rather than the document - the provenance baseline ledger, template
section sets, configuration - is read and parsed at most once per command
invocation and threaded or cached at run scope. Per-document recomputation of a
workspace-scoped fact is the defect class; the baseline ledger memoization is
its first application, and the loop-invariant path resolution fix is the same
rule applied to derived values.

**D5 - Complexity budgets with a synthetic-corpus regression gate.** No checker
or verb hot path may be superlinear in corpus size; O(features x documents)
scans are banned outright. The gate asserts the budget mechanically: benchmarks
over synthetic corpora generated at test time at two sizes, under the dedicated
scale marker, asserting operation counts and cross-size scaling ratios rather
than wall-clock, so the gate is deterministic on shared CI runners. This extends
the accepted graph benchmark layer from its 5,000-document envelope to the
measured 12k scale, which this record adopts as the new supported envelope.

**D6 - Report volume is capped, marked, and delegated to JSON.** Human-readable
report phases render a fixed per-section cap with an explicit truncation marker
and aggregate counts; the full result set stays available under `--json`, which
remains the machine contract. Render loops query terminal geometry once per run,
not per line. This extends the accepted output contract's truncation clause to
the check and graph report surfaces.

**D7 - Warm reads become the default where the cache is sound.** With D1 making
warm validation cheap, callers that currently force cold builds for no
correctness reason - the MCP find tool, the second graph build inside the status
stats path - use the cached graph. The orientation surface composes one scan and
one graph per invocation, honouring the batched-core decision it drifted from,
and type-filtered listings classify by path arithmetic instead of parsing.
Ref-scoped reads remain cache-off by codified rule.

**D8 - Native leaf libraries accelerate the existing seams; no native
engine.** The parse hot path keeps its libyaml-backed loader (the
already-shipped `CSafeLoader`-with-fallback seam in the frontmatter
parser), and the opt-in graph analysis surface routes its expensive
algorithm (betweenness centrality) through a C-backed graph library with
the pure networkx implementation as the automatic fallback when the wheel
is unavailable. The canonical graph structure, every checker, all
serialization, and the wire contract remain pure Python: native code is
confined to leaf computations behind seams D2 and the parser already
define, so no semantics are duplicated. A dedicated native calculation
engine is explicitly rejected at the current scale envelope and revisits
only under a new record if a 100k-document target or a sub-100ms
interactive consumer materialises.

Adjacent but explicitly out of scope: the `--target` routing defect in `doctor`
and `spec doctor` recorded in the grounding audit is an ordinary correctness bug
to be fixed independently; it is named here only so the performance work is not
conflated with it.

## Rationale

The audit demonstrates that every expensive behaviour is a pattern, not an
incident: the same corpus is re-read because nothing forbids it, the same
expensive analysis is bought accidentally because the API bundles it with cheap
counts, and the same workspace fact is re-parsed because no rule scopes reads to
the run. Point fixes were therefore rejected wherever a standing contract could
eliminate the class. The racily-clean cache rule wins because it is the
established resolution of exactly this soundness-versus-cost trade-off, proven
at far larger scale by git, and because it returns the implementation to the
already-accepted stat-keyed design rather than pivoting from it - D1 is
concretization of `2026-06-10-graph-backend-adr` layer 4, not supersession. The
single-ingress contract wins over per-check patching because the validators
decision already ratified the direction (first-class snapshot fields so checkers
stop re-parsing); D3 finishes that thought and makes it enforceable. Operation
counts beat wall-clock for the gate because the project's testing mandate
demands determinism and CI runners do not offer it for timing. The report policy
is the output-standardization contract applied to the one surface family it had
not yet reached. Together the decisions take the measured corpus from
minute-class to seconds-class using only validated, output-identical refactors
plus two explicitly versioned surface changes.

## Consequences

- The supported scale envelope formally moves from ~5,000 to ~12,000 documents,
  with projected verb times on the measured corpus dropping from 80-87s to under
  15-22s (`2026-07-27-vault-scale-performance-audit`); the graph decision's
  envelope statement is extended by this record, and both records now bind the
  cache: the earlier one for its existence and invalidation invariants, this one
  for its validation policy.
- Accepting the racily-clean rule accepts a stated staleness window: a same-size,
  same-tick edit made outside the mutating verbs can be served stale until the
  next touch. The window is negligible on NTFS and ext4 and covered by re-hashing
  on coarse filesystems, but it is nonzero, and the deep-verification path exists
  for operators who need certainty.
- The snapshot grows (raw bytes, additional metadata), trading resident memory
  for I/O; on the measured corpus this is bounded by total corpus size, but the
  implementation must watch peak memory on corpora another order larger.
- The single-ingress contract makes writing a new checker slightly more
  ceremonious: it must declare snapshot consumption and passes the
  unreadable-corpus test, which is the point.
- Report caps change what a human sees by default on large corpora; the marked
  truncation and JSON delegation keep information loss explicit, but scripts
  scraping human output (never a supported interface) may notice.
- The scale gate adds a benchmark tier to CI whose corpora are generated per
  run, costing test time; the dedicated marker keeps it out of the default
  developer loop.
- Two surface changes (opt-in analysis, report caps) require schema-version
  bumps and contract tests in the same change, per the codified discipline.
- Deferred, each needing its own decision if pursued: parallel calculate phase
  over the snapshot, a persistent daemon serving warm graphs, and any envelope
  beyond ~12k documents.

## Codification candidates

- **Rule slug:** `single-ingress-check-pipeline`. **Rule:** A vault checker
  consumes the shared corpus snapshot and must not read document content or
  metadata from disk during the calculate phase; facts a checker needs are added
  to the snapshot, not re-ingested.
- **Rule slug:** `workspace-facts-read-once`. **Rule:** A fact scoped to the
  workspace (ledger, template set, configuration) is read at most once per
  command invocation and shared at run scope, never recomputed per document.
- **Rule slug:** `analysis-is-opt-in`. **Rule:** Render and orientation paths
  may consume only descriptive-count surfaces; graph-theoretic analysis is
  invoked only by an explicit analysis request.
