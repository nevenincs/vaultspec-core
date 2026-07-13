---
tags:
  - '#research'
  - '#framework-dir-flatten'
date: '2026-06-25'
modified: '2026-06-27'
related: []
---

# `framework-dir-flatten` research: `framework dir rules-wrapper inventory and flatten grounding`

Grounding for the `framework-dir-flatten` decision. This inventories the contents of the
installed `.vaultspec/rules/` wrapper, contrasts them with the flat source builtins, and
maps every live code, test, and doc reference the flatten will touch. Discovery used
`vaultspec-rag` semantic search plus a targeted reference sweep.

## Findings

### Installed `.vaultspec/rules/` contents (the wrapper being removed)

The framework dir (`framework_dir` = `.vaultspec`, `DirName.VAULTSPEC`) currently holds
all builtin resources one level too deep, under a `rules/` wrapper:

- `.vaultspec/rules/rules/` - `vaultspec.builtin.md`, `vaultspec-cli.builtin.md`,
  `vaultspec-rag.builtin.md`, `.gitignore`
- `.vaultspec/rules/skills/` - ten skill dirs, each with a `SKILL.md` (plus the
  documentation skill's `agents/` and `references/` subtrees)
- `.vaultspec/rules/agents/` - ten persona `.md` files
- `.vaultspec/rules/system/` - `01-core.md`, `02-operations.md`, `03-vaultspec.md`,
  `90-custom.md`
- `.vaultspec/rules/templates/` - `adr`, `audit`, `code-review`, `exec-step`,
  `exec-summary`, `index`, `plan`, `reference`, `research` markdown templates
- `.vaultspec/rules/hooks/` - `example-audit-on-create.yaml`
- `.vaultspec/rules/mcps/` - `vaultspec-core.builtin.json`, `vaultspec-rag.builtin.json`
- `.vaultspec/rules/reference/` - `cli.md`

Bookkeeping artifacts sit as siblings of the wrapper, not inside it:
`.vaultspec/_snapshots/` (pristine `.builtin.md` copies for revert) and
`.vaultspec/providers.json` (the install manifest). The flatten moves the eight resource
dirs up to the framework root, where they will share that root with the two bookkeeping
artifacts.

### Source builtins are already flat

`src/vaultspec_core/builtins/` already holds `rules/`, `skills/`, `agents/`, `system/`,
`templates/`, `hooks/`, `mcps/`, and `reference/` directly. `seed_builtins` copies this
whole tree into a target dir; install passes that target as `<framework_dir>/rules`,
which is the sole reason the installed shape gains the extra level. The earlier
source-layout-collapse work flattened the source; this aligns install with it.

### Live reference map

- **Path fulcrum:** `init_paths` in `src/vaultspec_core/core/types.py` derives all seven
  resource dirs as `vaultspec / "rules" / <resource>`. The resource name resolver
  `_resolve_path` in `src/vaultspec_core/core/resources.py` takes its base dir as an
  argument, so it follows the fulcrum with no edit of its own.
- **Seed sites:** three `seed_builtins(fw_dir / "rules")` calls in
  `src/vaultspec_core/core/commands.py` (install, install-into-path, and upgrade paths).
- **Path consumers rebuilding the segment:** `src/vaultspec_core/core/revert.py`
  (snapshot, revert, and modified-builtins helpers, all keyed on `vaultspec_dir / "rules"`),
  `src/vaultspec_core/vaultcore/hydration.py` (templates path),
  `src/vaultspec_core/vaultcore/checks/rename_integrity.py` (resource paths), and
  `src/vaultspec_core/core/resolver.py` (warning strings only).
- **Stale docstrings:** `src/vaultspec_core/builtins/__init__.py` plus the `rules`,
  `skills`, `system`, `agents`, `hooks`, and `mcps` core modules name the nested layout
  in prose.
- **Snapshots and manifest:** snapshots live at `.vaultspec/_snapshots/<category>/`,
  already flat relative to the wrapper; `providers.json` records provider names, not
  paths, so the manifest needs no rewrite. The migration only relocates directories.
- **Tests:** roughly 180 hardcoded `.vaultspec/rules/...` constructions across the CLI,
  core, vaultcore, protocol, and top-level test trees, plus the `setup_rules_dir`
  conftest fixtures and a `rules_src_dir.name == "rules"` assertion.
- **Packaging:** none. Builtins are discovered via `importlib.resources` over the package
  tree, so `pyproject.toml` carries no path glob to update. No `MANIFEST.in` or install
  scripts reference the layout; only `docs/framework.md` and `docs/MCP.md` do.

### Migration grounding

The migration registry (`src/vaultspec_core/migrations/__init__.py`) runs every entry
whose `target_version` exceeds the manifest's recorded version, under an advisory lock on
`providers.json`, triggered on `install --upgrade` and lazily on any `vault` command.
Every existing entry mutates only `.vault/` content and the docstring states that
contract; this flatten is the first to mutate `.vaultspec/` itself, so the contract text
must widen. Two hazards drive the design: the inner `rules` child collides with its own
`rules` wrapper (so relocation needs a staged move through a temporary name, not a naive
rename), and once resources sit at the framework root the snapshot glob must exclude
`_snapshots/` and `providers.json` or it will recurse into its own copies. The migration
must be idempotent and safely re-runnable after a partial failure.
