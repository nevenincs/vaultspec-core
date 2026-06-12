---
tags:
  - '#research'
  - '#vaultspec-source-layout-collapse'
date: '2026-05-17'
modified: '2026-05-17'
related: []
---

# `vaultspec-source-layout-collapse` research: `inventory the dev-mode carve-out and the canonical-content split`

This research grounds a planned refactor that (a) deletes the dev-mode
plumbing introduced by the prior `doctor-dev-repo` and `builtins-build-strategy`
decisions and (b) relocates the canonical bundled content into the Python
package source tree so the source repository can run a normal install against
itself. The work was triggered by the source repository owner observing that
`.vaultspec/` doubles as both authored content and an install target in this
repo, requiring an accumulating list of carve-outs to keep the two roles from
colliding.

## Findings

### Background: the two prior ADRs we are unwinding

`2026-03-21-builtins-build-strategy-adr` introduced a hatchling
`force-include` rewrite. At wheel build time the entire `.vaultspec/rules/`
tree is copied into `vaultspec_core/builtins/` inside the wheel; the source
tree keeps `.vaultspec/rules/` as the canonical content and excludes
`src/vaultspec_core/builtins/` from version control via `.gitignore`. The
runtime helper `_builtins_root()` in `src/vaultspec_core/builtins/__init__.py`
detects which layout is live (wheel vs editable install) by probing for a
`templates/` subdirectory and falls back to walking up the source tree to
locate `.vaultspec/rules/` for editable installs.

`2026-04-30-doctor-dev-repo-adr` introduced a multi-signal dev-repo detector
(`is_dev_repo`, `_cached_is_dev_repo`, `DevRepoProtectionError`,
`guard_dev_repo`) in `src/vaultspec_core/core/guards.py`. The detector
recognises the vaultspec-core source repository (or any of its worktrees) by
combining a `pyproject.toml` name match with the presence of
`src/vaultspec_core/__init__.py`. Three CLI commands (`install`, `uninstall`,
`sync`) gained a `--dev` flag that authorises writes on the source repo, and
three diagnosis collectors learnt to auto-detect the source repo and adjust
their expectations so `spec doctor` no longer false-positives on the dev tree.

Together these two ADRs work around the fact that the source repo's
`.vaultspec/` is BOTH the authored content AND the install target. Each new
collision has added a new flag, a new dev-aware branch, or a new
auto-detection. The accumulated surface is now large enough that consolidating
the source layout into the Python package (so the source repo behaves like any
consumer) is cheaper than continuing to add carve-outs.

### Dev-mode plumbing inventory

The discovery pass enumerated every callsite touched by the dev-mode
subsystem. Counts below are call sites, not raw line numbers.

Module `src/vaultspec_core/core/guards.py` defines `DevRepoProtectionError`,
`is_dev_repo`, `_cached_is_dev_repo`, and `guard_dev_repo`. The module exists
only to support the dev-mode plumbing and has no other consumers.

Module `src/vaultspec_core/core/commands.py` calls `guard_dev_repo` three
times (one per top-level command). It pipes the `dev=` keyword through to
`get_recommended_entries` in five places and through to nested
`sync_provider` invocations during install and upgrade.

Module `src/vaultspec_core/cli/root.py` defines the `--dev` Typer flag on
three commands (`cmd_install`, `cmd_uninstall`, `cmd_sync`), with matching
docstring blocks and example invocations. The flag is forwarded verbatim into
`install_run`, `uninstall_run`, and `sync_provider`.

Module `src/vaultspec_core/core/gitignore.py` keeps the `dev=` keyword on
`get_recommended_entries`. When `dev=True` the function omits the bare
`.vaultspec/` line so canonical content stays version-controlled. The
docstring carries a long explanation of the dev-shape behaviour.

Module `src/vaultspec_core/core/diagnosis/collectors.py` auto-detects the
source repo in two places: `collect_framework_presence` consults
`_cached_is_dev_repo` to suppress the corruption signal when `.vaultspec/`
exists without `providers.json`, and `collect_gitignore_state` calls
`is_dev_repo` to pick the dev-shape recommended entry set.

Module `src/vaultspec_core/core/executor.py` auto-detects the source repo in
`_execute_repair_gitignore` so the automated repair path uses the dev-shape
gitignore shape.

Module `src/vaultspec_core/builtins/__init__.py` walks up to ten directory
levels looking for `pyproject.toml`, then resolves to `.vaultspec/rules/`
under the repo root. This branch only fires in editable installs of the
source repo; consumer wheels never reach it.

Test files exercise this surface in four locations: `test_guards.py` (twelve
plus test cases for the detector and the guard policy), `test_guard_plumbing.py`
(two regression tests for `--dev` forwarding through install to sync_provider),
`tests/test_dev_mode.py` (five plus end-to-end tests on entry shape and CLI
guard behaviour), and `src/vaultspec_core/tests/cli/test_collectors.py` (two
integration tests for the framework-presence and gitignore-state collectors).

### Bundled content inventory

The canonical `.vaultspec/rules/` tree carries seven subdirectories: `agents`,
`hooks`, `mcps`, `rules`, `skills`, `system`, `templates`. They count
forty-two leaf files in total (markdown rules, agent personas, YAML hook
descriptors, JSON MCP descriptors, skill bundles).

