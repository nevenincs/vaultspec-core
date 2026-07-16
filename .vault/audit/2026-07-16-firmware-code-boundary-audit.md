---
tags:
  - '#audit'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - '[[2026-07-16-firmware-code-boundary-plan]]'
  - '[[2026-07-16-firmware-code-boundary-adr]]'
---

# `firmware-code-boundary` audit: `one-way vault reference boundary firmware pass` | (**status:** `PASS`)

## Scope

Read-only review of branch `feature/firmware-code-boundary` versus `main` (PR 212), a
documentation-only firmware wording pass introducing the one-way vault reference
boundary. Audited the full diff against the governing decision, the executed L2 plan
(9 steps), the grounding research, and the two standing decisions the wording must not
contradict (commit-linkage, firmware-mcp-primacy). No Python change exists, so the
Safety domain reduced to confirming zero code-behavior impact. Reviewed by the
`vaultspec-code-reviewer` persona dispatched as an independent read-only subagent.

## Findings

### code-behavior-impact | low | Zero Python or executable surface touched; Safety domain satisfied

The diff over `*.py` is empty. The entire change set is markdown firmware sources
under `src/vaultspec_core/builtins/`, their CLI-generated `.vaultspec/` mirror, and
vault records. No schema, template, or persona `tools:`/`mode:`/`order:` frontmatter
changed. No crash, resource, or concurrency surface exists.

### intent-completeness | low | All six decided surfaces and both echo and full forms landed as decided

Every Implementation item of the governing decision is present and anchored where
specified: the canonical Code Stands Alone mandate beside the Comments mandate in
`system/01-core.md`; the removable-harness characterization in
`system/03-vaultspec.md`; the one-way hierarchy clause in `rules/vaultspec.builtin.md`;
the compressed bullet in each executor persona; the Boundary Integrity check (existing
HIGH class, no taxonomy change) in `agents/vaultspec-code-reviewer.md`; and the
in-place Traceability disambiguation in `skills/vaultspec-execute/SKILL.md`. The
canonical full form appears once; echoes are compressed per the mcp-primacy anti-bloat
shape.

### executor-trio-parity | low | Executor bullet is byte-identical across all three personas

The extracted Code stands alone bullet in `vaultspec-low-executor.md`,
`vaultspec-standard-executor.md`, and `vaultspec-high-executor.md` hashes identically
(md5 `b974bd08...`), satisfying the structural-parallelism constraint (D9 of the
firmware-wording-review decision).

### mirror-parity | low | Deployed mirror matches its builtin sources exactly

Each of the eight touched files is identical between `src/vaultspec_core/builtins/`
and `.vaultspec/`; the mirror was reconciled by `vaultspec-core sync`, not hand-edited.

### constraint-record-scoping | low | Wording forbids the project's own dev records, never the literal path string

Every insertion scopes the prohibition to references to the project's own development
records rather than the literal `.vault` path string, preserving legality for
vault-domain product code. The trailer carve-out is present on all four full-boundary
statements; the executor echo and the framework characterization correctly defer to
the canonical mandate rather than restating it.

### consistency-standing-adrs | low | No contradiction with commit-linkage or mcp-primacy decisions

The trailer wording names trailers as the sanctioned linkage channel without making
them load-bearing, consistent with the enrichment-only commit-linkage decision.
Placement honors the mcp-primacy per-surface audience split. All changed lines use
ASCII spaced hyphens; no em dash appears in the diff.

### phrasing-variance | low | Minor wording drift in the carve-out clause (nitpick)

`system/01-core.md` and `agents/vaultspec-code-reviewer.md` read "the only sanctioned
linkage channel"; `rules/vaultspec.builtin.md` and `skills/vaultspec-execute/SKILL.md`
read "the sanctioned linkage channel". Meaning is identical; optional consistency
nitpick, not a defect.

### vault-record-quality | low | Step Records complete, plan fully closed, frontmatter CLI-owned

All nine exec Step Records exist for the feature; the plan has zero open rows.
Spot-checked exec frontmatter carries the correct tag pair, CLI-owned `step_id`, and
quoted wiki-link. The follow-up issue for the mechanical scanner was verified filed as
issue 213 by the orchestrator (outside the read-only diff review's own scope).

### drift | low | No files or wording touched beyond the decided surfaces plus vault records

The builtin change set is exactly the six decided surfaces (eight files) plus their
mirror; no extra firmware surface, persona, or skill was modified.

## Recommendations

- Optional (ties to phrasing-variance): harmonize the carve-out clause to a single
  form ("the only sanctioned linkage channel") across the four full-boundary surfaces
  on a future wording pass. No action required for merge.

Status: PASS. No CRITICAL or HIGH findings; safe to merge.
