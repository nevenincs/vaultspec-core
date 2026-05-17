---
tags:
  - '#research'
  - '#cli-json-consistency'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-json-consistency` research: `--json outputs lack uniform shape across the CLI`

Synthesis note for finding S19. Captures Xavi's round-3b survey
across nine commands.

## Findings

### Survey results across nine commands

Xavi round-3b finding [33], [43], [47], [48], [49], [50].
Outputs surveyed:

- **`spec mcps status --json`** (gold standard): top-level
  `status: "ok"` plus typed arrays for `missing`, `drifted`,
  `stale_managed`, `warnings`. CI gate is a single string
  compare.
- **`migrations status --json`**: top-level `status:
  "up_to_date"` plus `registered: [...]`, `pending: [...]`.
  Self-describing.
- **`spec doctor --json`**: deep tree per-provider state.
  Useful but verbose.
- **`vault repair --json`**: phase breakdown, per-diagnostic
  fixability. Richest output in the survey.
- **`vault list --json`**: clean per-document array
  `{path, name, doc_type, feature, date, tags}`. Excellent.
- **`vault stats --json`**: single-shot summary
  `{total_docs, total_features, counts_by_type,
  orphaned_count, dangling_link_count}`. Tidy.
- **`vault graph --json`**: standard NetworkX-shaped node-link
  export. Immediately consumable by graph tooling.
- **`vault plan status --json`**: clean per-plan object
  `{tier, ..., completion_percent}`. Good.
- **`vault check all --json`** (weakest): bare per-check
  array, no top-level success/failure wrapper, no diagnostic
  counts, no schema version.

### The pattern in the data

Four of nine outputs carry a top-level `status` field. Five
do not. The output most consequential for CI (`vault check
all --json` — the obvious gate for "is this vault green")
does not. The output least likely to drive CI (`spec mcps
status --json`) does.

The pattern is not random. Verbs that semantically report a
single state (status verbs) have a top-level status field.
Verbs that report a multi-item operation (check verbs,
graph exports) do not. This is an artifact of how each
command's output was modelled: status-shaped output gets
status-shaped JSON; iterative-shaped output gets array-
shaped JSON.

### Why the asymmetry breaks CI

CI gates need a single answer: did this run pass. The bare
array shape forces CI to iterate every entry, accumulate
state, and compute the answer. The top-level field provides
the answer directly. The same operation in CI takes one line
or twenty depending on which command was modelled which way.

The fix is to add the top-level summary field to every JSON
output, alongside the existing per-item arrays. The two
shapes coexist: the summary for CI gates, the array for
detailed inspection.

### Coordination with the sync-vocabulary ADR

The sync-vocabulary ADR defines a canonical seven-word
outcome taxonomy. The `--json` schema should consume that
taxonomy: every top-level `status` field's value is one of
the seven words (or `mixed` when items have heterogeneous
outcomes). The two ADRs share the same source of truth.

### Schema versioning

None of the surveyed outputs declares a schema version. A
consumer that pattern-matches against today's structure has
no way to detect future schema additions. Adding `schema:
"vaultspec.<command>.<v>"` at the top level lets consumers
adapt cleanly across CLI versions.

## Constraints identified

- Existing consumers that parse today's `--json` outputs are
  the user-facing contract. Additions (top-level fields,
  schema version) are backwards-compatible; removals or
  renames are not.
- The shape change must be implementable per command without
  rewriting the renderer wholesale. Each command's JSON
  emitter wraps its existing output in a thin envelope.
- The schema-version string must be stable. A documented
  registry of schema versions lives alongside the CLI
  reference.

## Recommendation

Adopt a uniform top-level JSON envelope: `status` (canonical
outcome word), `schema` (versioned identifier), plus the
command's existing payload as a nested object. Apply across
all `--json` outputs. Document the envelope as a stable
contract. Full design in the sibling ADR.
