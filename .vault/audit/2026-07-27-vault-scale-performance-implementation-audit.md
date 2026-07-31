---
tags:
  - '#audit'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:c641383f5d5e042f05da4a3199448be0046209be37bacfc15604b02b0ef63cc4'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
  - "[[2026-07-27-vault-scale-performance-adr]]"
---

# `vault-scale-performance` audit: `implementation`

## Scope

Verification of the plan's 19 Steps against the authorizing ADR's seven
decisions, executed 2026-07-27 in a worktree shared with the unrelated
in-flight markdown-feature-scope work. Verified surfaces: the graph cache
(`src/vaultspec_core/graph/cache.py`), graph API and render paths
(`src/vaultspec_core/graph/api.py`), the query and orientation seams, the
check pipeline (`src/vaultspec_core/vaultcore/checks/`), the schema
resolver seam (`src/vaultspec_core/vaultcore/body_schema.py`), the shared
console, the MCP index-regeneration path, and the new test tiers.

## Findings

### gates | low | All quality gates pass; the only failures are pre-existing and foreign

The unit CI gate passes 1,916 of 1,918 tests; the two failures
(`test_vault_repair`) are caused by the unrelated in-flight body-schema
attestation warnings and reproduce without this feature's changes, as do
the three generated-CLI-reference failures (a new archive verb from the
other feature) and two `ty` diagnostics in the other feature's test file.
Scoped `ty` on every file this feature touched passes; `prek` hooks on the
same set pass (ruff lint and format clean). The vaultcore suite (557),
graph suite (143), MCP-related tests (69), the new single-ingress
enforcement tests (2), counts tests (3), cache tests (22), and the
benchmark-marked scale gate (3) all pass.

### contract-enforcement | low | The single-ingress contract is enforced physically, not by convention

The enforcement test deletes the corpus after ingress and requires the
calculate phase to reproduce its baseline diagnostics exactly; the scale
gate independently asserts exactly one read per corpus document across the
whole non-mutating pass at two corpus sizes. Both passed on first run
after wiring, which corroborates that no converted checker retains a
hidden disk dependency.

### parity | low | Output parity holds on the real corpus; deviations are the two decided surface changes

On this repository's vault, check totals, graph tree titles, and status
output match the pre-change baseline modulo documents this feature itself
added. Accepted pathological-input deviations, each documented in the
owning docstring or step record: lone-CR newline normalisation in the
content checks, symlinked-document reporting on the encoding graph path,
and sorted-first feature-tag selection for multi-tagged exec records.

### serializer-drops-body-schema | medium | The plan CLI serializer drops the scaffolded body_schema field

Out of this feature's code scope but surfaced by it: plan structural verbs
(`tier promote`, `step add`) rewrite the plan document without preserving
the scaffolded `body_schema` frontmatter, so the plan now warns as
unattested under the in-flight provenance checker. Hand-restoring
frontmatter is forbidden; the fix belongs to the serializer in the
markdown-feature-scope work.

### review | low | Independent read-only persona review dispatched

A read-only reviewer persona was dispatched over the exact changed-file
set with the ADR as its brief; its verdict is recorded in the findings
appended below.

### review-verdict | low | Independent review returned PASS; its one medium finding is fixed

The reviewer confirmed the racily-clean cache rule sound (comparison
direction, vanished-file path, and key-set equality all correct with no
staleness outside the accepted window), behaviour preservation on normal
corpora, test integrity (no mocks or stubs), and the single-ingress wiring
for every checker but one. Its single medium finding - the exec mapping
check could fall back to a disk read when a referenced plan failed to
decode during ingress - is fixed in the same session: a plan absent from
the ingress text map is now classified as unparseable without touching
disk, and the enforcement suite gained a test planting an undecodable plan
referenced by a real record and asserting the finding survives corpus
deletion. All 212 check tests and the scale gate pass after the fix.

### native-leaf-acceleration | low | D8 amendment implemented and measured

The decision record was amended (concretization in place, status stays
accepted) to add D8: native leaf libraries behind existing seams, a
dedicated C engine explicitly rejected. Verification on the real corpus:
the already-shipped libyaml frontmatter loader engages (7.3x over the
pure-Python loader; the full parse pass runs at C-loader speed), and the
new rustworkx routing for opt-in betweenness runs 13.2x faster at 1,181
nodes with a maximum score delta of 1.6e-19 versus networkx. A four-test
engine parity suite pins the agreement to 1e-12; the full graph suite
(147 tests) passes against engine-computed scores. One dependency added
(`rustworkx>=0.18.0`) with a pure networkx fallback.

### review-residuals | low | Two low-severity reviewer notes accepted as future cleanup

Unused module loggers in three check modules predate this feature, and the
save-path fingerprint re-reads bytes the ingress already read - a
pre-existing cold-build cost shape, correctly hashing raw bytes for
consistency with validation. Both are noted for a future pass, neither
blocks.

## Recommendations

- Fix the plan-serializer `body_schema` drop inside the
  markdown-feature-scope feature before its provenance checker ships, or
  every CLI-managed plan will warn as unattested (finding
  serializer-drops-body-schema).
- Route the adjacent `--target` routing defect in `doctor` and
  `spec doctor` (recorded in the grounding audit) as an ordinary bug fix;
  it remains open and untouched by this feature.
- When the shared worktree's in-flight work lands, re-run the repair and
  generated-reference test families to confirm the pre-existing failures
  close with it (finding gates).
