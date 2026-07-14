---
tags:
  - '#research'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-13-install-mode-adr]]"
---

# `install-parity` research: `companion-project provisioning parity`

Vaultspec-core and vaultspec-rag are companion projects, so their scaffolding,
installation commands, flags, and behaviors must be analogous: a consumer must be
able to provision both in exactly the same manner. Core just shipped mode-aware
provisioning (the `install-mode` feature: a persisted tool-versus-dependency mode,
committed `.vaultspec/workspace.json`, uvx renderers, a mode-aware doctor, a version
floor, and upgrade inference). This research inventories vaultspec-rag's entire
install surface against that machinery and analyzes whether the three placements the
user names - fully integrated project dependency, development-group dependency, and
tool-only - require a third persisted mode or stay a detection detail under two.

## Findings

### Rag's install surface today

- `vaultspec-rag install` performs BOTH workspace enrollment and environment
  provisioning in one verb. Enrollment (`src/vaultspec_rag/commands/_install.py:172-190`)
  seeds rag's builtin rules/mcps/skills into the consumer's `.vaultspec/` and then
  calls core's own `sync_provider("all", ...)` - the enrollment pipe is core's
  machinery byte-for-byte, so rag already writes into the consuming project's tree
  exactly the way core does. Provisioning (`_install.py:241-263`) is rag-specific:
  torch (patches the consumer's `pyproject.toml` with a cu130 index pin), model
  downloads, and the pinned qdrant binary.
- Flags: `--target`, `--upgrade`, `--dry-run`, `--force`, `--skip`, `--json` mirror
  core; rag adds `--torch-config`, `--torch-group [NAME]` (PEP 735 placement,
  default `dev`), `--yes`, `--sync`, `--provision/--no-provision`, `--mcp/--no-mcp`,
  `--local-only`, and per-component skips. There is NO `--mode` flag anywhere in rag.
- rag's only persisted choice, the `--local-only` backend marker, is written to
  `~/.vaultspec-rag/local-only.json` (`config.py:225-250`) - per-host, gitignored,
  unversioned. The committed-versus-per-machine state separation is therefore
  INVERTED relative to core: core commits the shared declaration and gitignores the
  manifest; rag has only the per-machine side and no committed counterpart.
- rag's builtin MCP definition (`src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`)
  is a static, concrete `{"command": "uv", "args": ["run", "vaultspec-search-mcp"]}`.
  Core's renderer passes token-free definitions through unchanged, so rag's MCP
  entry always renders the dependency-mode shape regardless of the workspace's
  declared mode - the exact venv coupling core just fixed for itself.
- No version floor, no mode inference on `--upgrade` (it only re-seeds bundled
  files), no doctor parity: `server doctor` reports dependency readiness and live
  service health only, with no install-mode or floor rows.
- The rag repository itself declares `vaultspec-core>=0.1.27` as a direct project
  dependency (`pyproject.toml:26`) and is a core-provisioned workspace, but carries
  no `.vaultspec/workspace.json` - its own mode is undeclared.

### Parity table

| Core concept                                           | Rag equivalent                                                                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `--mode {tool,dependency}` flag                        | absent                                                                                                             |
| Committed `.vaultspec/workspace.json` declaration      | absent; nearest analogue is the per-host `local-only.json`, which is orthogonal (storage backend, not launch mode) |
| pyproject detection feeding mode resolution            | absent for launch mode; rag's flag > env > persisted > default chain exists but resolves the backend choice        |
| Mode-neutral MCP definition + sentinel-token renderer  | absent - static `uv run` JSON that bypasses the renderer                                                           |
| Legacy-workspace dependency rendering bridge           | absent                                                                                                             |
| Doctor mode row + observed-versus-declared drift check | absent                                                                                                             |
| `minimum_vaultspec_version` floor                      | absent                                                                                                             |
| Upgrade mode inference                                 | absent                                                                                                             |
| Consuming-project enrollment pipe                      | SHARED - rag reuses core's `seed_builtins` + `sync_provider`                                                       |

### The three-placement question

- PEP 621 `[project.dependencies]` is runtime metadata embedded in built
  distributions: placement (1) leaks the harness to every downstream consumer of
  the project. PEP 735 `[dependency-groups]` is explicitly excluded from any built
  distribution: placement (2) is invisible downstream. This is the substantive
  difference between the two dependency placements - shipping semantics, not
  resolution.
- uv syncs the DEFAULT `dev` group on every `uv sync`/`uv run` without flags, so
  for the default dev group the rendered artifacts (uv run hooks, uv run MCP
  launch) behave byte-identically to a project dependency. A third mode scoped to
  the default dev group changes NOTHING in rendering - it is bookkeeping plus a
  sharper doctor label ("dev-scoped, will not leak" versus "runtime dep, will
  leak").
- NAMED groups are where real divergence lives: a non-default group needs
  `--group <name>` threaded into every `uv run`, which the rendered hook entries
  and MCP launch do not carry; and rag's own torch code documents that
  `[tool.uv.sources]` pins are silently inert on group-placed dependencies until
  the group is enabled (`_torch_flow.py:206-267`). Supporting named groups would
  make the group name itself persisted state, not just an enum member.
- Precedent inside the family: rag's torch flow already implements a three-way
  placement (project deps / named group / skip) with a warn-don't-migrate posture
  on conflicting existing placements. Ecosystem-wide, no dev-tool (pytest, ruff,
  mypy, prek) refuses runtime-dependency placement; the convention is guidance
  only.
- Companion coupling: rag is torch/GPU-heavy, so core-as-dependency with
  rag-as-tool is a legitimate and likely COMMON simultaneous configuration. The
  current `workspace.json` schema has a single `install_mode` key with no package
  axis. Two candidate shapes: (a) single mode plus per-package overrides
  (`{"install_mode": "dependency", "overrides": {"vaultspec-rag": "tool"}}`) -
  minimal, backward-compatible, but undersells how common divergence will be; (b)
  a per-package map as the primary shape
  (`{"packages": {"vaultspec-core": "...", "vaultspec-rag": "..."}}`) - symmetric
  for N companions but a breaking schema change requiring migration.
- Flag vocabulary: uv's own naming (`--dev`, `--group`, extras) suggests
  `--mode tool|dependency|dev` if a third mode is adopted, scoped to the default
  dev group (the rendering-identical case).

## Sources

- Rag surface: `src/vaultspec_rag/commands/_install.py:8-10,34,47-48,77-83,142-152, 172-190,224-263`, `src/vaultspec_rag/cli/_install.py:48-217`,
  `src/vaultspec_rag/config.py:34-121,190-250,318-329`,
  `src/vaultspec_rag/commands/_torch_flow.py:206-267`,
  `src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`,
  `src/vaultspec_rag/workspace.py`, `src/vaultspec_rag/cli/_service_doctor.py`,
  rag `pyproject.toml:19-36,63-65` (all under `Y:/code/vaultspec-rag-worktrees/main`).
- Core reference: `src/vaultspec_core/core/enums.py:299-343`,
  `core/workspace_mode.py:47-63,194-243`, `core/mcps.py:41-80`,
  `core/diagnosis/collectors.py:731-933`, `cli/root.py:231-241`.
- Standards and uv: https://peps.python.org/pep-0621/, https://peps.python.org/pep-0735/,
  https://docs.astral.sh/uv/concepts/projects/dependencies/,
  https://docs.astral.sh/uv/concepts/projects/sync/,
  https://docs.astral.sh/uv/reference/cli/,
  https://pydevtools.com/handbook/explanation/what-is-pep-735/.
