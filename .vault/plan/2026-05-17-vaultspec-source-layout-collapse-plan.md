---
tags:
  - '#plan'
  - '#vaultspec-source-layout-collapse'
date: '2026-05-17'
tier: L2
related:
  - "[[2026-05-17-vaultspec-source-layout-collapse-adr]]"
  - "[[2026-05-17-vaultspec-source-layout-collapse-research]]"
  - "[[2026-03-21-builtins-build-strategy-adr]]"
  - "[[2026-04-30-doctor-dev-repo-adr]]"
---

# `vaultspec-source-layout-collapse` plan

Relocate the canonical bundled content from `.vaultspec/rules/` into the
Python package source tree, move the three human-facing documents into a
new top-level `docs/` directory, delete the dev-mode carve-out, and
bootstrap the dev repo so it runs the normal consumer install path against
itself.

## Description

The work is authorised by the source-layout-collapse ADR. It reverses the
two earlier ADRs noted in the `related` chain: the builtins build strategy
(which kept canonical content at `.vaultspec/rules/` and rewrote paths at
wheel build time via hatchling `force-include`) and the doctor dev-repo
exception (which added a multi-signal source-repo detector plus a `--dev`
authorisation flag on install, uninstall, and sync). Both ADRs were correct
local fixes for the underlying collision (the dev repo's `.vaultspec/`
serves as both authored content and install target). This plan removes the
collision structurally so the carve-outs become unnecessary.

The plan is tier L2: a single linear sequence of Phases, each containing
concrete Steps. The Phases are ordered by dependency: the canonical content
must move before any code can reference the new location, the build system
must be retargeted before a wheel build can succeed, and the test fixtures
must be repointed before the test suite can pass. Within a Phase, Steps
are atomic file or symbol changes and can be applied in any order.

## Steps

### Phase `P01` - relocate canonical content

This Phase moves the authored content out of `.vaultspec/` into its new
homes (`src/vaultspec_core/builtins/` for the bundled rules tree,
`docs/` for the three human-facing documents). All moves use `git mv` so
history is preserved. The Phase ends when `.vaultspec/` no longer exists
in the source tree.

- [ ] `P01.S01` - move the agents subtree; `.vaultspec/rules/agents/` to `src/vaultspec_core/builtins/agents/`.
- [ ] `P01.S02` - move the hooks subtree; `.vaultspec/rules/hooks/` to `src/vaultspec_core/builtins/hooks/`.
- [ ] `P01.S03` - move the mcps subtree; `.vaultspec/rules/mcps/` to `src/vaultspec_core/builtins/mcps/`.
- [ ] `P01.S04` - move the rules subtree; `.vaultspec/rules/rules/` to `src/vaultspec_core/builtins/rules/`.
- [ ] `P01.S05` - move the skills subtree; `.vaultspec/rules/skills/` to `src/vaultspec_core/builtins/skills/`.
- [ ] `P01.S06` - move the system subtree; `.vaultspec/rules/system/` to `src/vaultspec_core/builtins/system/`.
- [ ] `P01.S07` - move the templates subtree; `.vaultspec/rules/templates/` to `src/vaultspec_core/builtins/templates/`.
- [ ] `P01.S08` - move the CLI reference; `.vaultspec/CLI.md` to `docs/CLI.md`.
- [ ] `P01.S09` - move the MCP reference; `.vaultspec/MCP.md` to `docs/MCP.md`.
- [ ] `P01.S10` - move and rename the framework manual; `.vaultspec/README.md` to `docs/framework.md`.
- [ ] `P01.S11` - remove the now-empty `.vaultspec/` directory from the source tree.

### Phase `P02` - flip the gitignore tracking contract

This Phase converts `src/vaultspec_core/builtins/` from a build-time-only
directory into a tracked source-of-truth directory, and adds the
consumer-shape ignore for `.vaultspec/` so the dev repo can install
vaultspec against itself without polluting `git status`. The Phase ends
when the tracked tree and the ignore set match the consumer shape.

