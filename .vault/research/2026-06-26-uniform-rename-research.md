---
tags:
  - '#research'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
related:
  - "[[2026-06-26-uniform-rename-reference]]"
  - "[[2026-05-17-cli-rename-integrity-adr]]"
  - "[[2026-05-17-cli-rename-integrity-research]]"
---

# `uniform-rename` research: `uniform feature-tag rename across all binding surfaces`

This research scopes a backend plus CLI verb that atomically renames a
`#feature` across every vault binding surface: document filenames, the exec
folder, the feature tag in `tags:`, `related:` wiki-link references, and the
feature index. The contract boundary is to rewrite frontmatter, wiki-links, and
the conformant feature tag only - never free-form body prose. Firmware
conformance to the new verb is a deliberately separate, later phase and is out
of scope here. The companion reference documents the existing machinery and the
binding-surfaces inventory.

## Findings

### Why rename is not first-class today

There is no `rename_feature` anywhere in the tree; the `feature` group exposes
only `list`, `index`, `archive`, `unarchive` (`vault_cmd.py:37`). An operator who
wants to rename a feature has two bad paths. Archive-and-re-add loses content:
`archive_feature` only moves files under `.vault/_archive/` (`query.py:298`)
where they become invisible to every scan, and `vault add` rescaffolds empty
bodies. Hand-editing the tag, every filename, the exec folder, every incoming
wiki-link, and the index is exactly the multi-surface drift the framework rules
forbid and that `vault check all` then flags (stale tags, filename-convention
violations, dangling links, a stale index). This is the same drift shape the
cli-rename-integrity ADR diagnosed for spec resources - a move that leaves
source-of-truth metadata stale - scaled to N documents and four extra surfaces.
The existing `rename_integrity` check covers only `.vaultspec/` resource name
agreement (`rename_integrity.py:35`), so feature drift is currently unchecked.

### Backend design options

The proven building blocks already exist: case-safe filename rename
(`_rename_document_path`, `structure.py:57`), the whole-tree `related:` link
cascade (`_rewrite_incoming_refs`, `structure.py:256`, which re-reads from disk
after renames land so it also fixes links inside the renamed docs themselves),
`.bak`-rollback related surgery (`related_surgery.py:75`), index regeneration
(`generate_feature_index`, `index.py:25`), and the single-doc rename precedent
(`_execute_rename`, `edit_cmd.py:818`).

- Option A - a dedicated `rename_feature(root, old, new, *, dry_run, force)` in
  `query.py` that computes the rename set (`list_documents(feature=old)` as
  `archive_feature` does), maps each path by swapping only the feature segment,
  renames files plus the exec folder, rewrites the `#old` -> `#new` tag in each
  renamed doc, delegates `related:` links to `_rewrite_incoming_refs`, and the
  index to `generate_feature_index`. Mirrors where the sibling verbs live.
- Option B - extract a shared generic rename engine used by both the structure
  cascade and the new backend. The cascade primitives are private to
  `structure.py`; reuse means lifting them into a shared module. The codebase
  already states a "one implementation, no drift" principle for related surgery
  (`related_surgery.py:10`), so a modest extraction is idiomatic.
- Option C - compose existing CLI primitives only (loop `vault rename` plus
  `set-frontmatter --tags` plus `vault feature index`). Rejected: `vault rename`
  sets an arbitrary stem, rewrites only graph-discovered links, does not know the
  feature segment or the exec folder, and gives no atomic boundary.

Recommendation: Option A as the surface, realised on a small slice of Option B.
Add `rename_feature` to `query.py`, and extract `_rewrite_incoming_refs` plus
`_rename_document_path` into a shared `vaultcore` module so the structure check
and the rename backend call one implementation. The only genuinely new logic is
the feature-segment filename/folder transform, the `#old` -> `#new` tag-block
rewriter, and the index wiring. This reuses every path already hardened for
CRLF, BOM, Windows-case, chain, cycle, and dedup edge cases.

### Atomicity strategy

The cli-rename-integrity ADR mandates atomic move-plus-metadata or rollback, and
explicitly warns that Windows atomic filesystem ops are fragile. At feature scale
many files move, so true single-syscall atomicity is impossible without renaming
a parent directory. Recommended shape: compute-plan-then-apply with a reverse
journal. Phase one computes the full plan (rename set, per-file tag rewrites,
predicted link rewrites, index plan, collisions) without mutating. Phase two
applies, recording each rename and content write; on any failure, walk the
journal in reverse (rename files back, restore `.bak`s). Finish with a
postcondition `vault check` pass. Honest framing for the ADR: existing precedents
are not globally atomic - the structure cascade renames each file then runs a
separate rewrite pass (`structure.py:760`), and `_execute_rename` sequences
rewrite -> replace -> refresh (`edit_cmd.py:906`). So the realistic bar is
per-file-atomic writes plus a cross-file reverse journal plus a postcondition
verify, not POSIX all-or-nothing.