Three top-level documents live alongside the rules tree at `.vaultspec/`:
`CLI.md` (the command reference), `MCP.md` (the MCP server reference), and
`README.md` (the framework manual). These three documents are human-facing
prose; the rules tree is the machine-facing content that ships into consumer
projects on install.

Three callers depend on the bundled-content layout via the
`vaultspec_core.builtins` module:

- `vaultspec_core.core.commands._list_builtins` walks `_builtins_root()`
  during dry-run install to enumerate what would be written.
- `vaultspec_core.core.commands.install_run` calls `seed_builtins(rules_dir, force=...)` to copy bundled content into the consumer workspace's
  `.vaultspec/rules/` during install and upgrade.
- `vaultspec_core.cli.root.cmd_spec_doctor` calls `check_outdated` to
  surface drift between the deployed and bundled content.

Tests in five files call `seed_builtins(...)` to materialise real templates
into a `tmp_path` consumer workspace before exercising the CLI or MCP server.
These tests do not care where the bundled content originates; they only need
`seed_builtins` to populate a target directory.

### Build pipeline contract

`pyproject.toml` carries two `force-include` blocks that rewrite paths during
build: the sdist block copies `.vaultspec/rules` to `.vaultspec/rules` (so the
sdist carries authored content at its source location), and the wheel block
copies the same source to `vaultspec_core/builtins` so the wheel ships with
bundled content alongside the Python package.

`.github/workflows/publish.yml` carries a guard step that fails the publish
job if `.vaultspec/rules` is missing on disk before the wheel build runs.

`.gitignore` excludes the entire `src/vaultspec_core/builtins/` tree except
for `__init__.py`. The exclusion exists precisely because the directory is
generated at build time and must not be tracked while the canonical content
lives at `.vaultspec/rules/`.

### Documentation cross-reference inventory

`README.md` links to `./.vaultspec/CLI.md`, `./.vaultspec/MCP.md`, and
`./.vaultspec/README.md` in nine locations (badge, prose, table).

`pyproject.toml` declares its `Documentation` project URL as
`https://github.com/wgergely/vaultspec-core/tree/main/.vaultspec/README.md`.

`justfile` carries four invocations of mdformat / pymarkdown / lychee that
glob over `.vaultspec/` paths, plus an explicit per-file list pinning
`.vaultspec/README.md`, `.vaultspec/MCP.md`, `.vaultspec/CLI.md`.

`.pre-commit-config.yaml` pins the wrapped-markdown hook to the regex
`^(README\.md|\.vaultspec/(README|MCP|CLI)\.md|\.vaultspec/rules/.*\.md)$`.

The bundled rule `.vaultspec/rules/rules/vaultspec-cli.builtin.md` references
`.vaultspec/CLI.md` and `.vaultspec/README.md` from its body as authoritative
references. This rule ships into consumer projects on install, so the
references must resolve in consumer projects too (not only in the source
repo).

The handbook drift test `src/vaultspec_core/tests/cli/test_cli_handbook_drift.py`
hardcodes `_HANDBOOK = _REPO_ROOT / ".vaultspec" / "CLI.md"`.

### Test fixtures asserting on canonical content

Test files in `src/vaultspec_core/tests/cli/` assert on the canonical content
location in five distinct ways:

- `test_vaultspec_rule_contracts.py` reads `PROJECT_ROOT / ".vaultspec" / "rules"` and several specific subdirectories and files (eight lines).
- `test_agents_render.py` defines `_AGENTS_SRC = _REPO_ROOT / ".vaultspec" / "rules" / "agents"` and parametrises over its contents at collection time.
- `test_install_conditions.py` and `test_ambiguous_states.py` glob
  `*.builtin.md` from the canonical rules subtree.
- `workspace_factory.py` (test helper) globs `*.builtin.md` from the same
  subtree.

These tests assert on the canonical source-of-truth content; they must
follow the content to its new home after a relocation.

A separate group of tests (fourteen files in `src/vaultspec_core/tests/cli/`)
reference `.vaultspec/rules/` as a CONSUMER-side runtime path, typically by
creating `tmp_path / ".vaultspec" / "rules"` to model a consumer workspace.
These references describe the install-time shape of a consumer project and
do not need to change when the canonical source location moves.

### What the discovery agents did NOT find

The discovery pass found no Python module that hardcodes
`.vaultspec/CLI.md`, `.vaultspec/MCP.md`, or `.vaultspec/README.md` outside
the handbook drift test. The three top-level documents are referenced only
from prose (README, bundled rules) and the one drift test.

The discovery pass found no caller of `seed_builtins`, `list_builtins`, or
`check_outdated` outside the three documented invocations in `commands.py`
and `cli/root.py` and the five test fixture call sites. The
`_builtins_root()` walk-up branch has no consumer outside its own module.

The discovery pass found no GitHub Actions workflow or external build script
that depends on the dev-mode flag, the guard module, or the dev-shape
gitignore output. The `publish.yml` guard checks only that
`.vaultspec/rules` exists before the wheel build runs.