- [ ] `P02.S12` - remove the `src/vaultspec_core/builtins/*` exclusion and the `!src/vaultspec_core/builtins/__init__.py` whitelist; `.gitignore`.
- [ ] `P02.S13` - remove the obsolete `.vaultspec/lib/` whitelist block and the `.vaultspec/.tmp/` entry; `.gitignore`.
- [ ] `P02.S14` - replace the `.vaultspec/*.lock`, `.vaultspec/_snapshots/`, and `.vaultspec/providers.json` entries inside the vaultspec-managed block with a single bare `.vaultspec/` entry; `.gitignore`.

### Phase `P03` - retarget the build system

This Phase removes the hatchling `force-include` rewrites (no longer
needed once the source layout mirrors the wheel layout), repoints the
project documentation URL at the new framework manual, and updates the
publish workflow guard. The Phase ends when a clean `uv build` produces a
wheel that ships the bundled content at `vaultspec_core/builtins/` purely
via package discovery.

- [ ] `P03.S15` - remove the sdist force-include block that mapped `.vaultspec/rules` onto itself; `pyproject.toml`.
- [ ] `P03.S16` - remove the wheel force-include block that mapped `.vaultspec/rules` to `vaultspec_core/builtins`; `pyproject.toml`.
- [ ] `P03.S17` - repoint the `Documentation` project URL from `.vaultspec/README.md` to `docs/framework.md`; `pyproject.toml`.
- [ ] `P03.S18` - retarget the wheel-precondition guard from `.vaultspec/rules` to `src/vaultspec_core/builtins`; `.github/workflows/publish.yml`.

### Phase `P04` - collapse the `_builtins_root` resolver

This Phase deletes the walk-up branch and the wheel-probe shortcut in
`_builtins_root`. With the canonical content in the package source tree,
`importlib.resources` resolves the directory unconditionally for both
editable and wheel installs. The Phase ends when the resolver is a single
unconditional return.

- [ ] `P04.S19` - delete the wheel-probe shortcut that returns `pkg_dir` when `templates/` exists alongside the module; `src/vaultspec_core/builtins/__init__.py`.
- [ ] `P04.S20` - delete the walk-up loop that searches for `pyproject.toml` and falls back to the source-repo `.vaultspec/rules/`; `src/vaultspec_core/builtins/__init__.py`.

### Phase `P05` - retire the dev-mode plumbing

This Phase deletes the source-repo detector, the `--dev` authorisation
flag, the dev-shape gitignore branch, and the dev-aware auto-detection
branches in the diagnosis and executor pipelines. The Phase ends when no
production module references `guards`, `is_dev_repo`,
`_cached_is_dev_repo`, `guard_dev_repo`, `DevRepoProtectionError`, or the
`dev=` keyword.

- [ ] `P05.S21` - delete the guards module that defines the source-repo detector and the authorisation policy; `src/vaultspec_core/core/guards.py`.
- [ ] `P05.S22` - delete the dedicated tests for the source-repo detector and the guard policy; `src/vaultspec_core/core/tests/test_guards.py`.
- [ ] `P05.S23` - delete the regression tests for the `--dev` parameter forwarding through install to sync; `src/vaultspec_core/core/tests/test_guard_plumbing.py`.
- [ ] `P05.S24` - delete the end-to-end dev-mode tests covering CLI guard behaviour and entry shape; `tests/test_dev_mode.py`.
- [ ] `P05.S25` - remove the `--dev` Typer option and its docstring block from `cmd_install`; `src/vaultspec_core/cli/root.py`.
- [ ] `P05.S26` - remove the `--dev` Typer option and its docstring block from `cmd_uninstall`; `src/vaultspec_core/cli/root.py`.
- [ ] `P05.S27` - remove the `--dev` Typer option and its docstring block from `cmd_sync`; `src/vaultspec_core/cli/root.py`.
- [ ] `P05.S28` - remove the `dev=` parameter and the `guard_dev_repo` call from `install_run`, including all internal `dev=` forwarding; `src/vaultspec_core/core/commands.py`.
- [ ] `P05.S29` - remove the `dev=` parameter and the `guard_dev_repo` call from `uninstall_run`, including all internal `dev=` forwarding; `src/vaultspec_core/core/commands.py`.
- [ ] `P05.S30` - remove the `dev=` parameter and the `guard_dev_repo` call from `sync_provider`, including all internal `dev=` forwarding; `src/vaultspec_core/core/commands.py`.
- [ ] `P05.S31` - remove the `dev=` parameter and the dev-shape branches from `get_recommended_entries`; `src/vaultspec_core/core/gitignore.py`.
- [ ] `P05.S32` - update `DEFAULT_ENTRIES` to the single `.vaultspec/` entry; `src/vaultspec_core/core/gitignore.py`.
- [ ] `P05.S33` - drop the specialised `.vaultspec/_snapshots/`, `.vaultspec/*.lock`, and `.vaultspec/providers.json` emissions made redundant by the bare `.vaultspec/` entry; `src/vaultspec_core/core/gitignore.py`.
- [ ] `P05.S34` - remove the `_cached_is_dev_repo` consultation from the framework-presence collector; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [ ] `P05.S35` - remove the `is_dev_repo` consultation from the gitignore-state collector; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [ ] `P05.S36` - remove the `is_dev_repo` consultation from the gitignore-repair executor step; `src/vaultspec_core/core/executor.py`.
- [ ] `P05.S37` - delete the dev-repo-aware framework-presence integration test; `src/vaultspec_core/tests/cli/test_collectors.py`.
- [ ] `P05.S38` - delete the consumer-near-miss multi-signal integration test; `src/vaultspec_core/tests/cli/test_collectors.py`.

