---
tags:
  - '#adr'
  - '#cli-rename-integrity'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-rename-integrity-research]]'
---

# `cli-rename-integrity` adr: `Rename must rewrite the frontmatter name field` | (**status:** `accepted`)

## Problem Statement

The `vaultspec-core spec rules rename`, `spec skills rename`, and
`spec agents rename` verbs move the resource's directory or file
but do not rewrite the frontmatter `name:` field. After rename,
the filename and the frontmatter disagree silently. `list` shows
the new name; `show` reveals the body still carries the old name.
Identity-by-name is broken in two opposed answers at once.

Finding B8. Same dispatch path across the three rename verbs.

## Considerations

- The frontmatter is the framework's source-of-truth contract.
  When the rename verb fails to update it, the verb is
  effectively breaking the contract on the user's behalf
  without telling them.
- An atomic rewrite (file move + frontmatter update) is the
  minimum bar. Either both happen or neither happens.
- A new vault check (filename-and-frontmatter-name agreement)
  is useful for catching pre-existing inconsistencies in
  repositories that have been through unfixed renames.
- The fix interacts with the supersession/archive verbs from
  the memory-lifecycle ADR — those verbs also rewrite
  frontmatter. Consistency across all metadata-rewriting verbs
  matters; this ADR sets the pattern, and the memory-lifecycle
  verbs follow it.

## Constraints

- Renames must be atomic. A failure between move and
  frontmatter update would leave the resource in the broken
  state today's bug already produces. The implementation must
  write the new frontmatter to the new location in a single
  filesystem operation, or rollback.
- The verbs may not rewrite body content. Body cross-references
  to the old name remain the operator's responsibility. The
  contract is frontmatter only.
- Existing repositories may have prior-broken renames already
  on disk. The new check identifies them; a `--fix` mode
  rewrites the frontmatter to match the filename (the rule
  that filename wins for already-broken state is conservative
  — both filename and frontmatter could be wrong, but at least
  the filename is what callers visibly use today).

## Implementation

**Atomic rename.** When `spec * rename OLD NEW` is invoked:

1. Read the existing resource (filename `OLD`, frontmatter
   `name: OLD`).
1. Compute the new file path (filename `NEW`).
1. Build the new file content: identical body, frontmatter with
   `name: NEW`.
1. Write the new file at the new path.
1. Remove the old file.
1. Steps 4–5 happen in an atomic operation (write-then-rename,
   or rename-then-rewrite under a lock).
1. Print the canonical outcome `updated` (per the sync-
   vocabulary ADR) with the previous and new names named in
   the annotation.

If the resource lacks a frontmatter `name:` field (defensible
for builtins where the name is derived from the filename), the
rename still moves the file, but the absence is noted in the
output: `Frontmatter has no name field; filename moved only`.

**New vault check: rename integrity.** Add a check that walks
every authored resource under `.vaultspec/rules/`,
`.vaultspec/skills/`, `.vaultspec/agents/` (and provider
mirrors) and reports any resource whose filename stem disagrees
with its frontmatter `name`. The check is:

- Read-only by default. Reports each disagreement with both
  values named.
- Has a `--fix` mode that rewrites the frontmatter to match the
  filename (filename-wins) and prints the canonical outcome
  `updated` per affected resource.
- Has a `--fix-frontmatter-wins` mode that does the opposite
  (rewrites the filename to match the frontmatter), as the
  conservative alternative for operators who know the
  frontmatter is correct.

**`vault check rename-integrity --fix` vs `vault check schema`.**
The new check sits alongside the existing structural checks.
`vault check all` runs it by default. `spec doctor` includes
its results in the spec-side summary.

**Companion language updates.**

- The framework manual's section on rename semantics is
  updated to state plainly that rename rewrites both filename
  and frontmatter atomically.
- Agent personas update to know rename is a safe operation;
  the pre-fix workaround (manually editing the frontmatter
  after rename) goes away.
- The `spec * rename --help` text explicitly states the
  frontmatter rewrite as part of the operation.

## Rationale

The current behaviour silently breaks the framework's stated
source-of-truth contract. Joan's reproduction is from one
session; the same bug exists on `rules`, `skills`, `agents`
because they share dispatch. Fixing at the dispatch layer
fixes three verbs at once with the same code.

The new check is the structural safety net. Without it, any
repository that ever ran an unfixed rename remains in the
broken state forever. With it, the framework discovers and
optionally repairs the state. The two-direction `--fix`
options (filename-wins vs frontmatter-wins) acknowledge that
the operator may know which side is canonical and want to
preserve their choice; the conservative default (filename-
wins) follows what the broken state visibly looks like to
list-consuming callers today.

Atomicity matters. A write-then-rename order with explicit
rollback on failure is the right shape for any filesystem
operation that touches multiple files; this verb should adopt
the pattern as the precedent for the rest of the metadata-
rewriting verbs that the memory-lifecycle ADR introduces.

## Consequences

Gains. Rename actually renames. Identity-by-name agrees with
itself. The framework's source-of-truth contract is honoured
across the rename verb tree. The new check catches existing
broken state from prior renames.

Difficulties. Atomic filesystem operations on Windows are
historically fragile; the implementation must test on the
Windows path with care. The new check runs on every `vault check all`, adding to the per-check cost; the check is cheap
(walk the spec tree, compare filename stem to frontmatter
field) but it does add a constant.

Pitfalls. The `--fix-frontmatter-wins` flag is destructive in
the sense that it renames files. Operators must understand
that filename changes propagate to anything that already
references the resource by filename (e.g., pre-commit hook
configs). The verb prints the affected paths and asks for
confirmation when run interactively.

Pathways. With this ADR landed, the broader pattern of
"metadata-rewriting verbs must be atomic across all the state
they touch" becomes the standing rule. The memory-lifecycle
ADR's `vault adr supersede` and `vault feature archive`
inherit the same expectation: rewrite all the affected fields,
or rewrite none. The audit's silent-failure findings
(B7 edit, B8 rename, B9 archive) share the same shape: the
fix in this cluster of three ADRs is to make the contract
visible and enforce atomicity across all of them.
