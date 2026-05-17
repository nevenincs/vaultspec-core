---
tags:
  - '#adr'
  - '#vaultspec-source-layout-collapse'
date: '2026-05-17'
related:
  - "[[2026-05-17-vaultspec-source-layout-collapse-research]]"
  - "[[2026-03-21-builtins-build-strategy-adr]]"
  - "[[2026-04-30-doctor-dev-repo-adr]]"
---

# `vaultspec-source-layout-collapse` adr: `collapse the dev-mode carve-out and relocate bundled content into the package` | (**status:** `accepted`)

## Problem Statement

The vaultspec-core source repository keeps its canonical framework content
under `.vaultspec/rules/` (forty-two leaf files across seven subdirectories)
and its human-facing manual under three top-level documents
(`.vaultspec/CLI.md`, `.vaultspec/MCP.md`, `.vaultspec/README.md`). The same
`.vaultspec/` directory is also the install target for any consumer project
that runs `vaultspec-core install`. Because the source repo doubles as a
consumer of its own framework, the two roles collide on the same path.

Two prior ADRs added carve-outs to keep the collision tractable. The
`builtins-build-strategy` ADR introduced a hatchling `force-include` rewrite
that copies `.vaultspec/rules/` into `vaultspec_core/builtins/` at wheel
build time, plus a runtime helper that walks up the source tree to locate
`.vaultspec/rules/` for editable installs. The `doctor-dev-repo` ADR
introduced a multi-signal dev-repo detector and a `--dev` authorisation flag
on `install`, `uninstall`, and `sync`, plus auto-detection in three
diagnosis collectors so `spec doctor` no longer false-positives on the
source repo.

The carve-out surface has grown to roughly forty call sites across nine
production modules, plus four dedicated test modules. Every future change
that touches install, sync, gitignore management, or framework diagnosis
must reason about the dev-mode branch. This ADR replaces the carve-outs
with a structural fix: the source repository runs `vaultspec-core install`
against itself like any consumer, and the canonical authored content lives
in the Python package source tree where it cannot collide with install
artefacts.

## Considerations

The dev-mode plumbing exists to solve three concrete problems: (a) prevent
`install`, `uninstall`, and `sync` from overwriting the canonical
`.vaultspec/rules/` content in the source repo; (b) keep the canonical
content tracked in git despite the recommended consumer-side `.gitignore`
block that lists `.vaultspec/`; (c) stop `spec doctor` from declaring the
source repo's framework `CORRUPTED` because `providers.json` (an install
artefact) is absent. All three problems disappear if the source repo is no
longer the install target for itself.

The hatchling `force-include` rewrite that maps `.vaultspec/rules/` into
`vaultspec_core/builtins/` at wheel build time was a pragmatic compromise:
it kept the authored content at a path consumers understood while shipping
it inside the wheel where the runtime helper could resolve it via
`importlib.resources`. The compromise becomes unnecessary once the authored
content moves to `src/vaultspec_core/builtins/` directly. The wheel layout
and the source layout converge.

The walk-up logic in `_builtins_root()` exists only to support editable
installs of the source repo. Once the canonical content lives in the
package source tree, both editable and wheel installs find the same content
via `importlib.resources` and the walk-up branch becomes dead code.

The three top-level documents at `.vaultspec/CLI.md`, `.vaultspec/MCP.md`,
and `.vaultspec/README.md` are human-facing prose that documents the
framework for repository visitors. They are not bundled into consumer
projects, and consumer projects have no reason to find them at
`.vaultspec/`. Moving them to a top-level `docs/` directory aligns with the
common Python project convention and removes a second source of confusion
about what `.vaultspec/` means.

## Constraints

The wheel must continue to ship the bundled content at the import path
`vaultspec_core.builtins`. The `seed_builtins`, `list_builtins`, and
`check_outdated` callers in `vaultspec_core.core.commands` and
`vaultspec_core.cli.root` consume the package at this path; any layout
change must preserve it.