### Phase `P06` - repoint test fixtures at the new canonical location

This Phase moves every test fixture that reads canonical content from
`.vaultspec/rules/...` to the new `src/vaultspec_core/builtins/...`
location, and repoints the handbook drift test at the new docs path. The
Phase ends when no production code or test reads canonical content from
the old `.vaultspec/rules/` location.

- [ ] `P06.S39` - retarget the `_AGENTS_SRC` constant used to parametrise the agents-render regression suite; `src/vaultspec_core/tests/cli/test_agents_render.py`.
- [ ] `P06.S40` - retarget the canonical-content path fixtures that assert on the skill and agent rule contracts; `src/vaultspec_core/tests/cli/test_vaultspec_rule_contracts.py`.
- [ ] `P06.S41` - retarget the canonical-content glob that asserts on `*.builtin.md` presence during install conditions; `src/vaultspec_core/tests/cli/test_install_conditions.py`.
- [ ] `P06.S42` - retarget the canonical-content glob that walks the rules subtree from the ambiguous-states regression suite; `src/vaultspec_core/tests/cli/test_ambiguous_states.py`.
- [ ] `P06.S43` - retarget the canonical-content glob inside the shared workspace factory helper; `src/vaultspec_core/tests/cli/workspace_factory.py`.
- [ ] `P06.S44` - retarget the `_HANDBOOK` constant in the CLI handbook drift guard; `src/vaultspec_core/tests/cli/test_cli_handbook_drift.py`.

### Phase `P07` - update documentation cross-references

This Phase updates every external reference to the moved documents and
the moved content tree, and strips the `--dev` mentions from the CLI
command docstrings. The Phase ends when no doc, config, or docstring
references the old paths.

