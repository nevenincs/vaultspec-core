---
tags:
  - '#research'
  - '#cli-rename-integrity'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-rename-integrity` research: `spec rename leaves frontmatter name field stale`

Synthesis note for finding B8 — rename produces a two-state
inconsistency. Captures the evidence behind the sibling ADR.

## Findings

### Filename vs frontmatter disagree after rename

Joan round-3a finding [45]. After
`vaultspec-core spec skills rename A B`:

- `vaultspec-core spec skills list` reports the skill as `B`
  (the filename moved).
- `vaultspec-core spec skills show B` returns a body whose
  frontmatter `name:` field still says `A` (the frontmatter did
  not).

The verb moves the directory but does not rewrite the frontmatter
that the file declares about itself. Two source-of-truth fields
silently disagree.

### Identity-by-name is broken

A skill (or rule, or agent) has two identity candidates: the
filename stem and the frontmatter `name` field. Today the
framework reads both for different purposes. The directory layout
keys on filename. The frontmatter `name` is consumed by parts of
the rendering pipeline. After rename, the two answers differ.

Any tool that trusts the filename is correct under the new name.
Any tool that trusts the frontmatter is correct under the old
name. They cannot both be right. Today the inconsistency is
silent: no check exists for "filename and frontmatter `name`
agree".

### Sister verbs and corresponding bugs

`spec rules rename`, `spec skills rename`, `spec agents rename`
all route through the same handler. The same bug exists on all
three.

### Why a single source of truth matters

The framework's design philosophy is that the frontmatter is
authoritative metadata. `vault check schema` validates
frontmatter against documented schemas. `vault check frontmatter` checks required fields. The filename is supposed
to be a derived convenience: a sortable index into the
canonical content.

When the rename verb moves the file but not the metadata, it
inverts the design: the filename becomes authoritative and the
frontmatter becomes a stale annotation. The fix is to keep the
frontmatter as the source of truth and ensure the rename verb
updates both.

### Risk of silent breakage in downstream operations

Subsequent operations that key on `name:` (e.g., synchronisation
of a renamed rule into a provider directory, or any tool that
correlates spec resources by their frontmatter identity) will
operate against the stale value. The user will not see the
discrepancy unless they explicitly `show` the resource after
rename.

This is the same shape as the B7 silent-failure bug at a
different verb: an operation that appears to succeed (the
`list` output shows the new name) while the underlying state is
inconsistent.

## Constraints identified

- A rename of an authored resource is the user-facing
  operation; a rename of a builtin should not be possible
  (revert restores the canonical name). The fix is scoped to
  authored content.
- Some `name:` fields may reference the old name in body
  prose (cross-references, examples). The rename verb should
  not attempt body rewrites; the frontmatter is the contract.
- A new `vault check` would be useful: filename-and-frontmatter-
  name-agree. This catches existing repositories where prior
  renames left stale state.

## Recommendation

Make the rename verb rewrite frontmatter `name` atomically with
the directory move. Add a `vault check rename-integrity` check
that validates filename-and-frontmatter-name agreement across
the entire vault. Full design in the sibling ADR.