Consumer projects that previously ran `vaultspec-core install` and received
a `.vaultspec/CLI.md`, `.vaultspec/MCP.md`, or `.vaultspec/README.md` at
their workspace root must not regress: this ADR has already confirmed that
none of those three files were ever seeded into consumer projects by
`seed_builtins`, so the move does not affect any consumer-side behaviour.

The bundled rule `vaultspec-cli.builtin.md` references
`.vaultspec/CLI.md` and `.vaultspec/README.md` from its body and ships into
consumer projects on install. After the move those documents no longer
exist anywhere reachable from the consumer's workspace. The references
must be rewritten to URLs (the source repository's GitHub view) so they
resolve from both the dev repo and a fresh consumer project.

The release pipeline guard in `.github/workflows/publish.yml` checks for
`.vaultspec/rules` before building the wheel. After the move that
directory will not exist; the guard must be retargeted at the new canonical
location or removed.

The pre-existing gitignore recommendation pipeline emits
`.vaultspec/_snapshots/`, `.vaultspec/*.lock`, and `.vaultspec/providers.json`
in dev mode. After the collapse the source repo's `.vaultspec/` becomes a
plain install artefact like any consumer's, so the recommended set
unconditionally includes the bare `.vaultspec/` line and these three
specialised entries become redundant under a broader rule.

The handbook drift test in `test_cli_handbook_drift.py` hardcodes the
location of `CLI.md`. The test must be retargeted at the new path before
the move lands, otherwise the test fails immediately.

## Implementation

The implementation runs as a single layout collapse with seven phases that
proceed in dependency order. Each phase produces a working tree at every
intermediate point: a partial collapse must never leave the test suite,
the build, or the wheel in an inconsistent state.

Phase one moves the canonical content. The seven subdirectories under
`.vaultspec/rules/` move into `src/vaultspec_core/builtins/` via `git mv`,
preserving history. The three top-level documents move from `.vaultspec/`
to a new `docs/` directory with `git mv`; `.vaultspec/README.md` is renamed
to `docs/framework.md` to avoid confusion with the repository README. The
now-empty `.vaultspec/` directory is removed.

Phase two flips the gitignore tracking contract. The `.gitignore` block that
excluded `src/vaultspec_core/builtins/*` is removed so the relocated content
is tracked. A new entry `.vaultspec/` is added at the top level so the
generated install directory (now produced by running `vaultspec-core install`
against this repo like any consumer) is ignored.

Phase three updates the build system. The two `force-include` blocks in
`pyproject.toml` are removed: the bundled content is already in the package
source tree, so both sdist and wheel pick it up via the standard package
discovery. The `Documentation` project URL is repointed at the new
`docs/framework.md` path. The publish workflow guard at
`.github/workflows/publish.yml` is repointed at the new canonical location
under `src/vaultspec_core/builtins/`.

Phase four collapses `_builtins_root()`. The walk-up branch is deleted; the
function returns `Path(str(resources.files(__package__)))` unconditionally.
The wheel-probe shortcut is no longer needed.

Phase five removes the dev-mode plumbing. The `guards.py` module is
deleted along with its three tests (`test_guards.py`, `test_guard_plumbing.py`,
`tests/test_dev_mode.py`). The `--dev` flag is removed from
`cmd_install`, `cmd_uninstall`, and `cmd_sync` in `cli/root.py`, and the
`dev=` parameter is removed from `install_run`, `uninstall_run`,
`sync_provider`, and `get_recommended_entries`. The auto-detect branches in
`collect_framework_presence`, `collect_gitignore_state`, and
`_execute_repair_gitignore` are removed. The `get_recommended_entries`
function unconditionally emits the bare `.vaultspec/` line whenever the
directory exists; the three specialised entries (`_snapshots/`, `*.lock`,
`providers.json`) become redundant and are removed.

Phase six repoints the test fixtures. Tests that read canonical content
from `.vaultspec/rules/...` are repointed at `src/vaultspec_core/builtins/...`.
The handbook drift test is repointed at `docs/CLI.md`. Tests that exercise
removed dev-mode constructs are deleted (the three dedicated test modules
plus the two integration tests inside `test_collectors.py`).

Phase seven updates the documentation cross-references. The repository
README is updated to link `./docs/CLI.md`, `./docs/MCP.md`, and
`./docs/framework.md`. The justfile, pre-commit config, and lychee
invocations are repointed at the new doc paths and the new bundled-content
path. The bundled rule `vaultspec-cli.builtin.md` is updated to link to the
GitHub URLs for the human documents since consumer projects no longer have
them locally. CLI command docstrings that mentioned `--dev` are stripped.

Phase eight (verification only, no production change) bootstraps the dev
repo by running `vaultspec-core install` against itself. The result must be
indistinguishable from a fresh consumer install: a `.vaultspec/` directory
is created, ignored by git, and contains `providers.json` plus the seeded
rules. `spec doctor` reports `ok` without any source-repo carve-out.

## Rationale

The carve-outs added by `builtins-build-strategy` and `doctor-dev-repo`
were correct local fixes when they landed: each solved a concrete symptom
without changing the source layout. Their combined cost has now passed the
threshold where a structural fix becomes cheaper than another local one.

The structural fix is justified by three observations from the research
inventory. First, every dev-mode branch traces back to the same root cause:
the source repo's `.vaultspec/` doubles as canonical content and install
target. Second, the hatchling `force-include` rewrite already produces a
wheel layout in which the bundled content lives in
`vaultspec_core/builtins/`, so the proposed new source layout is exactly the
existing wheel layout. Third, the human-facing documents were already
separate from the bundled content's purpose (they are not seeded into
consumers), so moving them into a conventional `docs/` directory clarifies
their role without changing what consumers see.