### Validation and collision rules

Mirror `archive_feature`'s guards and the tag grammar: source must match at
least one doc (`query.py:331`); refuse an empty source or target after stripping
(`query.py:318`); target must satisfy `^[a-z0-9][a-z0-9-]*$` (`vault_cmd.py:243`)
and yield a schema-valid `#target` (`models.py:345`); reject a target equal to a
`DocType` value (`adr`, `audit`, `exec`, `plan`, `reference`, `research`,
`index`) because `_parse_feature_from_tags` would hide such a feature
(`query.py:71`). Collision: default-refuse when the target already has docs;
`--force` opts into merge, which introduces per-file path collisions the plan
phase must detect (the stem-collision guard exists in `hydration.py:447`).

### Edge cases

- Cross-feature incoming wiki-links in other features' docs are rewritten by the
  whole-tree `related:` walk - rename improves on archive, which can only warn
  about them (`query.py:334`).
- `related:` inside the renamed docs themselves is handled by the same cascade
  because it reads post-rename disk state, but only if the cascade runs after all
  renames land.
- Exec folder `{plan_date}-{feature}` and exec files
  `{plan_date}-{feature}-{suffix}.md` both embed the feature; the `{plan_date}`
  prefix must be preserved verbatim (`hydration.py:415`).
- Index: cleanest path is delete `old.index.md` and regenerate for `new` rather
  than renaming in place (`index.py:58`).
- Internal exec references: `step_id` is feature-agnostic and scope blocks list
  source paths, so both are untouched; the `[[{plan_stem}]]` entry is rewritten
  because the plan doc is renamed.
- Date-prefix preservation: use an anchored transform keyed on the date so the
  feature token is matched only in the feature segment.
- Flow-style YAML lists are not rewritten by `_rewrite_incoming_refs`
  (`structure.py:271`); the same gap would hit a flow-style `tags:`.
  `append_related_entry` already normalises flow to block (`related_surgery.py:251`)
  - borrow that, or require `vault check all --fix` clean before rename.
- Dry-run returns the full plan; `--json` uses a versioned envelope with
  canonical status (`updated` / `unchanged` / `failed`) mirroring `archive`.

### CLI surface and verification

Confirm `vaultspec-core vault feature rename <old> <new>` on `feature_app` with
two positionals (reads more naturally than a `--to` asymmetry), plus
`--dry-run`, `--json`, `--force`, `--no-hints`, and the standard `--target`.
Output mirrors `archive`: renamed count, old -> new path list, count of rewritten
cross-feature links, collision warnings, and a next-step hint. Correctness is
provable with existing checks (`check structure`, `check frontmatter`, dangling
links, `check features` for index consistency, `feature list`); recommend a
postcondition self-check that rides the diagnostics on the envelope.

### Recommended approach

Add `rename_feature(root, old, new, *, dry_run, force)` to `query.py` (Option A)
on a small extraction of the cascade primitives (the Option B slice). Sequence:
validate -> compute plan -> [dry-run returns plan] -> apply with reverse journal
(rename files plus exec folder via the case-safe renamer, rewrite each renamed
doc's tag block, run `_rewrite_incoming_refs` vault-wide, delete the old index
and regenerate the new one) -> postcondition verify -> invalidate the graph
cache. Surface as `vault feature rename` with output and envelope mirroring
`archive`.

### Open questions for the ADR

1. Atomicity bar: reverse-journal rollback (true cross-file all-or-nothing) vs
   sequenced-plus-verify (matches precedent at `structure.py:760` and
   `edit_cmd.py:906`), weighed against Windows filesystem fragility.
1. Shared-engine extraction: lift the cascade primitives into a shared module vs
   import privates vs duplicate.
1. Merge semantics under `--force`: refuse-on-any-target-doc vs true merge, and
   how to resolve per-file path collisions on merge.
1. Feature-tag surgery: a dedicated `#old` -> `#new` tag-block rewriter
   (analogous to `_ensure_index_directory_tag`, `structure.py:548`) vs reusing a
   whole-list `set-frontmatter --tags`, and whether to handle flow-style
   `tags:` / `related:`.
1. Body prose: confirm rename never touches body; decide whether to surface a
   read-only warning listing body occurrences of the old feature that become
   silent drift.
1. Index: regenerate (recommended) vs rename in place.
1. `modified` stamp policy: refresh every renamed/relinked doc for consistency,
   or only the directly-renamed ones (the cascade currently does not refresh).
1. Archived docs: confirm rename intentionally skips `.vault/_archive/`.
1. Reserved feature names: confirm validation rejects a feature whose name equals
   a `DocType` value (a pre-existing latent footgun rename can gate).
