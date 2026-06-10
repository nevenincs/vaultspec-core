---
name: vaultspec-cli
---

# Vaultspec Core CLI

This project is vaultspec-managed. See `vaultspec.builtin.md` for framework rules and
the
[framework manual](https://github.com/wgergely/vaultspec-core/blob/main/docs/framework.md)
for workflow concepts.

## Mandate

Use `vaultspec-core` to create, read, audit, and repair `.vault/` documents. Never
hand-write frontmatter, filenames, plan structure, or new `.vault/` documents; editing
the body prose of a document scaffolded by `vaultspec-core vault add` is permitted (see
"Allowed manual edits" below). `vaultspec-core` enforces templates, tag taxonomy,
wiki-link resolution, schema dependencies, and provider sync; bypassing it produces
drift that `vaultspec-core vault check` and `vaultspec-core spec doctor` will flag.

## Commands

| Task                                                  | Run                                                                       |
| ----------------------------------------------------- | ------------------------------------------------------------------------- |
| Create a `.vault/` document                           | `vaultspec-core vault add <type> --feature <tag>`                         |
| List or filter vault documents                        | `vaultspec-core vault list [DOC_TYPE] [--feature <tag>]`                  |
| Show statistics, invalid, or orphan documents         | `vaultspec-core vault stats [--invalid] [--orphaned]`                     |
| Visualize the vault dependency graph                  | `vaultspec-core vault graph [--feature <tag>]`                            |
| Audit drift, broken links, or missing references      | `vaultspec-core vault check all [--fix]`                                  |
| Strip generated template annotations                  | `vaultspec-core vault sanitize annotations [--feature <tag>] [--dry-run]` |
| Confirm required documents exist for a feature        | `vaultspec-core vault check features --feature <tag>`                     |
| Archive a completed feature                           | `vaultspec-core vault feature archive <tag>`                              |
| List registered rules, skills, agents, hooks, or MCPs | `vaultspec-core spec <resource> list`                                     |
| Verify MCP config health                              | `vaultspec-core spec mcps status --json`                                  |
| Inspect the assembled system prompt                   | `vaultspec-core spec system show`                                         |
| Propagate edits under `.vaultspec/rules/...`          | `vaultspec-core sync`                                                     |
| Diagnose overall workspace health                     | `vaultspec-core spec doctor`                                              |
| Inspect or run pending schema migrations              | `vaultspec-core migrations status` / `vaultspec-core migrations run`      |

`<resource>` is one of `rules`, `skills`, `agents`, `hooks`, or `mcps` for `list`; one
of `rules`, `skills`, `agents`, `mcps`, or `system` for resource-scoped maintenance
sync. Use top-level `vaultspec-core sync` as the authoritative complete propagation
command after source-side changes.

## Runtime

- Run `vaultspec-core <cmd>` when the binary is on `PATH`. In uv-managed environments,
  run `uv run --no-sync vaultspec-core <cmd>`.
- Use `--target DIR` (or `-t`) to operate on a directory other than the current one.
- Use `--dry-run` to preview changes.
- Use `--json` for machine-readable output.
- Read sync-shaped results (`vaultspec-core install`, `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, `vaultspec-core migrations run`) with one
  vocabulary: `created`, `updated`, `unchanged`, `removed`, `restored`, `skipped`,
  `failed`. `unchanged` is a successful no-op, not a failure; `skipped` always carries a
  reason worth reading; only `failed` stops the pipeline. With `--json`, the top-level
  `status` is the run's aggregate outcome (`mixed` when items disagree).
- Use `--force` when a mutating command must overwrite existing output.
- Run `vaultspec-core <cmd> --help` for the full flag, subcommand, and exit-code
  reference.

## Allowed manual edits

Permitted:

- Edit body prose of a `.vault/` document scaffolded by `vaultspec-core vault add`.
- Edit source files under `.vaultspec/rules/rules/`, `.vaultspec/rules/skills/`,
  `.vaultspec/rules/agents/`, `.vaultspec/rules/hooks/`, or `.vaultspec/rules/mcps/`,
  then run `vaultspec-core sync`.

Forbidden:

- Hand-writing frontmatter, filenames, or new `.vault/` documents.
- Editing files inside generated provider directories; `vaultspec-core sync` regenerates
  them.

## Maintaining the bundled CLI reference

The machine-facing reference at `reference/cli.md` is part hand-written prose and part
generator-owned. The derivable zones (today, the command-inventory signature block) sit
between `vaultspec:generated:begin` / `vaultspec:generated:end` HTML-comment markers and
are owned by the generator: never hand-edit between the markers, because the next
generate overwrites those edits. The prose outside the markers (the entry-point table,
global-options narrative, per-command option tables, and the rest) stays hand-authored.

Run `vaultspec-core spec reference generate` to rewrite the managed regions from the
live Typer command surface; this is the canonical way to update the bundled reference
after a command, flag, or argument changes. The `--check` variant renders in memory,
diffs against the committed file, and exits non-zero on mismatch without writing - it is
wired into pre-commit and gates CI, so a drifted reference fails the build until the
generator is re-run.

## References

- `.vaultspec/rules/reference/cli.md` - locally-resident machine-facing CLI reference:
  command inventory, options, argument enumerations, exit codes, and environment
  variables. Read this first; no network round-trip needed.
- [CLI reference](https://github.com/wgergely/vaultspec-core/blob/main/docs/CLI.md) -
  human-facing prose reference: every command, subcommand, option, and exit code.
- [Framework manual](https://github.com/wgergely/vaultspec-core/blob/main/docs/framework.md)
  \- framework concepts, workflow, and skill catalog.
