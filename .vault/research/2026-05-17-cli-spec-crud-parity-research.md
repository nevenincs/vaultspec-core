---
tags:
  - '#research'
  - '#cli-spec-crud-parity'
date: '2026-05-17'
modified: '2026-06-13'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-spec-crud-parity` research: `CRUD verbs diverge across spec noun groups`

Synthesis note for findings S9, S15, S16 — the same noun pattern
produces inconsistent verb shapes across `spec` resource groups.

## Findings

### S9 — Uneven CRUD parity across rules / skills / agents

Joan round-3a finding [41]–[42]. The three noun groups
`spec rules`, `spec skills`, and `spec agents` look like a verb
trinity, but:

- `spec rules add` accepts `--content` to seed the rule's body.
- `spec skills add` and `spec agents add` accept `--description`
  instead.
- Output strings on `add` (the past-tense outcome word) vary
  across the three. One says `updated` on a fresh create (a
  separate bug); others say something else.
- Help text shape and column widths are inconsistent across
  the three.

Same shape, three different surfaces.

### S15 — `spec hooks` has no CRUD verbs

`vaultspec-core spec hooks list` enumerates events;
`vaultspec-core spec hooks run` invokes them. The verb pair
`list`/`run` is the full surface. There is no `spec hooks add`,
no `edit`, no `enable`, no `disable`. The example hook ships
disabled and the documented path to enable it is to edit the
configuration file directly.

The verb pair invites the natural question "how do I add a
hook" and the surface has no answer. Joan flagged this in
round-3a as a missing-CRUD finding rather than a bug.

### S16 — `spec mcps` has a `status` verb the others do not

`vaultspec-core spec mcps status` reports MCP server health.
`spec rules`, `spec skills`, `spec agents` have no `status`.
Either status is useful for the noun (in which case the
others should have it) or it is not (in which case mcps should
not). Same-shaped nouns should share verbs.

### The shared shape

Every spec noun group is supposed to be a CRUD container. The
fact that each one ships a slightly different verb set, with
slightly different flag names, with slightly different outcome
words, is the visible surface of a missing per-noun-group
template.

A team adding a fourth noun group (e.g., `spec workflows`)
today has no obvious shape to follow. The framework's own
mirror — three noun groups in production with three different
shapes — produces no canonical answer.

### What the shape should be

Every spec noun group exposes the same minimum verb set:

- `<group> list` (read all)
- `<group> show <name>` (read one)
- `<group> add` (create) with a consistent flag for body
  content
- `<group> edit <name>` (update via editor; subject to the
  spec-edit-safety ADR)
- `<group> rename <old> <new>` (subject to the rename-
  integrity ADR)
- `<group> remove <name>` (delete authored content)
- `<group> revert <name>` (restore canonical builtin; subject
  to the sync-vocabulary ADR's renaming of revert semantics)
- `<group> sync` (push to providers, subject to the sync-
  vocabulary ADR)
- `<group> status` (report health)

Plus where the noun supports authoring, a uniform body-content
flag (`--body`, not `--content` on one and `--description` on
two).

## Constraints identified

- `spec system` is structurally different from the others
  (single doc, not a collection). It does not need a full CRUD;
  `show` and `sync` are sufficient. The uniform-CRUD rule
  applies to collection-shaped nouns, not singleton-shaped
  ones.
- `spec hooks` adds an authoring surface; today hooks are
  config-file-only. Adding CRUD verbs to hooks is a small
  amount of work for a meaningful surface improvement.
- `spec mcps` may be ahead of the others on `status` because
  MCP servers have an external health concept. The right
  answer is to add `status` to every noun group, with
  consistent semantics (does the authored content match the
  synced provider output, do all references resolve, etc.).

## Recommendation

Define a single CRUD-shape template for collection-shaped
noun groups. Apply it to `spec rules`, `spec skills`,
`spec agents`, `spec hooks`, `spec mcps`. Leave `spec system`
as the singleton exception. Full design in the sibling ADR.
