---
tags:
  - '#adr'
  - '#cli-spec-crud-parity'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-spec-crud-parity-research]]'
---

# `cli-spec-crud-parity` adr: `Define a uniform CRUD shape for every spec noun group` | (**status:** `accepted`)

## Problem Statement

The `spec` subtree exposes several noun groups (`rules`, `skills`,
`agents`, `system`, `hooks`, `mcps`) with inconsistent verb sets
and flag names. The same conceptual operation (create a resource)
takes `--content` on one group and `--description` on two others.
The `status` verb exists on `mcps` and nowhere else. The `hooks`
group has no CRUD verbs at all. The `system` group is a singleton
and structurally different from the rest.

There is no per-group template. Each noun group's verb set
appears to have been decided independently when the group was
added.

Findings S9, S15, S16 in the audit.

## Considerations

- A uniform CRUD template constrains future noun groups to a
  predictable shape. The framework's own three-group mirror
  today is unable to teach a fourth group the canonical
  pattern.
- Collection-shaped nouns (rules, skills, agents, hooks, mcps)
  need the same verbs. Singleton-shaped nouns (system) get a
  reduced template. The distinction must be explicit.
- The fix interacts with several adjacent ADRs:
  - Sync-vocabulary (the `revert` verb's semantics are
    redefined there; `restore` may be the cleaner name).
  - Rename-integrity (the rename verb's atomicity invariant
    applies here).
  - Spec-edit-safety (the editor-resolution contract applies
    to every `<group> edit`).
- Adding CRUD to `spec hooks` is the largest content addition;
  it makes hooks an authored-content first-class surface
  rather than a configuration-file-only surface.

## Constraints

- Existing flag names that diverge (`--content` vs
  `--description`) are user-facing contract. The fix unifies
  them under a single name (`--body`) and accepts the legacy
  names as deprecated aliases for one release.
- `spec system` is a singleton. The uniform template does not
  apply; the existing `show`/`sync` shape stays.
- Adding `status` to every noun group must produce useful
  output for each, not boilerplate. The semantics may differ
  per noun group (rules check sync-with-provider; mcps checks
  external health) but the verb is consistent.

## Implementation

**Canonical collection-shape CRUD template.** Every collection-
shaped noun group exposes exactly this verb set:

- `<group> list` — read all. Supports `--json`.
- `<group> show <name>` — read one. Supports `--json`.
- `<group> add <name>` — create. Supports `--body <text>` and
  `--from-file <path>` for body content. Optional metadata
  flags per group (e.g., `--description` becomes a separate
  optional flag, not the body content carrier).
- `<group> edit <name>` — update via editor (per spec-edit-
  safety ADR's editor resolution order).
- `<group> rename <old> <new>` — atomically rename (per
  rename-integrity ADR's invariant).
- `<group> remove <name>` — delete authored content. Refuses
  on builtins; refers the user to `<group> restore`.
- `<group> restore <name>` — drop in the canonical builtin
  version. Replaces today's `revert` verb (the rename clarifies
  the semantic per sync-vocabulary ADR's "restore" outcome
  word).
- `<group> sync` — push to providers (per sync-vocabulary
  ADR's outcome taxonomy).
- `<group> status` — report health: do authored items match
  their synced provider mirrors, do all references resolve, do
  any items have stale frontmatter, what is the sync state?

**Singleton-shape template.** `spec system` retains `show` and
`sync` only. Documented as the singleton exception in the
help text and the manual.

**Apply uniformly.**

- `spec rules`: takes the canonical CRUD shape. `--body`
  replaces `--content` (legacy alias for one release).
- `spec skills`: same. `--body` replaces `--description` as
  the body carrier. `--description` becomes an optional
  metadata flag for the human-readable description; it does
  not pre-populate the body.
- `spec agents`: same. `--description` becomes optional
  metadata.
- `spec hooks`: gains `add`, `edit`, `rename`, `remove`,
  `restore`, `sync`, `status`. The existing `list` and `run`
  remain. Authoring a hook today requires editing the config
  file; the new verbs make hooks first-class.
- `spec mcps`: gains `edit`, `rename`, `restore`. `status`
  remains and serves as the template for `status` on other
  groups.

**Outcome vocabulary.** Every verb emits the seven canonical
outcome words from the sync-vocabulary ADR. The `add`-says-
`updated`-on-fresh-create paper cut is closed by routing every
`add` through the same renderer.

**Help text shape.** Every group's help text follows the same
template: usage line, brief description, options panel,
commands panel. Column widths are normalised. The framework
manual links to the help text directly rather than re-describing
each group's verb set.

**Companion language updates.**

- Framework manual section on the `spec` subtree is rewritten
  to describe the canonical template once and the noun-group-
  specific semantics in short subsections.
- Builtin rule files that describe how to customise rules /
  skills / agents are updated to use the unified vocabulary
  (`--body`, `restore`, etc.).
- Agent personas update to know that adding a hook is now
  first-class CLI work, not config-file editing.
- Help-text generator gets a shared template that every noun
  group consumes.

## Rationale

Three rounds of audit produced inconsistencies on every spec
noun group. The findings cluster (S9 + S15 + S16) is a single
architectural omission: the framework lacks a per-group
template, and absent one, each group's shape is the artifact of
when it was written.

A uniform template is small to specify and large in payoff.
Future noun groups (workflows, plugins, whatever) inherit the
shape automatically. The framework's own surface becomes
internally teachable — a developer who has learned one group
knows all of them.

Promoting hooks to first-class authoring is the largest
content change in this ADR. The user surface gains a real
verb where today only config-file editing exists. The
implementation cost is small; the discoverability win is
large.

Renaming `revert` to `restore` is the smaller wording change
that aligns with the sync-vocabulary ADR's outcome taxonomy.
The pre-fix verb `revert` reads as "undo my change" to a new
user but means "drop in the builtin"; `restore` is honest.

## Consequences

Gains. Every spec noun group has the same shape. Operator
mental model collapses. New noun groups inherit the template.
Help text is consistent across groups. The "add a hook" gap
closes.

Difficulties. Flag-name renames break automation that calls
the old names. The one-release deprecation window with
warnings is the standard transition. The `revert` to `restore`
rename is the most visible name change and gets its own
release-note line.

Pitfalls. The `<group> status` verb must produce useful output
for each group, not template noise. The implementation cost
is one purpose-built status routine per group; sharing only the
output shape, not the underlying check logic.

Pathways. Once the spec subtree has a uniform CRUD shape, the
"add a workflows group" or "add a plugins group" decisions
become small. The framework gains an internal scaffolding
template for any future first-class authored-content surface.
