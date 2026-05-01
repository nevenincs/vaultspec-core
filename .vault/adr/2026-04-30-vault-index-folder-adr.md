---
tags:
  - '#adr'
  - '#vault-index-folder'
date: '2026-04-30'
related:
  - '[[2026-04-30-vault-index-folder-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

# `vault-index-folder` adr: dedicated index subfolder | (**status:** `accepted`)

## Problem Statement

Generated `<feature>.index.md` files currently live at the root of `.vault/`,
mixed with the six canonical document subfolders (`adr/`, `audit/`, `exec/`,
`plan/`, `reference/`, `research/`). On this repo alone there are 55 such
files. The pollution makes the vault root unreadable and breaks the visual
symmetry of the documentation taxonomy. Indexes are auto-generated,
feature-scoped, and structurally distinct from the six existing categories,
so they deserve their own home.

## Considerations

The migration must touch every subsystem that knows about index files
(generator, scanner, classifier, five vault checkers, CLI, synthetic vault,
template). It must preserve wiki-link resolution. It must produce a clean
upgrade path for vaults that still have legacy root-level indexes. And it
must integrate with the existing tag taxonomy in a way that does not require
two parallel rules.

Key factors:

- The current `is_generated_index` predicate is filename-based, not
  location-based. That is a load-bearing invariant: every checker uses it.
  The migration should keep the filename suffix authoritative and add the
  folder as a redundant, location-based confirmation.
- Wiki-link resolution in `_build_stem_index` walks `scan_vault` which uses
  `rglob`. Indexes in a new subfolder remain reachable as `[[<feature>.index]]`
  with no resolver changes.
- The `DirName` enum and `VaultSpecConfig` already model directory names as
  configurable string constants. Extending the same mechanism for the index
  folder fits the existing shape.
- Five checkers (`structure`, `frontmatter`, `body-links`, `orphans`,
  `features`) all special-case index files. The cleanest cutover is a single
  predicate update plus structure-checker awareness of the new folder.
- The repo's own `.vault/` has 55 root-level indexes. The migration must
  succeed on real data as the final commit of this PR.

## Constraints

- No breaking changes to wiki-link resolution. Existing
  `related: "[[<feature>.index]]"` references must keep working without
  rewrites.
- Migration must be auto-fixable through `vault check --fix`. Operators
  cannot be required to run a separate migration script.
- The new directory must obey the existing taxonomy rule: every `.vault/`
  document carries exactly two tags (one directory tag, one feature tag).
- Tests must use real filesystem fixtures (`WorkspaceFactory`,
  `vaultspec_core.testing.synthetic`). No mocks, patches, stubs, or skips.
- The `spec doctor` framework error pre-existing on this repo
  (`.vaultspec/ corrupted manifest`) is out of scope; the source repo
  legitimately does not ship `providers.json`.

## Decision

Adopt the following architecture.

**Folder name and configurability.** The new subfolder is `.vault/index/`,
held as a configurable knob `VaultSpecConfig.index_dir` with default
`"index"`, mirroring the existing `docs_dir` / `framework_dir` pattern.
Resolution is `target_dir / docs_dir / index_dir`. A new `DirName.INDEX`
enum value (`"index"`) backs the default. Configurability matches the
ergonomic shape of every other framework directory; it costs nothing extra
and avoids ossifying a hardcoded path.

**Directory tag.** Indexes get a seventh directory tag `#index`, joining
`#adr`, `#audit`, `#exec`, `#plan`, `#reference`, `#research`. Index
documents henceforth carry the standard two-tag shape (`#index` plus
`#{feature}`) and the `generated: true` marker stays as a content-level
flag. This collapses the "indexes are special" case at the frontmatter
layer and lets the existing frontmatter validator run uniformly.

**`is_generated_index` predicate.** Stays filename-based
(`path.name.endswith(".index.md")`). The folder is a redundant signal, not a
replacement. Filename remains authoritative so loose files in unexpected
locations are still recognised and can be migrated by `--fix`.

**Migration via vault check structure --fix.** The structure checker gains
a "legacy root-level index" finding: any `*.index.md` file at the
`.vault/` root is an ERROR with `fixable=True`. Auto-fix relocates the
file to `.vault/index/` and adds the `#index` directory tag to its
frontmatter. The relocation is atomic (rename then frontmatter rewrite);
on failure of either step the operation rolls back.

**Scanner classification.** `get_doc_type` learns the new folder. A path
relative to `docs_dir` whose first component is `index_dir` returns
`DocType.INDEX`. The existing root-level fallback (path with `<2` parts
ending in `.index.md`) is kept for one release as a backwards-compatible
classification path, so legacy vaults that have not yet run `--fix` still
report sensibly. Once a vault is migrated, the fallback never fires.

