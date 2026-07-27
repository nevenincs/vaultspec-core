---
tags:
  - '#audit'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
related: []
---

# `vault-scale-performance` audit: `large-vault command latency`

## Scope

Wall-clock behaviour of the read-side verbs at one order of magnitude above the
design envelope. Two corpora were measured: this repository's own vault (1,163
documents) and the AEAT production vault (11,962 documents: 332 plans, 8,250 exec
records, 577 ADRs, 714 indexes, 711 features). All figures are measured, not
estimated, and every fix candidate cited below was validated to produce
byte-identical output against the baseline. The CLI startup floor is 0.45s. The
audit exists because the graph performance posture (`2026-06-10-graph-backend-adr`)
targets correct behaviour to roughly 5,000 documents; AEAT sits 2.4x past that
envelope and the superlinear verbs have become minute-class.

Baseline wall-clock:

| command           | core (1.1k docs) | AEAT (12k docs) | scaling vs 10.3x corpus |
| ----------------- | ---------------- | --------------- | ----------------------- |
| `vault graph`     | 1.9s             | 87.2s           | 45x, superlinear        |
| `doctor`          | 4.4s             | 80.4s           | 18x, superlinear        |
| `vault check all` | 4.1s             | 79.5s           | 19x, superlinear        |
| `status`          | 2.9s             | 25.6s           | 8.8x                    |
| `vault list`      | 0.9s             | 5.6s            | 6.1x                    |
| `spec doctor`     | 2.6s             | 2.9s            | flat, workspace-only    |

Projection with the findings below resolved: `vault graph` 87.2s to ~4s, `status`
25.6s to ~3s, `vault check all` 79.5s to ~19s, `doctor` 80.4s to ~22s; capping the
report phase takes the latter two under 15s.

## Findings

### baseline-ledger-per-document-read | critical | Creating the documented provenance ledger adds ~90s to every check run

`_read_baseline(root_dir)` in `src/vaultspec_core/vaultcore/body_schema.py:284`
reads and parses a workspace-global ledger once per document. The ledger is
currently absent, so an existence probe short-circuits the whole pass at 0.27s -
the defect costs nothing today. But AEAT emits thousands of "Body schema
provenance is not attested" warnings whose documented remediation is to create
exactly that ledger. Measured with a synthetic 11,890-entry, 1.6MB ledger: one
parse is 0.008s; the projected 11,890 per-document parses total 90.3s added to
`vault check all` and `doctor`. The trap detonates on precisely the path the tool
instructs the operator to take. Memoizing to a single read per run removes the
cost entirely. Rated critical despite zero present-day cost because it is armed by
following the tool's own advice.

### render-tree-buys-all-pairs-centrality | high | The graph tree render runs all-pairs shortest paths to print a three-number title

`render_tree` at `src/vaultspec_core/graph/api.py:1414` calls `metrics()` only to
build the title string ".vault 11890 docs, 28969 links, 711 features". That call
triggers `nx.betweenness_centrality` at `src/vaultspec_core/graph/api.py:1261`,
O(V\*E), roughly 344M operations - 76.8s of the 87.2s total. Deriving the three
counts directly was validated identical and 14,905x faster. The root cause is that
`metrics()` conflates cheap descriptive counts with expensive graph-theoretic
analysis, so every caller pays for both.

### features-check-quadratic | high | check_features is O(features x documents)

`_index_exists_for` (`src/vaultspec_core/vaultcore/checks/features.py:38`, invoked
at `:174`) and `_count_feature_docs` (`:53`, invoked at `:191`) each perform a
full snapshot scan inside the per-feature loop: 711 features x 11,890 documents,
about 16.9M iterations and 7.9M `extract_feature_tags` calls. The enclosing loop
already makes a single full pass that could precompute both facts. Validated:
27.7s to 0.04s, 698x, identical output.

### exec-mapping-replans-per-record | high | check_exec_mapping re-parses each plan once per exec record

`src/vaultspec_core/vaultcore/checks/exec_mapping.py:144` calls `_plan_step_ids`
unmemoized inside the per-record loop: 7,304 `parse_plan` invocations for only 208
distinct plans, 35x redundant, driving 2.17M `_build_step` calls. Validated with a
per-plan memo: 21.1s to 0.18s, 119x, identical output.

### cache-fingerprint-hash-always | high | The graph cache's own validation costs more than the cache saves

`fingerprint_vault` at `src/vaultspec_core/graph/cache.py:148` SHA-256s every file
unconditionally. The module docstring calls size+mtime the "cheap fast-path
guard", but it never short-circuits: validation only runs after all 11,890 hashes
are computed. Cold build 11.9s, warm 7.3s of which 6.5s is fingerprinting; the net
cache benefit is only 4.6s. A stat-only manifest is 0.29s, 22x cheaper, which
would put the warm build at roughly 1.1s. The docstring's soundness argument - a
same-size edit landing inside one mtime tick evades a stat-only check - is real
but overstated on nanosecond-resolution filesystems (NTFS, ext4). This diverges
from the governing design, which specified the fingerprint as a
`(st_size, st_mtime_ns)` key (`2026-06-10-graph-backend-adr`); hash-always was an
implementation-time hardening whose cost was never measured at scale. Which
validation policy to adopt, and what residual risk to accept, is the sharpest
decision the follow-on ADR must make.

### check-pipeline-re-ingests | high | The check pipeline does not stay staged after ingress

