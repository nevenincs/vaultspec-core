---
tags:
  - '#adr'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-uniform-rename-research]]"
  - "[[2026-06-26-uniform-rename-reference]]"
  - "[[2026-05-17-cli-rename-integrity-adr]]"
---

# `uniform-rename` adr: `uniform feature rename verb with atomic multi-surface rewrite` | (**status:** `accepted`)

## Problem Statement

A feature in a vaultspec vault is a `#feature` tag that binds a group of
documents across the lifecycle. The feature name is physically duplicated across
many surfaces: document filenames, the exec folder name, exec record filenames,
the `#feature` tag in frontmatter `tags:`, `related:` wiki-link stems, and the
feature index (its filename, tags, heading, and related list). Renaming a
feature is not a first-class operation today: the `feature` group exposes only
`list`, `index`, `archive`, `unarchive`. The two available paths are both
broken. Archive-and-re-add loses body content, because archived docs are
invisible to scans and `vault add` rescaffolds empty bodies. Hand-editing every
surface is forbidden by the framework rules and reliably produces the
multi-surface drift that `vault check all` then flags (stale tags,
filename-convention violations, dangling links, a stale index). This is the same
drift the cli-rename-integrity ADR diagnosed for spec resources - a move that
leaves source-of-truth metadata stale - now at feature scale: many documents
across four extra surfaces. We need a uniform, format-conformant rename verb plus
backend that updates every surface atomically. This ADR records that decision;
firmware conformance to the new verb is a deliberately separate later phase.

## Considerations

- Source-of-truth contract: frontmatter and filenames are the framework's
  identity contract. A rename that updates some surfaces but not others breaks
  that contract silently - the exact failure mode of the resource-rename bug.
- Contract boundary: rewrite filenames, the exec folder and exec record
  filenames, the `#`-prefixed `#feature` tag, `related:` wiki-links, and the
  feature index only. Free-form body prose is never touched (matching the
  cli-rename-integrity frontmatter-only constraint). Body wiki-links are already
  a schema violation, so conformant vaults carry none.
- Reuse over reinvention: the hardened machinery already exists - case-safe
  filename rename and the whole-tree `related:` link cascade (CRLF, BOM, rename
  chain, cycle, and dedup safe), `.bak`-rollback related surgery, and idempotent
  index regeneration. New code should be confined to the feature-segment
  transform, the tag-block rewriter, and the orchestration.
- Atomicity at multi-file scale: true single-syscall atomicity is impossible when
  many files move. Existing precedents (the structure cascade, the single-doc
  rename) are sequenced-then-verify, not all-or-nothing; a dependable verb argues
  for a higher bar.
- Windows and case-insensitive filesystems: the cli-rename-integrity ADR warns
  that atomic filesystem ops are fragile on Windows; the case-only rename hop in
  the cascade primitive already handles this.
- Consistency with siblings: `archive`/`unarchive` define the established shape
  (positional feature tag, `--dry-run`/`--json`, cross-link analysis, empty-tag
  guard); rename should mirror it.

## Considered options

Three axes were evaluated; the chosen option on each is marked.

Backend shape:

- Option A (chosen) - a dedicated `rename_feature()` in `query.py` composing the
  existing primitives. Mirrors where `archive`/`unarchive` live; minimal new
  surface.
- Option B (partially adopted) - extract a shared generic rename engine. Adopted
  as a slice: the cascade primitives move to a shared module so the structure
  check and rename call one implementation. A full generic engine is rejected as
  over-engineering for now.
- Option C (rejected) - compose existing CLI primitives only (loop `vault rename`
  plus `set-frontmatter --tags` plus `feature index`). `vault rename` sets
  arbitrary stems, ignores the feature segment and exec folder, and offers no
  atomic boundary.

Atomicity:

- Reverse-journal rollback (chosen) - compute the full plan, apply while
  recording every rename and content write, and on any failure walk the journal
  in reverse to restore the original state. True cross-file all-or-nothing.
- Sequenced plus postcondition verify (rejected) - lighter and matches precedent,
  but a mid-run crash leaves a partial rename, contradicting the dependability
  goal.
- Temp-staging directory or whole-vault transactional copy (rejected) - heavier
  and historically Windows-fragile.

Collision policy:

- Refuse, with `--force` to merge (chosen) - refuse when the target feature
  already has documents; `--force` merges old into the target, detecting and
  refusing any per-file path collision (same date and type after the segment
  swap).
- Always refuse on collision (rejected) - simplest, but removes the ability to
  consolidate two features via rename.

## Constraints

- Reuse depends on extracting `_rewrite_incoming_refs` and
  `_rename_document_path` from `src/vaultspec_core/vaultcore/checks/structure.py`
  into a shared `vaultcore` module with no behaviour change. The structure check
  is covered by its own tests (e.g. `test_structure_case_rename.py`), which must
  stay green - that is the regression gate for the extraction.
