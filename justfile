# ===========================================================================
#  vaultspec-core development harness
#
#  Every entry point is a FLAT HYPHENATED recipe named `<verb>-<thing>` -
#  `just check-type`, `just test-broad`, `just fix-markdown`. There is no
#  `target` argument anywhere: the thing a recipe acts on is part of its name,
#  so `just --list` is the complete surface and tab completion reaches every
#  one of them. Run `just` for the annotated recipe list, grouped by
#  CONSEQUENCE.
#
#  PLATFORM AGNOSTIC BY CONSTRUCTION. Every recipe body below is a single
#  command with no shell branching, no pipes, no conditionals, and no `sh`
#  versus PowerShell dialect. All of the logic - step chaining, tool-or-Docker
#  fallback, advisory-versus-gating exit codes - lives in the modules directly
#  under `dev/`, which import only the standard library and therefore behave
#  identically on every platform. There is no shell script backing this file.
#  To change what a recipe runs, edit `dev/toolchain.py`, which is the single
#  declarative source of truth for the whole toolchain.
#
#  The sub-packages beside those modules - `dev/audit`, `dev/binaries`,
#  `dev/health`, `dev/statistics` - are the INSTRUMENTS the recipes invoke when
#  a measurement or a build is too large to express as a command line. They are
#  free to depend on whatever they measure with, which is exactly why they sit
#  one level down from the stdlib-only dispatch core rather than inside it.
#  Each carries its own cohabiting `tests` package.
#
#  One instrument lives OUTSIDE `dev/`: the documentation-asset renderers in
#  `docs/_render/`, which sit with the `docs/assets/` output they write rather
#  than with the tooling that invokes them. `just docs-all` drives them.
#
#  Two sub-packages beside the instruments are not instruments at all.
#  `dev/guards` holds the repository-health guards - the checks on these
#  recipes, on the CI workflows, on `pyproject.toml`, on the installed
#  `.vaultspec/templates` and on `typings/` - which have no module to cohabit
#  with because their subject is this checkout's own configuration. They carry
#  the `repo` pytest marker and `just test-repo` selects them BY THAT MARKER
#  across every tree, so a repository-health guard is gated by what it asserts
#  rather than by where it is filed; `just test-unit` and `just test-broad`
#  exclude the same marker, so the library lanes never run them.
#  `dev/smoke` holds the distribution smoke check, run by path against a built
#  wheel and sdist by `.github/workflows/publish.yml`, never by pytest.
#
#  The GROUPS split by CONSEQUENCE, not by tool. The taxonomy is a closed set
#  of ten, identical in every repository:
#
#    setup    Provisioning and dependency resolution. MUTATES the environment.
#    dev      Day-to-day operations on this checkout that are not gates.
#    check    GATES.    Read-only, and a finding fails the build.
#    fix      MUTATES.  Everything automatically repairable, in one pass.
#    audit    ADVISORY, and exits 0 even with findings, because each yields a
#             lead to confirm. `audit-deps` is the ONE exception: a published
#             advisory against a pinned version is a verdict, so it gates.
#    build    Produces artifacts from a plain checkout.
#    release  Actions that need a published tag.
#    docs     Regenerates committed documentation assets.
#    test     GATES.
#    meta     The recipe list and the composed pipeline.
#
#  NO TOOL IS MIRRORED HERE. `vaultspec-core` and `vaultspec-rag` are finished
#  products with their own CLIs and their own MCP servers; wrapping either one
#  only adds a layer that can drift out of step with it. Invoke them directly
#  (`uv run --no-sync vaultspec-core ...`, `uv run --no-sync vaultspec-rag ...`
#  or the MCP tools). That applies to rag's whole surface - the search service,
#  its lifecycle, and its indexes are rag's to manage, not this harness's.
#
#  What this file does expose is the operations the repository performs on
#  ITSELF - its own `.vault/` corpus and its own `.vaultspec/` harness - as the
#  `vault-*` and `framework-*` recipes, because those are development actions
#  on this checkout rather than product usage.
# ===========================================================================

set quiet := true

# Requires just >= 1.38 (`set working-directory`, native modules, `[doc]`/`[group]`).
#
# just defaults to `sh -cu` on every platform, which on Windows means a Git Bash
# `sh.exe` that is only on PATH for some Git for Windows install options. This
# names the one interpreter every Windows machine is guaranteed to have.
#
# `cmd` is chosen for EXIT-CODE FIDELITY, not familiarity. It forwards a native
# command's status verbatim; `pwsh -Command` and `powershell -Command` collapse
# every non-zero status onto 1, which would erase this harness's own exit codes
# and destroy the advisory-versus-gating split the recipe groups are built on.
# cmd's weaknesses - `%VAR%` expansion and no single-quote literal - cost
# nothing here, because every recipe body below is a single command with no
# shell syntax and no recipe body contains either character.
set windows-shell := ["cmd.exe", "/c"]