- [ ] `P07.S45` - retarget the MCP badge link from `./.vaultspec/MCP.md` to `./docs/MCP.md`; `README.md`.
- [ ] `P07.S46` - retarget the CLI reference prose links from `./.vaultspec/CLI.md` to `./docs/CLI.md`; `README.md`.
- [ ] `P07.S47` - retarget the MCP reference prose links from `./.vaultspec/MCP.md` to `./docs/MCP.md`; `README.md`.
- [ ] `P07.S48` - retarget the framework manual prose links from `./.vaultspec/README.md` to `./docs/framework.md`; `README.md`.
- [ ] `P07.S49` - retarget the intra-docs framework manual cross-reference; `docs/CLI.md`.
- [ ] `P07.S50` - retarget the intra-docs framework manual cross-reference; `docs/MCP.md`.
- [ ] `P07.S51` - retarget the `mdformat --check` glob from `.vaultspec/` paths to `docs/` and `src/vaultspec_core/builtins/`; `justfile`.
- [ ] `P07.S52` - retarget the `pymarkdown scan` glob from `.vaultspec/` paths to `docs/` and `src/vaultspec_core/builtins/`; `justfile`.
- [ ] `P07.S53` - retarget the lychee link-check glob from `.vaultspec` to `docs` and `src/vaultspec_core/builtins`; `justfile`.
- [ ] `P07.S54` - retarget the `mdformat` fix-target glob from `.vaultspec/` paths to `docs/` and `src/vaultspec_core/builtins/`; `justfile`.
- [ ] `P07.S55` - retarget the wrapped-markdown hook file regex from `^(README\.md|\.vaultspec/(README|MCP|CLI)\.md|\.vaultspec/rules/.*\.md)$` to a regex covering `docs/(framework|MCP|CLI)\.md` and `src/vaultspec_core/builtins/.*\.md`; `.pre-commit-config.yaml`.
- [ ] `P07.S56` - retarget the bundled CLI reference link from `.vaultspec/CLI.md` to the source repository's GitHub URL for `docs/CLI.md`; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [ ] `P07.S57` - retarget the bundled framework manual reference link from `.vaultspec/README.md` to the source repository's GitHub URL for `docs/framework.md`; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [ ] `P07.S58` - strip the `--dev` flag mention and the source-repo-install example from the `cmd_install` docstring; `src/vaultspec_core/cli/root.py`.
- [ ] `P07.S59` - strip the `--dev` flag mention and the source-repo-uninstall example from the `cmd_uninstall` docstring; `src/vaultspec_core/cli/root.py`.
- [ ] `P07.S60` - strip the `--dev` flag mention from the `cmd_sync` docstring; `src/vaultspec_core/cli/root.py`.

## Parallelization

The Phases run in strict dependency order. `P01` must land first because
every subsequent Phase references the new canonical paths. `P02` must
land before any `vaultspec-core install` invocation against the dev repo
otherwise the install will refuse to overwrite tracked content. `P03`,
`P04`, and `P05` are independent of each other and can be applied in any
order once `P01` and `P02` have landed; the executor SHOULD treat them as
one editing batch since the test suite expects all three to be consistent.
`P06` and `P07` depend on `P01` through `P05` together; they cannot be
verified in isolation because the test suite assertions and the doc
cross-references describe the post-collapse state.

Within a Phase, individual Steps are atomic file or symbol edits with no
ordering constraint. An executor may batch Steps inside a Phase into a
single commit if the Phase as a whole produces a working tree; partial
Phase commits are not permitted because the gitignore contract, the build
system, and the dev-mode plumbing are mutually entangled and an
intermediate state cannot be tested.

## Verification

The plan is complete when every Step in every Phase is closed and the
following criteria all hold simultaneously.

- `uv run --no-sync pytest -m "not integration and not e2e"` passes the
  full unit suite with no regressions.
- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_cli_handbook_drift.py
  -v` passes against the new docs location.
- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_collectors.py
  -v` passes without the two deleted integration tests.
- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_vaultspec_rule_contracts.py
  -v` passes against the new canonical content location.
- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_agents_render.py
  -v` passes with `_AGENTS_SRC` resolving to the new canonical location.
- `uv run --no-sync ty check src/vaultspec_core` is clean.
- `uv run --no-sync ruff check src tests` and
  `uv run --no-sync ruff format --check src tests` are clean.
- `uv build` produces a wheel that ships the bundled content at the
  expected import path `vaultspec_core/builtins/` without any
  `force-include` rewrite in `pyproject.toml`.
- `git grep -nE 'is_dev_repo|guard_dev_repo|_cached_is_dev_repo|DevRepoProtectionError|--dev|dev: bool'`
  returns zero matches in `src/` and `tests/` (the `uv sync --dev` shell
  command inside the project-coordinator agent body is the only allowed
  occurrence and is unrelated to the source-repo guard).
- `uv run --no-sync vaultspec-core install` against a fresh checkout of
  the source repository succeeds without `--dev`, creates a `.vaultspec/`
  directory at the workspace root, leaves it untracked in `git status`,
  and produces a `.vaultspec/providers.json` manifest.
- `uv run --no-sync vaultspec-core spec doctor` against the freshly
  installed source repository reports `framework: ok / present` without
  any source-repo carve-out.
- `uv run --no-sync vaultspec-core vault check all` passes.
- `uv run --no-sync prek run --all-files` passes.
- A `git commit` and `git push` on the working branch succeed without
  `--no-verify`. If any push needs `--no-verify` after the collapse
  lands, the collapse is incomplete.