- The `related:` link cascade does not rewrite YAML flow-style lists, and the
  same gap applies to a flow-style `tags:`. The tag-block rewriter must normalize
  flow `tags:` to block form (borrowing the pattern in `related_surgery.py`) so
  rename is robust on imperfect inputs rather than requiring a pre-clean vault.
- The graph cache must be invalidated after rename so subsequent commands see the
  new feature.
- Reserved-name hazard: `_parse_feature_from_tags` skips `DocType`-named tags, so
  a feature literally named `adr`, `audit`, `exec`, `plan`, `reference`,
  `research`, or `index` would be invisible. Rename must reject such a target; the
  latent footgun is documented rather than silently inherited.
- Archived docs under `.vault/_archive/` are out of scan scope and intentionally
  not renamed; this is documented behaviour, not an omission.
- Parent-feature stability: this ADR builds only on stable, shipped, test-covered
  internals (`query`, `checks/structure`, `index`, `related_surgery`). No
  frontier or immature dependency.

## Implementation

High-level layering (not a plan):

1. Shared-module extraction. Lift the case-safe path renamer and the `related:`
   link-rewrite engine out of the structure check into a shared `vaultcore`
   module; the structure check imports them unchanged. This is the
   "one implementation, no drift" slice of Option B.

1. Backend `rename_feature(root, old, new, *, dry_run=False, force=False)` in
   `query.py`. It validates (non-empty old and new, source matches at least one
   doc, new is kebab-case and a schema-valid tag, new is not a `DocType` value,
   and - unless `force` - new has no existing docs); computes a plan (for every
   document of the old feature outside `_archive`, derive the new path via an
   anchored date-keyed transform that swaps only the feature segment, plus the
   exec folder rename, per-file tag rewrites, predicted link rewrites, the index
   plan, and any merge collisions); in dry-run returns the plan without mutating;
   applies under a reverse journal (rename files and the exec folder via the
   case-safe renamer, rewrite each renamed doc's `#old` to `#new` tag block
   normalizing flow form, run the link cascade vault-wide, then delete the old
   index and regenerate the new one); on any failure walks the journal in reverse
   (rename back, restore content from per-file backups); and finally refreshes the
   `modified` stamp on every renamed or relinked doc, invalidates the graph cache,
   and runs a postcondition verify whose diagnostics ride the result.

1. CLI command `vault feature rename <old> <new>` on the feature group, with
   `--dry-run` / `--json` / `--force` / `--no-hints` / `--target`. Output mirrors
   `archive`: renamed count, the old-to-new path list, the count of rewritten
   cross-feature links, collision warnings, and a next-step hint. `--json` emits a
   versioned envelope (e.g. `vaultspec.vault.feature.rename.v1`) with canonical
   status `updated` / `unchanged` / `failed` and a payload carrying the plan.

1. Verification surface. No new check is strictly required; correctness is
   provable with the existing structure, frontmatter, dangling, and features
   checks plus `feature list`. A dedicated feature-rename-integrity check is noted
   as a future candidate.

## Rationale

The research established that every hard part of this problem -
case-insensitive renames, link rewriting that preserves CRLF/BOM/anchors and
collapses rename chains, rollback-able writes, idempotent index regeneration -
already exists and is test-covered. Option A on a slice of Option B confines new,
unproven code to three small concerns while reusing the hardened paths, the
lowest-risk route to a dependable verb. The reverse-journal atomicity bar was
chosen over the lighter sequenced-and-verify because the explicit goal is a
dependable, stable rename: a partial rename on crash is precisely the drift this
work exists to eliminate, and the per-file `.bak` rollback already proven in
related surgery makes the journal cheap to build. Refuse-with-force-merge matches
the safe-by-default posture of the sibling `archive` verb while leaving a
deliberate, guarded path to consolidate features. The frontmatter-and-wiki-links
boundary inherits directly from the cli-rename-integrity decision, keeping the
contract narrow and predictable. These conclusions are grounded in the companion
research and reference documents linked in the frontmatter.

## Consequences

Gains: feature rename becomes a single safe operation; cross-feature incoming
links that `archive` could only warn about are now actually rewritten so nothing
dangles; the shared-module extraction removes a latent duplication risk between
the structure check and any future rename path; the reserved-name rejection
closes a pre-existing footgun.

Costs and difficulties: the reverse journal is the main new complexity and must
be correct on the unhappy path, which is the hardest thing to test; the shared
extraction touches a working check and risks regression if done carelessly
(mitigated by its existing tests); merge semantics under `--force` introduce
per-file collision handling that must fail safely.

Honest limits: rename does not touch archived docs or free-form prose, so a body
mention of the old feature name becomes silent drift - a read-only advisory
listing such occurrences is a possible future enhancement; flow-style frontmatter
beyond `tags:` and `related:` is out of scope. The reverse journal is held in
memory, so it rolls back on an exception raised during apply but not across a
hard process kill or power loss, which can still leave a partial rename;
crash-durable atomicity would require a write-ahead log and is out of scope for
this decision.

Pathways opened: a feature-rename-integrity check, a body-occurrence advisory,
and eventual unification of the spec-resource rename verbs onto the same shared
engine all become natural follow-ons.
