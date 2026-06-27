---
tags:
  - '#adr'
  - '#framework-dir-flatten'
date: '2026-06-25'
modified: '2026-06-25'
related:
  - '[[2026-06-25-framework-dir-flatten-research]]'
---

# `framework-dir-flatten` adr: `collapse the redundant rules wrapper in the framework dir` | (**status:** `accepted`)

## Problem Statement

The installed framework directory nests every builtin resource group under a
redundant `rules/` parent: `.vaultspec/rules/rules/`, `.vaultspec/rules/skills/`,
`.vaultspec/rules/agents/`, `.vaultspec/rules/system/`, `.vaultspec/rules/templates/`,
`.vaultspec/rules/hooks/`, `.vaultspec/rules/mcps/`, and `.vaultspec/rules/reference/`.
The source builtins package `src/vaultspec_core/builtins/` is already flat, so the
extra level exists only because install seeds builtins into `<framework_dir>/rules`
rather than `<framework_dir>` itself. The duplication produces the confusing
`.vaultspec/rules/rules/` path, makes every resource one segment deeper than it needs
to be, and diverges the installed shape from the source shape it mirrors. This is phase
one of a broader builtins refactor; phase two (enrolling vaultspec-rag into the
pipeline) is parked.

## Considerations

The fulcrum is `init_paths` in `src/vaultspec_core/core/types.py`, which derives all
seven resource directories as `vaultspec / "rules" / <resource>`; flattening means
`vaultspec / <resource>`. `seed_builtins` is invoked with `<framework_dir>/rules` at
three sites in `src/vaultspec_core/core/commands.py`, and the snapshot, revert,
hydration, and rename-integrity helpers each rebuild the `rules/` segment
independently. After flattening, the resource subtree shares the `.vaultspec/` root
with the bookkeeping artifacts `_snapshots/` and `providers.json`; today the `rules/`
wrapper isolates resources from those, so once it is removed snapshot globbing and
resource discovery must explicitly exclude the bookkeeping entries. Existing installs
in the wild carry the nested layout, so an upgrade-time migration is mandatory.
Packaging needs no change: builtins are discovered through `importlib.resources` over
the package tree, not a path glob in `pyproject.toml`.

## Considered options

- **Flatten resources directly under `.vaultspec/` (chosen).** The installed layout
  mirrors the flat source layout: `.vaultspec/rules/` holds the rule files,
  `.vaultspec/skills/` the skills, and so on. One canonical level. Cost: a migration
  plus a broad path and test sweep.
- **Keep the wrapper, rename it to a non-colliding name (e.g. `builtins/`).** Removes
  only the `rules/rules/` collision, not the redundant depth, and still diverges from
  the source shape. Rejected as a half-measure.
- **Leave as-is.** Zero work, but the confusing double-`rules` path and the
  source/install divergence persist. Rejected.

## Constraints

This is the first migration registry entry to mutate `.vaultspec/` itself rather than
`.vault/` content. The registry docstring in `src/vaultspec_core/migrations/__init__.py`
documents a "migrations only mutate `.vault/`" contract and warns that bodies must not
re-enter the advisory lock (no `add_providers` or `write_manifest` calls); the new
migration must honor the lock constraint, and the contract text must be widened to admit
framework-dir relocation. The relocation also collides with itself: the wrapper is named
`rules` and one of its children is also `rules`, so `.vaultspec/rules/rules/` to
`.vaultspec/rules/` cannot be a naive rename. It requires a staged move (relocate the
non-`rules` children first, then move the inner `rules` through a temporary name), must
be idempotent, and must be safely re-runnable after a partial failure. There is no
external-library or frontier risk; this is purely internal path topology.

## Implementation

A single source-of-truth change in `init_paths` collapses the seven
`vaultspec / "rules" / <resource>` joins to `vaultspec / <resource>`. The three
`seed_builtins(fw_dir / "rules")` call sites pass `fw_dir`. The snapshot and revert
helpers in `core/revert.py` drop the `rules/` segment and gain an exclusion for
`_snapshots/` and `providers.json`, now that resources sit at the framework root; the
hydration and rename-integrity helpers drop the segment likewise; resolver warning
strings naming `.vaultspec/rules/` are reworded.

A new migration module relocates each resource directory from
`.vaultspec/rules/<resource>` to `.vaultspec/<resource>`, handles the inner `rules`
rename through a staged move, removes the emptied wrapper, and returns a
`MigrationResult` reporting relocations. It is registered in the ordered registry with a
target version equal to the release that ships this change, runs under the existing
advisory lock, mutates only the framework dir, and is idempotent. The driver already
triggers on `install --upgrade` and lazily on any `vault` command.

The test suite's roughly 180 hardcoded `.vaultspec/rules/...` path constructions and the
`setup_rules_dir` conftest fixtures move to the flat layout, and the documentation
references in `docs/framework.md` and `docs/MCP.md` are reworded.

## Rationale

The source builtins were already collapsed into `vaultspec_core.builtins` by the earlier
source-layout-collapse work; this aligns the installed shape with that source shape,
removing a divergence grounding confirmed exists only because of the seed target.
Centralizing path derivation in `init_paths` makes the structural change one edit plus
mechanical propagation, and the migration registry already supplies the upgrade
mechanism, so the cost is bounded and the change carries no runtime-library risk.

## Consequences

The layout becomes cleaner, shallower, and self-documenting: `.vaultspec/rules/` and
`.vaultspec/skills/` instead of `.vaultspec/rules/rules/` and `.vaultspec/rules/skills/`,
with install mirroring source. The cost is one-time churn - a migration, a wide but
mechanical test sweep, and doc edits - while existing installs upgrade transparently on
the next `install --upgrade` or `vault` command. A new invariant emerges: bookkeeping
artifacts (`_snapshots/`, `providers.json`) coexist with resource directories at the
framework root, so resource discovery and snapshot code must keep an explicit allowlist
or exclusion, and a regression there would let snapshots recurse into themselves.
Finally, a clean flat resource root is the surface that phase two, the vaultspec-rag
pipeline enrollment, will extend.