# Every recipe that merely *uses* the environment goes through `uv run
# --no-sync`. Skipping the sync keeps `uv run` from re-resolving and rebuilding
# the project into `.venv`, which fails on Windows whenever a resident process
# - an MCP server, an editor, another agent's session - holds one of the
# console-script executables open. The recipes whose purpose IS to change the
# environment call `uv` directly, inside `dev/`.
dev := "uv run --no-sync python -m dev"

# List every recipe, grouped by consequence.
[group('meta')]
default:
    @just --list

# ===========================================================================
#  setup
# ===========================================================================

# `init` is the one command a fresh worktree needs, and the command git
# tooling and the worktree provisioner call after creating one. It cannot
# route through `{{dev}}`, which presumes the environment `init` is
# responsible for creating; it runs on an ephemeral interpreter instead, and
# `dev/init/` is stdlib-only for exactly that reason.
#
# Idempotent: a second run costs a stamp comparison and touches nothing.
# `just init-check` verifies without mutating, exiting 3 when the worktree is
# not initialized, which is what a hook or a provisioner calls. Set
# VAULTSPEC_INIT_JSON=1 for an NDJSON event stream, VAULTSPEC_INIT_FORCE=1 to
# ignore the stamp. Every run writes `.venv/init-report.json`.
#
# The phases run in dependency order and stop at the first failure: unlike the
# `-all` aggregates, which chain independent inspectors and run every one,
# these build one artifact, and `init-tools` runs executables out of the
# environment `init-python` creates. The report still lists every phase, with
# the ones that were not attempted naming the failure that stopped them.

# Initialize a fresh clone or worktree: dependencies, framework, hooks, .env.
[group('setup')]
init:
    uv run --no-project --python 3.13 -- python -m dev.init all

# Resolve the locked Python development toolchain into .venv.
[group('setup')]
init-python:
    uv run --no-project --python 3.13 -- python -m dev.init python

# Restore the pinned Node dependency graph. A no-op in this repository.
[group('setup')]
init-node:
    uv run --no-project --python 3.13 -- python -m dev.init node

# Enroll the Vaultspec framework and install the committed git hooks.
[group('setup')]
init-tools:
    uv run --no-project --python 3.13 -- python -m dev.init tools

# Report whether this worktree is initialized. Mutates nothing; exits 3 if not.
[group('setup')]
init-check:
    uv run --no-project --python 3.13 -- python -m dev.init check

# Install the locked dependency set.
[group('setup')]
deps-sync:
    {{dev}} deps sync

# Upgrade every dependency group.
[group('setup')]
deps-upgrade:
    {{dev}} deps upgrade

# Regenerate the lockfile.
[group('setup')]
deps-lock:
    {{dev}} deps lock

# Regenerate the lockfile at the newest allowed versions.
[group('setup')]
deps-lock-upgrade:
    {{dev}} deps lock-upgrade

# Verify the lockfile matches pyproject.toml.
[group('setup')]
deps-check:
    {{dev}} deps check

# ===========================================================================
#  check - GATES. Read-only, and a finding fails the build.
# ===========================================================================

# Ruff lint and format verification.
[group('check')]
check-python:
    {{dev}} lint python

# Ty type checking.
[group('check')]
check-type:
    {{dev}} lint type

# `check-type` above checks whichever platform it runs on, so a Windows
# contributor's green is not Linux's green: this repository carries both
# `msvcrt`/`ctypes.WinDLL` and `fcntl` paths, and a platform-specific attribute
# resolves on one OS and not the other. CI runs Linux, so unguarded
# Windows-only code passed every local gate and failed only after push - the
# exact "green here, red there" split a gate exists to prevent. Checking all
# three targets makes the local run reproduce CI regardless of the host.

# Ty type checking against every target platform.
[group('check')]
check-type-platforms:
    {{dev}} lint type-platforms

# TOML formatting verification.
[group('check')]
check-toml:
    {{dev}} lint toml

# Verify every documentation link resolves.
[group('check')]
check-links:
    {{dev}} lint links

# Markdown formatting and structure verification.
[group('check')]
check-markdown:
    {{dev}} lint markdown

# GitHub Actions workflow verification.
[group('check')]
check-workflow:
    {{dev}} lint workflow

# Each of the three below is a real gate whose burndown is unfinished, so none
# is a member of `check-all`: chaining one in would hide every dimension behind
# it. Run them by name until each can hold its line, then move it up.
# `check-type-strict` is NOT one of them - it holds its line and is a member.