Reversing `doctor-dev-repo` does not regress the bug it fixed
(`spec doctor` false-positiving on the source repo); the source repo runs
the normal consumer install path, generates a normal `providers.json`, and
the corruption check passes for the right reason instead of being
suppressed by a special case.

Reversing `builtins-build-strategy` does not regress the wheel-layout
invariant it locked in; the wheel still ships content at
`vaultspec_core.builtins`, the `_builtins_root()` resolution still works via
`importlib.resources`, and the helper just stops needing to know which
layout it is running under.

## Consequences

The total carve-out surface drops by roughly forty call sites and four
test modules. Future changes to install, sync, gitignore management, or
framework diagnosis no longer need to reason about a dev-mode branch.

The source repo behaves like any consumer for the purposes of install,
sync, doctor, and the recommended gitignore block. Contributors can verify
framework changes by running `vaultspec-core install` and inspecting the
result in their own working tree, instead of mentally translating between
"editable install" and "consumer install" behaviour.

The three human-facing documents move from `.vaultspec/` to `docs/`. The
new location is conventional and unambiguous about what the documents are
for. Existing GitHub permalinks to `.vaultspec/CLI.md`, `.vaultspec/MCP.md`,
or `.vaultspec/README.md` break; we accept this since the source repo is
pre-1.0 and the links are mostly internal.

The bundled rule that ships into consumer projects loses its ability to
reference the human documents via relative paths. The rule must instead
reference the GitHub URLs. A follow-up effort is opened (out of scope
here) to author a separate machine-facing operational summary that ships
bundled into `src/vaultspec_core/builtins/` so consumers ship with a
locally-resident command reference, in addition to the human prose in
`docs/`. That follow-up work splits the current monolithic `CLI.md` into
two artefacts (human prose, machine-facing operational map); this ADR
preserves the current monolithic shape and only relocates it.

The walk-up branch in `_builtins_root()` is deleted. Any third-party
consumer who reached into the function and depended on its
editable-install fallback would break; we accept this since the function is
package-private (leading underscore) and has no documented external
contract.

The release pipeline guard becomes a one-line check pointed at the new
path. The build itself becomes simpler because the `force-include` rewrite
no longer participates.
