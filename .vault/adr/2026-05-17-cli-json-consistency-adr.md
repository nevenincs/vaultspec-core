---
tags:
  - '#adr'
  - '#cli-json-consistency'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-json-consistency-research]]'
---

# `cli-json-consistency` adr: `Adopt a uniform --json schema with top-level status field` | (**status:** `accepted`)

## Problem Statement

`--json` outputs across the CLI have inconsistent top-level
shape. Four of nine surveyed outputs carry a top-level `status`
field; five do not. The output most useful for CI gating
(`vault check all --json`) is the bare-array case. CI integrators
have to write per-command parsing logic instead of pattern-
matching one shape.

Finding S19.

## Considerations

- Two reasonable answers: standardise on top-level `status`
  everywhere, or accept that status-shaped and iterative-shaped
  outputs are genuinely different. The audit's data argues for
  the former: status answers are useful even on iterative
  commands ("did the iteration as a whole pass").
- The fix coordinates with the sync-vocabulary ADR. Outcome
  words from the seven-element taxonomy populate the top-level
  status field on every command.
- Schema versioning is overdue. Consumers that have parsed
  today's outputs have no mechanism for forward compatibility.
- The fix is implementable per command in a small wrapper.
  Each command's existing payload becomes nested inside the
  envelope.

## Constraints

- Existing consumers parsing today's outputs are the contract.
  Adding fields is safe; removing or renaming is not. The
  fix is purely additive.
- The schema-version string must be stable across patch
  releases. A documented registry of schema versions lives
  alongside the CLI reference.
- The envelope must not duplicate information already in the
  payload. The top-level `status` summarises; the payload
  details. Duplication would be a maintenance burden and an
  ambiguity source.

## Implementation

**Uniform JSON envelope.** Every `--json` output wraps its
content in this shape:

```
{
  "schema": "vaultspec.<command>.v1",
  "status": "<one of: created | updated | unchanged | removed | restored | skipped | failed | mixed>",
  "data": { /* command-specific payload */ },
  "hints": { /* optional, per next-step-hints ADR */ }
}
```

- `schema`: namespaced identifier of the command plus a
  monotonic version integer. New fields under `data` may land
  without bumping the version (additive). Renamed or removed
  fields bump the version.
- `status`: the canonical outcome word for the whole
  invocation. `mixed` when individual items in `data` have
  heterogeneous outcomes.
- `data`: the command's existing JSON output, nested without
  modification. Backwards compatible.
- `hints`: structured next-step hint (per the next-step-hints
  ADR). Optional; absent when no hint applies.

**Apply to every `--json` output.**

- `vault check all --json` gains the envelope. `status` is
  `unchanged` (clean), `failed` (errors), or `updated` (when
  `--fix` ran).
- `migrations status --json` already has top-level `status`;
  it gets wrapped to match envelope shape.
- `spec mcps status --json` already has top-level `status`;
  wrapped to envelope shape.
- Every other surveyed command (`spec doctor`, `vault list`,
  `vault stats`, `vault graph`, `vault plan status`, `vault repair`) wraps its payload identically.

**Schema registry.** A documented section in the framework
manual enumerates every command's current schema version and
describes the contract for what each schema covers. Schema
bumps go in the release notes.

**`--json` mode contract.** When `--json` is in effect:

- Stdout contains only the envelope JSON. No prose. No
  banners.
- Stderr remains the channel for diagnostic logging at
  documented log levels.
- Exit code stays meaningful (sync with the spec-edit-safety
  ADR's honest-exit-code invariant). `status: failed` in the
  envelope implies non-zero exit code.
- Pretty-printing is on by default for readability; a future
  `--json-compact` flag may emit single-line output for
  pipes.

**Hints in JSON mode.** Per the next-step-hints ADR, hints
emitted to text mode become a structured `hints` field in
JSON:

```
"hints": {
  "next_step": {
    "command": "vaultspec-core vault add adr --feature ... --related ...",
    "description": "decide (next pipeline phase)"
  }
}
```

Hints are absent when no hint applies. Their inclusion does
not change `status`.

**Companion language updates.**

- Framework manual section on machine-readable outputs is
  rewritten to describe the envelope as the contract.
- `--help` text on every `--json`-supporting verb names the
  envelope and the schema version.
- Builtin rule files that reference machine-readable outputs
  are updated to consume the envelope.
- Agent personas update their CI-reasoning patterns to expect
  the envelope shape: `status` is the gate, `data` is the
  detail, `hints.next_step` is the suggestion.

## Rationale

The audit produced decisive evidence that the inconsistency
exists and that the most CI-critical command is the worst
offender. A purely additive envelope wraps every existing
output without breaking any consumer. The schema version
provides forward compatibility the framework currently
lacks.

The envelope coordinates with two adjacent ADRs:
sync-vocabulary's outcome taxonomy (the values `status`
takes) and next-step-hints (the `hints` field). The three
ADRs together turn `--json` from a per-command artifact into
a documented framework contract.

Wrapping rather than rewriting lets the change land per
command incrementally. Each verb adopts the envelope
independently; no big-bang migration is required.

## Consequences

Gains. CI gates collapse to one parse pattern across every
verb. Schema versioning becomes a first-class contract.
Top-level `status` field is the single source of "did this
run pass". Next-step hints become consumable by tooling.

Difficulties. Every `--json`-emitting verb needs the
envelope wired through. The per-verb cost is small (wrap the
existing payload) but the touch count is large. Test surface
grows: every verb needs a regression test for the envelope
shape.

Pitfalls. The envelope must not become a place to put
overflow concerns. If a need arises for a fifth top-level
field, the framework's contract review must gate the
addition. Otherwise the shape drifts back to the
inconsistency the audit found.

Pathways. With the envelope adopted, the framework has the
foundation for a documented machine-readable surface that CI
and IDE integrations can build against. The "is the
workspace green" question (round-3a S17) collapses to
`vaultspec-core vault check all --json | jq .status`. The
operator-guessing finding closes from the tooling side.