Ingress completes in 7.2s and `to_snapshot()` in 0.10s - the whole corpus is then
in memory - yet the calculate phase goes back to disk 51,688 more times.
Instrumented totals over 11,890 documents: 63,580 content reads (5.35 per
document) and 147,948 metadata syscalls (12.44 per document). Three distinct
classes of bounce. First, checks that never receive the snapshot
(`src/vaultspec_core/vaultcore/checks/__init__.py:113`, `:114`, `:123`, `:127`):
annotations, markdown, encoding, feature_rename_integrity, and rename_integrity
re-read 44,384 documents between them; only encoding legitimately needs disk,
because it inspects raw bytes for BOM and line endings while the snapshot carries
a decoded `str` (annotations recomputed from the snapshot was validated 3.4x
faster and identical). Second, checks that hold the snapshot but read disk anyway:
exec_mapping performs 7,304 content reads plus 8,462 `is_file` probes (see
finding exec-mapping-replans-per-record). Third, checks that hold everything but
hammer path syscalls: body_sections issues 44,704 metadata operations and zero
content reads, costing 4.17s.

### status-walks-corpus-five-times | medium | status rebuilds the graph and rescans the corpus it already holds

`src/vaultspec_core/vaultcore/orientation.py:491` holds a fully built graph, then
imports and calls `get_stats` with only `root_dir`; `get_stats` at
`src/vaultspec_core/vaultcore/query.py:214` builds a second complete `VaultGraph`,
and `list_documents` at `:152` re-reads and re-YAML-parses every document for data
the graph already holds. Net effect: 2x graph build, 2x fingerprint, 3x
`_scan_all`, 68,251 file opens for 11,890 documents. Separately,
`list_documents(doc_type="plan")` parses all 11,890 documents to find 332 plans,
though the document type is derivable from the directory path with zero I/O
(`get_doc_type` in `src/vaultspec_core/vaultcore/scanner.py` is pure path
arithmetic).

### resolve-per-document | medium | Loop-invariant path resolution recomputed per document

`src/vaultspec_core/vaultcore/body_schema.py:459` evaluates
`doc_path.resolve().relative_to(root_dir.resolve())`, calling `resolve()` twice
per document and recomputing the loop-invariant `root_dir.resolve()` 11,176
times. On Windows `resolve()` is `nt._getfinalpathname`, which opens a file
handle. Hoisting the invariant is 1.7x; dropping `resolve()` entirely is 18.2x
(2.97s to 0.16s) and identical, because `scan_vault` already yields absolute
canonical paths.

### report-phase-uncapped | medium | Human-readable report output is unbounded at scale

`vault check all` emits 4.3MB across 34,897 Rich `console.print` calls. Unscoped
`vault graph` prints 44,218 lines, with Rich re-querying the terminal size twice
per line (88,438 `nt.get_terminal_size` calls). No cap, aggregate, or truncation
marker exists on either surface.

### mcp-find-builds-cold | low | The MCP find tool always builds the graph cold

`src/vaultspec_core/mcp_server/tools/documents.py:611` constructs
`VaultGraph(root_dir, use_cache=False)`, so every MCP `find` call pays a full
cold build even when a valid cache exists.

### target-flag-ignored-by-doctor | high | doctor and spec doctor silently audit the wrong directory under --target

A correctness defect adjacent to but distinct from the performance findings:
`src/vaultspec_core/cli/root.py:967` and
`src/vaultspec_core/cli/spec_cmd.py:2008` use `target or Path.cwd()` instead of
the `target or _root_target or Path.cwd()` pattern established in
`src/vaultspec_core/cli/_target.py`, so `vaultspec-core --target X doctor`
audits the current directory and exits with a code derived from the wrong vault.
This is a straight bug fix, not an architectural decision, and must not be
conflated with the performance work.

## Recommendations

- Resolve the cache validation policy by decision, not patch: hash-always versus
  stat-trust with a racily-clean window, including the residual risk accepted per
  filesystem class (finding cache-fingerprint-hash-always). This reconciles the
  implementation with `2026-06-10-graph-backend-adr` and is the follow-on ADR's
  central call.
- Split cheap descriptive counts from expensive graph-theoretic analysis at the
  metrics API so no render path can buy an O(V\*E) computation by accident
  (finding render-tree-buys-all-pairs-centrality); the ADR must fix the API shape
  that makes the expensive computation opt-in.
- Establish a single-ingress contract for the check pipeline: every check
  receives the shared snapshot, the snapshot carries what checks actually need
  (including raw bytes so encoding folds into the one read), and the contract is
  enforced so a future check cannot silently re-ingest (finding
  check-pipeline-re-ingests; also resolves exec-mapping-replans-per-record and
  the disk half of features-check-quadratic).
- Adopt a standing memoization rule for workspace-global reads: a per-workspace
  fact is read once per run, never per document (finding
  baseline-ledger-per-document-read; same class as resolve-per-document).
- Set complexity budgets - no check superlinear in corpus size - and decide how
  regressions are caught, noting that `vaultspec_core.testing.synthetic` is the
  canonical generator and corpus fixtures are never committed (findings
  features-check-quadratic, exec-mapping-replans-per-record).
- Decide a report volume policy for the uncapped render surfaces (finding
  report-phase-uncapped), extending the established output contract
  (`2026-06-13-cli-output-standardization-adr`) to the check and graph report
  phases.
- Reuse the collapsed status internals so orientation composes one scan and one
  graph (finding status-walks-corpus-five-times), honouring the batched-core
  intent of `2026-06-12-vault-orientation-adr`.
- Route the `--target` routing defect (finding target-flag-ignored-by-doctor) as
  an ordinary bug fix outside the performance feature.
