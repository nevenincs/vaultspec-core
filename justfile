# ===========================================================================
#  vaultspec-core development harness
#
#  Every entry point is a top-level verb; behaviour within a verb is selected
#  by a `target` argument - `just lint type`, `just test broad`, `just fix
#  markdown`. Run `just` for the annotated recipe list, and `just <verb> help`
#  (or any unrecognised target) for that verb's targets with descriptions.
#
#  PLATFORM AGNOSTIC BY CONSTRUCTION. Every recipe body below is a single
#  command with no shell branching, no pipes, no conditionals, and no `sh`
#  versus PowerShell dialect. All of the logic - target dispatch, step
#  chaining, tool-or-Docker fallback, advisory-versus-gating exit codes - lives
#  in the `dev/` Python package, which imports only the standard library and
#  therefore behaves identically on every platform. There is no shell script
#  backing this file. To change what a target runs, edit `dev/toolchain.py`,
#  which is the single declarative source of truth for the whole toolchain.
#
#  The verbs split by CONSEQUENCE, not by tool:
#
#    lint   GATES.    Read-only, and a finding fails the build.
#    fix    MUTATES.  Everything automatically repairable, in one pass.
#    audit  Only `deps` gates. Every other target is advisory and exits 0
#           even with findings, because each yields a lead to confirm.
#    test   GATES.    `just test help` states what each lane proves.
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
#  `vault` and `framework` verbs, because those are development actions on this
#  checkout rather than product usage.
# ===========================================================================

set positional-arguments := false
set quiet := true

# just defaults to `sh -cu` on every platform, which on Windows means a Git Bash
# `sh.exe` that is only on PATH for some Git for Windows install options. This
# names the one interpreter every Windows machine is guaranteed to have. It is a
# shell DECLARATION, not platform-specific logic: because each recipe body below
# is a single command with no shell syntax, `cmd` and `sh` execute all of them
# identically, and there is no second dialect of anything to maintain.
set windows-shell := ["cmd.exe", "/c"]

# Every recipe that merely *uses* the environment goes through `uv run
# --no-sync`. Skipping the sync keeps `uv run` from re-resolving and rebuilding
# the project into `.venv`, which fails on Windows whenever a resident process
# - an MCP server, an editor, another agent's session - holds one of the
# console-script executables open. The recipes whose purpose IS to change the
# environment call `uv` directly, inside `dev/`.
dev := "uv run --no-sync python -m dev"

# List available recipes.
default:
    @just --list

# ===========================================================================
#  Bootstrap
# ===========================================================================

# The literal `uv sync` on the first line is deliberate: it is the only step
# that must work before a virtual environment exists, so it cannot route
# through `{{dev}}`. `framework install` then runs with --force because a fresh
# checkout carries the tracked `.vaultspec/` config but not the gitignored
# install manifest (`.vaultspec/providers.json`), and the diagnosis engine
# reads that combination as CORRUPTED; --force rebuilds the manifest from the
# tracked config the way a consumer recovering a lost manifest would.

# Provision a fresh clone or worktree: dependencies, framework, and git hooks.
bootstrap:
    uv sync --locked --group dev
    {{dev}} framework install

# ===========================================================================
#  Toolchain verbs
# ===========================================================================

# Manage project dependencies and the lockfile.
deps target='sync':
    {{dev}} deps {{target}}

# Run gating static analysis: style, types, config, links, and markdown.
lint target='all':
    {{dev}} lint {{target}}

# Apply every available formatter and automatic fix.
fix target='all':
    {{dev}} fix {{target}}

# Audit dependencies and code quality; only 'deps' gates.
audit target='all':
    {{dev}} audit {{target}}

# Run the project test suites.
test target='all':
    {{dev}} test {{target}}

# Build the Python distribution artifacts.
build target='python':
    {{dev}} build {{target}}

# ===========================================================================
#  This checkout's own vaultspec records and harness
# ===========================================================================

# Operate on this repository's own .vault/ development corpus.
vault target='check':
    {{dev}} vault {{target}}

# Operate on this repository's own .vaultspec/ framework harness.
framework target='doctor':
    {{dev}} framework {{target}}

# ===========================================================================
#  Assets and analytics
# ===========================================================================

# Regenerate the committed README terminal renders and demo GIF.
assets target='all':
    {{dev}} assets {{target}}

# MEASUREMENT ONLY - always exits 0. Composes the gates rather than
# re-implementing any threshold, so the report and the gate cannot disagree.
# `just health census` regenerates the distributions each baseline ratchet in
# pyproject.toml is calibrated from; run it before lowering a threshold.

# Rank the worst offenders across every code-health dimension.
health target='report':
    {{dev}} health {{target}}

# Dev-only and unshipped: it reads the operator's own ~/.claude and ~/.codex
# transcripts and writes into the gitignored statistic/out/. Every
# machine-varying input is a flag with a home-derived default, so the bare
# invocation is the normal one. Pass --help for the flag list.

# Report CLI usage analytics from the local agent transcript corpora.
analytics *args='':
    uv run --no-sync python -m statistic {{args}}

# ===========================================================================
#  Release artifacts
# ===========================================================================

# Parameterised rather than a fixed `build` target, and a release-workflow
# action rather than a routine local build. The binaries resolve
# `vaultspec-core==<tag>` from PyPI on first launch, so the tag must already be
# published for the result to bootstrap. `tag` is the release tag (e.g.
# vaultspec-core-v0.1.53); `rust_target` is a cargo triple (e.g.
# x86_64-pc-windows-msvc).

# `--no-project` matches .github/workflows/binaries.yml exactly: the binary
# build runs against a bare interpreter with no project environment, so a local
# reproduction and the release workflow invoke the script identically.

# Build the standalone PyApp binaries for one release tag and Rust target.
binaries tag rust_target outdir='dist-bin':
    uv run --no-project --python 3.13 -- python scripts/build_pyapp.py --tag {{tag}} --target {{rust_target}} --outdir {{outdir}}

# ===========================================================================
#  Aggregate pipeline
# ===========================================================================

# `test broad` rather than `test unit` on purpose - see `just test help`. This
# mirrors what CI proves, so a green run here means what a green CI run means.

# Run the full local gate: lint, dependency audit, vault checks, broad tests.
ci:
    {{dev}} ci all
