---
name: vaultspec-cli
---

# Vaultspec Core CLI

This project is vaultspec-managed. See `vaultspec.builtin.md` for framework rules and
workflow concepts.

## Mandate

Use `vaultspec-core` to create, read, audit, and repair `.vault/` documents. Never
hand-write frontmatter, filenames, plan structure, or new `.vault/` documents; editing
the body prose of a document scaffolded by `vaultspec-core vault add` is permitted (see
"Allowed manual edits" below). `vaultspec-core` enforces templates, tag taxonomy,
wiki-link resolution, schema dependencies, and provider sync; bypassing it produces
drift that `vaultspec-core vault check` and `vaultspec-core spec doctor` will flag.

## Orientation

Before starting work in a vaultspec-managed project you have no session context for, run
`vaultspec-core status` and read the in-flight plans it names. Each in-flight plan shows
a one-line overview: tier, completed waves and phases, step completion, and the next
open step. The targeted form `vaultspec-core status <plan-or-feature>` traces a plan to
its steps, execution records, and grounding documents. Orientation is descriptive and
read-only: it is the zeroth move, not a pipeline phase, and produces no artifact.

## Commands

### Orient

- `vaultspec-core status [TARGET]` - orient in an unknown or resumed project
- `vaultspec-core vault feature list` - list feature tags in the vault
- `vaultspec-core vault list [DOC_TYPE] [--feature <tag>]` - list or filter vault
  documents

### Author the pipeline

- `vaultspec-core vault add <type> --feature <tag>` - create a `.vault/` document

### Verify & audit

- `vaultspec-core vault check all [--fix]` - audit drift, broken links, or missing
  references
- `vaultspec-core vault check features --feature <tag>` - confirm required documents
  exist for a feature
- `vaultspec-core vault sanitize annotations [--feature <tag>] [--dry-run]` - strip
  generated template annotations

### Advanced vault inspection

- `vaultspec-core vault stats [--invalid] [--orphaned]` - show statistics, invalid, or
  orphan documents
- `vaultspec-core vault graph [--feature <tag>]` - visualize the vault dependency graph

### Workspace & maintenance

- `vaultspec-core spec <resource> list` - list registered rules, skills, agents, hooks,
  or MCPs
- `vaultspec-core spec mcps status --json` - verify MCP config health
- `vaultspec-core spec system show` - inspect the assembled system prompt
- `vaultspec-core sync` - propagate edits under `.vaultspec/...`
- `vaultspec-core spec doctor` - diagnose overall workspace health
- `vaultspec-core migrations status` / `vaultspec-core migrations run` - inspect or run
  pending schema migrations
- `vaultspec-core vault feature archive <tag>` - archive a feature so it no longer
  exists in the active project
- `vaultspec-core vault feature rename <old> <new>` - rename a feature tag across every
  binding surface (document filenames, the exec folder, the `#feature` tag, `related:`
  wiki-links, and the regenerated feature index); rolls back on failure during apply,
  and `--force` merges the source into an existing target feature
- `vaultspec-core vault rule promote --from <audit-stem> --as <rule-name>` - promote an
  audit finding to a project rule

`<resource>` is one of `rules`, `skills`, `agents`, `hooks`, or `mcps` for `list`; one
of `rules`, `skills`, `agents`, `hooks`, `mcps`, or `system` for resource-scoped
maintenance sync. Use top-level `vaultspec-core sync` as the authoritative complete
propagation command after source-side changes.

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
- Edit source files under `.vaultspec/rules/`, `.vaultspec/skills/`,
  `.vaultspec/agents/`, `.vaultspec/hooks/`, or `.vaultspec/mcps/`, then run
  `vaultspec-core sync`.

Forbidden:

- Hand-writing frontmatter, filenames, or new `.vault/` documents.
- Editing files inside generated provider directories; `vaultspec-core sync` regenerates
  them.

## References

- `.vaultspec/reference/cli.md` - locally-resident machine-facing CLI reference: command
  inventory, options, argument enumerations, exit codes, and environment variables. Read
  this first; no network round-trip needed.