# Gate cyclomatic and cognitive complexity.
[group('check')]
check-complexity:
    {{dev}} lint complexity

# Gate nesting depth.
[group('check')]
check-nesting:
    {{dev}} lint nesting

# Gate module length and class design limits.
[group('check')]
check-size:
    {{dev}} lint size

# Type checking under the strict profile.
[group('check')]
check-type-strict:
    {{dev}} lint type-strict

# AGGREGATES RUN EVERY STEP and exit with the first non-zero status; they do
# not stop at the first failure. An aggregate is asked for a complete picture,
# and fail-fast costs a CI round-trip per defect. That is why this dispatches
# into `dev/` rather than listing its members as just dependencies: a
# dependency chain cannot express run-all-then-report. The membership lives in
# `dev/toolchain.py` as references to the same targets the individual recipes
# above run, so this aggregate and those gates cannot disagree.
# `check-complexity`, `check-nesting` and `check-size` are deliberately NOT
# members - see the note above them.

# Run every gating static-analysis dimension that holds the line today.
[group('check')]
check-all:
    {{dev}} lint all

# ===========================================================================
#  fix - MUTATES. Everything automatically repairable, in one pass.
# ===========================================================================

# Format and auto-fix Python.
[group('fix')]
fix-python:
    {{dev}} fix python

# Format TOML files.
[group('fix')]
fix-toml:
    {{dev}} fix toml

# Format and repair markdown.
[group('fix')]
fix-markdown:
    {{dev}} fix markdown

# Repair this repository's own .vault/ corpus.
[group('fix')]
fix-vault:
    {{dev}} fix vault

# Apply every automatic fix, in one pass.
[group('fix')]
fix-all:
    {{dev}} fix all

# ===========================================================================
#  audit - ADVISORY, except `audit-deps`, which gates.
# ===========================================================================

# GATES. A published advisory against a pinned version is a verdict, not a
# lead, which is why this one recipe in the group fails the build.

# Gate on published advisories against the locked versions.
[group('audit')]
audit-deps:
    {{dev}} audit deps

# Scan for insecure patterns; advisory, exits 0.
[group('audit')]
audit-security:
    {{dev}} audit security

# Report unreachable code; advisory, exits 0.
[group('audit')]
audit-dead-code:
    {{dev}} audit dead-code

# Report undeclared and unused dependencies; advisory, exits 0.
[group('audit')]
audit-dependencies:
    {{dev}} audit dependencies

# Report test-tree complexity; advisory, exits 0.
[group('audit')]
audit-complexity:
    {{dev}} audit complexity

# Report every advisory dimension; one red dimension does not hide the rest.
[group('audit')]
audit-all:
    {{dev}} audit all

# MEASUREMENT ONLY - always exits 0. Composes the gates rather than
# re-implementing any threshold, so the report and the gate cannot disagree.
# `just health-census` regenerates the distributions each baseline ratchet in
# pyproject.toml is calibrated from; run it before lowering a threshold.

# Rank the worst offenders across every code-health dimension.
[group('audit')]
health-report:
    {{dev}} health report

# The same report, skipping the strict type check.
[group('audit')]
health-fast:
    {{dev}} health fast

# Regenerate the distributions the baseline ratchets are calibrated from.
[group('audit')]
health-census:
    {{dev}} health census

# ===========================================================================
#  test - GATES.
# ===========================================================================

# Run the library unit lane.
[group('test')]
test-unit:
    {{dev}} test unit

# Run the broad library lane - what CI proves.
[group('test')]
test-broad:
    {{dev}} test broad

# Run the vault-repair lane.
[group('test')]
test-vault-repair:
    {{dev}} test vault-repair

# Run the benchmark lane.
[group('test')]
test-benchmark:
    {{dev}} test benchmark

# Run the harness lane.
[group('test')]
test-harness:
    {{dev}} test harness

# Run the repository-health guards, selected by the `repo` marker.
[group('test')]
test-repo:
    {{dev}} test repo

# Run every test lane.
[group('test')]
test-all:
    {{dev}} test all

# ===========================================================================
#  build
# ===========================================================================

# Build the Python wheel and sdist.
[group('build')]
build-python:
    {{dev}} build python

# Build every artifact producible from a plain checkout.
[group('build')]
build-all:
    {{dev}} build all

# ===========================================================================
#  dev - this checkout's own vaultspec records and harness
# ===========================================================================

# Validate this repository's own .vault/ corpus.
[group('dev')]
vault-check:
    {{dev}} vault check

# Repair this repository's own .vault/ corpus.
[group('dev')]
vault-fix:
    {{dev}} vault fix