**Generator output location.** `generate_feature_index` writes to
`docs_dir / index_dir / f"{feature}.index.md"` and creates the directory
if missing. Old root-level files are not touched by the generator;
relocation is purely the migration's responsibility.

**Synthetic vault parity.** `_apply_stale_index` writes the stale-index
pathology to `vault_dir / "index" / f"{stem}.md"` (was `plan/`) so the
synthetic corpus matches the new canonical layout.

**Template and built-in rules.** The index template comment is updated
to reflect the new home. The directory-tag table in
`.claude/rules/vaultspec.builtin.md` gains a `.vault/index/` row. The
"two tags exactly" rule is restated unchanged (indexes already conform).

## Implementation

Phase ordering:

1. Constants: add `DirName.INDEX`, `VaultSpecConfig.index_dir`,
   `CONFIG_REGISTRY` entry, helper accessor.
1. Models: extend `DocType` description, expand
   `VaultConstants.SUPPORTED_DIRECTORIES` and `SUPPORTED_TAGS` to include
   `index` / `#index`, update `validate_vault_structure` and
   `validate_filename` to accept `.index.md` only inside the new folder.
1. Generator: update `generate_feature_index` to write into the new
   subfolder.
1. Scanner: update `get_doc_type` to classify the new folder; keep root
   fallback for one release for back-compat.
1. Structure checker: implement legacy-detection finding and auto-fix
   relocation, including frontmatter `#index` tag insertion.
1. Features checker: replace `_index_exists_for` filename match with a
   subfolder-aware lookup; keep the staleness logic untouched.
1. Synthetic vault: relocate the stale-index pathology fixture.
1. Template: update the index template's frontmatter and comment.
1. Tests: update or duplicate every test that constructs a
   `<feature>.index.md` path at root; add migration tests, scanner
   classification tests, and structure-checker legacy-flagging tests.
1. Docs: README, `.vaultspec/CLI.md`, `.vaultspec/README.md`, parent-level
   `.claude/rules/vaultspec.builtin.md`.
1. Migrate this repo's own `.vault/` as the final commit.

Reference `[[2026-04-30-vault-index-folder-research]]` for the full
inventory of call sites and tests.

## Rationale

Choosing Option A (add `#index` as a seventh directory tag) over Option B
(keep indexes as a tag-less special case) follows the established taxonomy
rule that every `.vault/` document carries exactly two tags. It also lets
the frontmatter validator run uniformly across all vault files instead of
maintaining a parallel exemption path. The cost is a one-time mass edit of
55 existing index files, which the migration handles automatically.

Configurability via `VaultSpecConfig.index_dir` mirrors the existing
`docs_dir` / `framework_dir` knobs. The marginal cost is a single
`ConfigVariable` entry and a `DirName` enum value. It avoids hardcoding a
path that future deployments may need to override (e.g. multi-vault
workspaces with custom layouts).

Keeping `is_generated_index` filename-based preserves a load-bearing
invariant. Switching to a folder-based check would require coordinated
updates across five checkers and would weaken detection of misplaced
index files - which is exactly the situation the structure checker needs
to flag.

## Alternatives considered

**Hardcode the folder name.** Simpler at the call site but inconsistent
with the rest of the framework (`docs_dir`, `framework_dir`,
`claude_dir` are all configurable). Rejected.

**Move indexes to `.vault/_index/` (underscore prefix).** Would mark them
visually as "special" but breaks the directory-tag convention (no `#_index`
tag) and requires adding the prefix-handling rule to every regex. Rejected.

**Keep indexes tag-less under the new folder.** Less disruption to the 55
existing files but maintains the "indexes are special" exemption in the
frontmatter validator and breaks the "exactly two tags" promise. Rejected
in favour of full taxonomy alignment.

**Eager rename in the generator.** Have `generate_feature_index` detect
and delete the legacy root-level file at write time. Rejected because it
muddles two responsibilities (generation versus migration) and bypasses
the operator-visible `vault check --fix` workflow.

## Consequences

Positive:

- The vault root contains only the six canonical subfolders plus the new
  `index/` folder. The taxonomy is uniform.
- Tag rules are uniform: every document in `.vault/` carries exactly two
  tags. No more exemptions.
- Migration is a one-shot operation gated through `vault check --fix`,
  visible to operators.
- New `index_dir` config knob fits the existing pattern and unlocks
  multi-vault deployments where the layout might differ.

Negative:

- 55 existing index files in this repo need migrating. The auto-fix
  handles it; CI will surface any remaining issues.
- Downstream vaults running older `vaultspec-core` versions are not
  affected at the schema level (filename still drives recognition) but
  their `vault check` runs will start flagging legacy locations as
  ERROR until they upgrade and run `--fix`. This is the intended
  behaviour.
- One-release backwards-compatible scanner fallback adds a small amount
  of code that needs removing in a follow-up.
