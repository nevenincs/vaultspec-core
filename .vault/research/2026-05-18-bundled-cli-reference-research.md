---
tags:
  - '#research'
  - '#bundled-cli-reference'
date: '2026-05-18'
related: []
---

# `bundled-cli-reference` research: `scope a machine-facing CLI reference bundled into the package`

The source-layout-collapse ADR deferred a follow-up: split the human-facing
prose documentation from a leaner machine-facing operational map and bundle
the latter into the package so consumer projects ship with a locally-resident
command reference. This research scopes that follow-up: it inventories the
current bundled rule, the human documentation, the seeding mechanism, and the
constraints any bundled reference must respect.

## Findings

### The current bundled CLI rule

`src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md` is a 119-line
rule. It carries a one-paragraph mandate, a fourteen-row task-to-command
table, a five-bullet runtime section, an allowed-edits section, and a
references section that links the human-facing `docs/CLI.md` and
`docs/framework.md` via GitHub URLs.

The rule is a high-level cheat sheet: it answers "how do I create a
document" or "how do I sync" with a single canonical invocation. It does
not enumerate every command, every flag, every exit code, or every
environment variable.

### Rules are always-on

`src/vaultspec_core/core/rules.py` discovers every `*.md` file in the
consumer's `rules_src_dir` (`.vaultspec/rules/rules/`) and assembles each
one into provider configuration with `trigger: always_on` frontmatter. The
bundled `builtins/rules/` subdirectory seeds into that location. Any file
placed under `builtins/rules/` therefore becomes an always-on rule injected
into every provider's assembled configuration (the consumer's `CLAUDE.md`,
`AGENTS.md`, and equivalents).

This is the central constraint. A comprehensive CLI reference is five to
eight hundred lines. Placing it under `builtins/rules/` would inflate every
provider configuration in every consumer project by that volume on every
sync. The reference must live somewhere that is bundled and seeded but NOT
discovered as a rule.

### What the human documentation already provides

`docs/CLI.md` is the canonical command reference (around 774 lines). It
carries an entry-points table, a global-options table, a command-signature
contract block (the machine-checkable list of every command signature), a
per-command section for every command and subcommand with argument and
option tables, an environment-variable table, and exit-code semantics
described inline within each command section.

`docs/MCP.md` (around 182 lines) documents the MCP server: setup, the
`VAULTSPEC_TARGET_DIR` environment variable, the verification commands, and
the `find` and `create` tool parameter and response schemas.

`docs/framework.md` (around 247 lines) documents the workflow phases, the
skill catalogue, customization, and the document directory structure.

Each document mixes machine-actionable content (command names, flag names,
argument enumerations, exit codes, environment variables, tool schemas)
with human narrative (prose rationale, worked examples, philosophy). The
machine-actionable content is the subset a bundled reference would carry.

### Drift protection that already exists

`src/vaultspec_core/tests/cli/test_cli_handbook_drift.py` walks the live
Typer command tree, invokes `--help` on every leaf command, and asserts
every command name and every non-global option name appears in
`docs/CLI.md`. This test keeps `docs/CLI.md` synchronized with the live CLI
surface. It is the reason `docs/CLI.md` can be trusted as a correct
extraction source.

Any hand-authored bundled reference would need an equivalent drift guard,
otherwise it can silently fall out of step with the live CLI.

### How seeding handles non-rule content

`seed_builtins` (`src/vaultspec_core/builtins/__init__.py`) walks the entire
`builtins/` tree with `rglob("*")` and copies every file (skipping
`__init__.py` and `__pycache__`) into the target `.vaultspec/rules/`
directory, preserving the relative subdirectory structure. A file at
`builtins/reference/cli.md` would seed to `.vaultspec/rules/reference/cli.md`.

The sync pipeline (`sync_provider`) dispatches over the known resource
subdirectories: `rules`, `skills`, `agents`, `system`, `mcps`. A subtree
that is none of those (for example, a new `reference/` subtree) is copied
into the consumer workspace by `seed_builtins` but is not processed by any
provider sync pass. It is inert: present and locally readable, but not
assembled into any provider configuration.

### Placement options the ADR must choose between

- **Under `builtins/rules/`**: rejected. Becomes an always-on rule and
  bloats every provider config.
- **A new `builtins/reference/` subtree**: seeds to
  `.vaultspec/rules/reference/`, inert to the sync passes, locally readable
  by an agent working in a consumer project. The existing
  `vaultspec-cli.builtin.md` rule would point at this local path.
- **A skill `references/` subdirectory**: skills already carry a
  `references/` convention (for example
  `builtins/skills/vaultspec-documentation/references/`). The CLI reference
  is not skill-scoped, so nesting it under one skill would mis-file it.

### Content-source options the ADR must choose between

- **Hand-authored**: a curated reference written by hand. Requires a new
  drift test, analogous to `test_cli_handbook_drift.py`, to keep it correct
  against the live CLI.
- **Generated at build time from `docs/CLI.md`**: a build step that extracts
  the machine-actionable tables from `docs/CLI.md` into the bundled
  reference. Inherits `docs/CLI.md`'s drift protection but adds build
  machinery and a generated artefact in the source tree.

### Out of scope for this follow-up

`docs/MCP.md` and `docs/framework.md` also carry machine-actionable
content. This research recommends the first iteration of the bundled
reference cover the CLI surface only; the MCP and framework surfaces can
follow in a later iteration once the placement and drift-protection
pattern is proven on the CLI reference.