# Render the .vault/ record graph.
[group('dev')]
vault-graph:
    {{dev}} vault graph

# Rebuild the .vault/ index.
[group('dev')]
vault-index:
    {{dev}} vault index

# List the .vault/ records.
[group('dev')]
vault-list:
    {{dev}} vault list

# Report .vault/ corpus statistics.
[group('dev')]
vault-stats:
    {{dev}} vault stats

# Report .vault/ corpus status.
[group('dev')]
vault-status:
    {{dev}} vault status

# Diagnose this repository's own .vaultspec/ framework harness.
[group('dev')]
framework-doctor:
    {{dev}} framework doctor

# Install this repository's own .vaultspec/ framework harness.
[group('dev')]
framework-install:
    {{dev}} framework install

# Upgrade this repository's own .vaultspec/ framework harness.
[group('dev')]
framework-upgrade:
    {{dev}} framework upgrade

# Reconcile this repository's own .vaultspec/ framework harness.
[group('dev')]
framework-sync:
    {{dev}} framework sync

# Regenerate the framework CLI reference.
[group('dev')]
framework-reference:
    {{dev}} framework reference

# Verify the framework CLI reference is current.
[group('dev')]
framework-reference-check:
    {{dev}} framework reference-check

# Report the installed framework providers.
[group('dev')]
framework-providers:
    {{dev}} framework providers

# Dev-only and unshipped: it reads the operator's own ~/.claude and ~/.codex
# transcripts and writes into the gitignored dev/statistics/out/. Every
# machine-varying input is a flag with a home-derived default, so the bare
# invocation is the normal one. Pass --help for the flag list.

# Report CLI usage analytics from the local agent transcript corpora.
[group('dev')]
analytics *args='':
    uv run --no-sync python -m dev.statistics {{args}}

# ===========================================================================
#  docs
#
#  The renderers live in `docs/_render/` and write into `docs/assets/`, so
#  these recipes regenerate the committed documentation assets.
# ===========================================================================

# Regenerate the committed documentation renders.
[group('docs')]
docs-renders:
    {{dev}} docs renders

# Regenerate the committed documentation demo.
[group('docs')]
docs-demo:
    {{dev}} docs demo

# Regenerate every committed documentation asset under docs/assets/.
[group('docs')]
docs-all:
    {{dev}} docs all

# ===========================================================================
#  release
# ===========================================================================

# Parameterised rather than a fixed build recipe, and a release-workflow action
# rather than a routine local build. `tag` is the release tag (e.g.
# vaultspec-core-v0.1.53); `rust_target` is a cargo triple (e.g.
# x86_64-pc-windows-msvc).

# WHAT THIS REPRODUCES is a published release, which is why it needs no wheel
# argument. The binaries carry their application, so nothing is resolved at
# launch - but something has to be resolved at BUILD time to fill the prepared
# distribution, and without `--wheel` that is `vaultspec-core==<tag>` from
# PyPI. The tag must therefore already be published for this recipe to run.
# The release workflow passes the wheel it just built instead, which is what
# makes publication a peer of the binaries there rather than an upstream.

# `--no-project` matches .github/workflows/binaries.yml exactly: the binary
# build runs against a bare interpreter with no project environment, so a local
# reproduction and the release workflow invoke the script identically.

# Build the offline PyApp binaries for one release tag and Rust target.
[group('release')]
release-binaries tag rust_target outdir='dist-bin':
    uv run --no-project --python 3.13 -- python dev/binaries/build_pyapp.py --tag {{tag}} --target {{rust_target}} --outdir {{outdir}}

# `root` is REQUIRED and is a checkout of nevenincs/homebrew-tap - the account
# channel root, which is where these pointers live. It used to default to this
# repository, which quietly wrote into a local `bucket/` and `Formula/` that the
# release job never read; the two roots drifted four releases apart before anyone
# noticed, and every install instruction named the stale one. See
# docs/channels.md. Point `checksums` at the release's SHA256SUMS.

# Regenerate and validate a release's channel pointers, as the release job does.
[group('release')]
release-channels tag root checksums='dist-bin/SHA256SUMS':
    uv run --no-project --python 3.13 -- python -m dev.packaging.generate --tag {{tag}} --checksums {{checksums}} --root {{root}}
    uv run --no-project --python 3.13 -- python -m dev.packaging.validate --root {{root}}

# ===========================================================================
#  meta
# ===========================================================================

# `test-broad` rather than `test-unit` on purpose. This mirrors what CI proves,
# so a green run here means what a green CI run means.

# Run the full local gate: static analysis, dependency audit, vault, tests.
[group('meta')]
ci:
    {{dev}} ci all
