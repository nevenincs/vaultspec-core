# vaultspec-core CLI reference

Complete command-line interface (CLI) reference for `vaultspec-core`. See the [framework manual](./README.md) for workflows and concepts.

## Entry points

| Command                                          | Description                                                                                            |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `vaultspec-core`                                 | Workspace management, vault operations, resource sync.                                                 |
| `vaultspec-mcp`                                  | Console script that launches the stdio Model Context Protocol (MCP) server.                            |
| `uv run python -m vaultspec_core.mcp_server.app` | Module invocation of the MCP server (avoids binary locking on Windows). See [MCP reference](./MCP.md). |

## Global options

These options apply at the top level unless noted. `--debug` and `--version` are top-level only. `--target` is accepted by target-aware workspace commands, `vaultspec-core vault ...`, `vaultspec-core spec ...`, and `vaultspec-core migrations ...`. `--json` is command-specific and appears only on commands that support JavaScript Object Notation (JSON) output.

| Option         | Short | Default | Description                                                                                                                |
| -------------- | ----- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| `--target DIR` | `-t`  | cwd     | Target workspace directory. Overrides `VAULTSPEC_TARGET_DIR`. Defaults to the current working directory if neither is set. |
| `--debug`      | `-d`  | off     | Enable DEBUG-level logging (top-level flag).                                                                               |
| `--version`    | `-V`  | -       | Print version and exit (top-level flag).                                                                                   |

## Workspace commands

### install

```bash
vaultspec-core install [PROVIDER] [OPTIONS]
```

Deploy the vaultspec framework into the target directory.

#### Arguments

| Argument   | Default | Description                                               |
| ---------- | ------- | --------------------------------------------------------- |
| `PROVIDER` | `all`   | `all`, `core`, `claude`, `gemini`, `antigravity`, `codex` |

#### Options

| Option      | Default | Description                             |
| ----------- | ------- | --------------------------------------- |
| `--upgrade` | off     | Re-sync builtins without re-scaffolding |
| `--dry-run` | off     | Preview without writing                 |
| `--force`   | off     | Overwrite existing installation         |
| `--skip`    | `[]`    | Skip specific sync passes (repeatable)  |
| `--dev`     | off     | Permit running inside the source repo   |
| `--json`    | off     | Emit machine-readable output            |

`core` installs `.vaultspec/` only, without any provider config.

______________________________________________________________________

### uninstall

```bash
vaultspec-core uninstall [PROVIDER] [OPTIONS]
```

Remove the vaultspec framework from the target directory.

#### Arguments

| Argument   | Default | Description                                               |
| ---------- | ------- | --------------------------------------------------------- |
| `PROVIDER` | `all`   | `all`, `core`, `claude`, `gemini`, `antigravity`, `codex` |

#### Options

| Option           | Default | Description                                    |
| ---------------- | ------- | ---------------------------------------------- |
| `--remove-vault` | off     | Also remove `.vault/`                          |
| `--dry-run`      | off     | Preview without deleting                       |
| `--force`        | off     | Required to execute (uninstall is destructive) |
| `--skip`         | `[]`    | Skip specific removal passes (repeatable)      |
| `--dev`          | off     | Permit running inside the source repo          |
| `--json`         | off     | Emit machine-readable output                   |

`.vault/` is preserved by default. Pass `--remove-vault` to delete it.

______________________________________________________________________

### sync

```bash
vaultspec-core sync [PROVIDER] [OPTIONS]
```

Authoritative complete sync from `.vaultspec/` to enrolled provider outputs:
rules, skills, agents, system prompts, provider config stubs, and MCP entries.
After editing or adding framework source files, this is the normal propagation
command.

#### Arguments

| Argument   | Default | Description                                       |
| ---------- | ------- | ------------------------------------------------- |
| `PROVIDER` | `all`   | `all`, `claude`, `gemini`, `antigravity`, `codex` |

`core` is not a valid sync target because sync reads from `.vaultspec/`.
Use `vaultspec-core install --upgrade` or `vaultspec-core install --force` for
framework/provider scaffolding repair, not as the normal propagation path after
source edits.

#### Options

| Option      | Default | Description                                           |
| ----------- | ------- | ----------------------------------------------------- |
| `--dry-run` | off     | Preview changes without writing                       |
| `--force`   | off     | Prune stale files and overwrite user-authored content |
| `--skip`    | `[]`    | Skip specific sync passes (repeatable)                |
| `--dev`     | off     | Permit running inside the source repo                 |
| `--json`    | off     | Emit machine-readable output                          |

## Vault commands

Group command: `vaultspec-core vault COMMAND`

### vaultspec-core vault add

```bash
vaultspec-core vault add DOC_TYPE [OPTIONS]
```

Create a new `.vault/` document from a template.

#### Arguments

| Argument   | Description                                             |
| ---------- | ------------------------------------------------------- |
| `DOC_TYPE` | `adr`, `audit`, `exec`, `plan`, `reference`, `research` |

#### Options

| Option          | Short | Default         | Description                                                                          |
| --------------- | ----- | --------------- | ------------------------------------------------------------------------------------ |
| `--feature TAG` | `-f`  | None (required) | Feature tag (kebab-case)                                                             |
| `--date DATE`   | -     | today           | Override date (ISO 8601)                                                             |
| `--title TITLE` | -     | None            | Document title                                                                       |
| `--related DOC` | `-r`  | None            | Related document(s). Accepts path, filename, stem, or `[[wiki-link]]`. Repeatable.   |
| `--tags TAG`    | -     | None            | Additional freeform tags beyond the required directory and feature tags. Repeatable. |
| `--force`       | -     | off             | Overwrite an existing document at the resolved path.                                 |
| `--dry-run`     | -     | off             | Preview without writing.                                                             |
| `--json`        | -     | off             | Emit machine-readable output.                                                        |

______________________________________________________________________

### vaultspec-core vault list

```bash
vaultspec-core vault list [DOC_TYPE] [OPTIONS]
```

List vault documents.

#### Arguments

| Argument   | Default | Description             |
| ---------- | ------- | ----------------------- |
| `DOC_TYPE` | None    | Filter by document type |

#### Options

| Option          | Short | Default | Description                   |
| --------------- | ----- | ------- | ----------------------------- |
| `--feature TAG` | `-f`  | None    | Filter by feature tag         |
| `--date DATE`   | -     | None    | Filter by date                |
| `--json`        | -     | off     | Emit machine-readable output. |

______________________________________________________________________

### vaultspec-core vault stats

```bash
vaultspec-core vault stats [OPTIONS]
```

Show vault statistics and document counts.

#### Options

| Option          | Short | Default | Description                            |
| --------------- | ----- | ------- | -------------------------------------- |
| `--feature TAG` | `-f`  | None    | Filter by feature tag                  |
| `--date DATE`   | -     | None    | Filter by date                         |
| `--type TYPE`   | -     | None    | Filter by document type                |
| `--invalid`     | -     | off     | Show only documents with invalid links |
| `--orphaned`    | -     | off     | Show only orphaned documents           |
| `--json`        | -     | off     | Emit machine-readable output.          |

______________________________________________________________________

### vaultspec-core vault graph

```bash
vaultspec-core vault graph [OPTIONS]
```

Outputs a hierarchical tree grouped by feature and type.

#### Options

| Option          | Short | Default | Description                          |
| --------------- | ----- | ------- | ------------------------------------ |
| `--feature TAG` | `-f`  | None    | Scope to a single feature            |
| `--json`        | -     | off     | Output as networkx node-link JSON    |
| `--metrics`     | `-m`  | off     | Show aggregate graph metrics         |
| `--ascii`       | -     | off     | Render ASCII topology                |
| `--body`        | -     | off     | Include document body in JSON output |

______________________________________________________________________

### vaultspec-core vault repair

```bash
vaultspec-core vault repair [OPTIONS]
```

Run the operator repair pipeline for `.vault/` content. This is the guided
recovery surface for degraded vaults. It reports preflight and migration state,
runs the health checks, applies supported mechanical fixes unless `--dry-run`
is set, refreshes generated feature indexes unless `--no-index` is set, rebuilds
graph state, and runs a postcheck pass.

`vaultspec-core vault repair` is broader than
`vaultspec-core vault check all --fix`. The check-level fixer remains available
for compatibility, but it does not own generated index refresh, post-fix graph
rebuild, root-cause grouping, or final delta reporting.

#### Options

| Option                       | Short | Default | Description                                      |
| ---------------------------- | ----- | ------- | ------------------------------------------------ |
| `--dry-run`                  | -     | off     | Preview repair actions without writing           |
| `--include-index/--no-index` | -     | on      | Refresh generated feature indexes during repair  |
| `--feature TAG`              | `-f`  | None    | Scope repair and index refresh to one feature    |
| `--verbose`                  | `-v`  | off     | Show INFO-level diagnostics and detailed paths   |
| `--json`                     | -     | off     | Emit machine-readable phase and summary payloads |

#### Phases

| Phase       | Purpose                                                               |
| ----------- | --------------------------------------------------------------------- |
| `preflight` | Report migration status and platform path behavior                    |
| `check`     | Run the current vault health suite without mutation                   |
| `fix`       | Apply supported safe check-level fixes, or report planned fixes       |
| `index`     | Refresh or preview generated `.vault/index/<feature>.index.md` files  |
| `postcheck` | Rebuild graph state and rerun checks after mutation                   |
| `summary`   | Report changed files, generated indexes, unresolved work, root causes |

Dry-run mode never writes generated indexes or check fixes. If migrations are
pending, dry-run reports that state instead of entering the vault scan path that
would apply lazy migrations on first use.

______________________________________________________________________

### vaultspec-core vault feature list

```bash
vaultspec-core vault feature list [OPTIONS]
```

List all feature tags in the vault.

#### Options

| Option        | Default | Description                               |
| ------------- | ------- | ----------------------------------------- |
| `--date DATE` | None    | Filter by date                            |
| `--orphaned`  | off     | Show only features with no incoming links |
| `--type TYPE` | None    | Filter by document type                   |
| `--json`      | off     | Emit machine-readable output.             |

______________________________________________________________________

### vaultspec-core vault feature index

```bash
vaultspec-core vault feature index [OPTIONS]
```

Generate or update `<feature>.index.md` files in `.vault/index/`. Each index links to every document sharing that feature tag, making implicit feature clusters explicit in the graph. Indexes carry the `#index` directory tag plus the feature tag and are auto-managed.

#### Options

| Option          | Short | Default | Description                           |
| --------------- | ----- | ------- | ------------------------------------- |
| `--feature TAG` | `-f`  | None    | Generate index for a specific feature |
| `--json`        | -     | off     | Emit machine-readable output.         |

______________________________________________________________________

### vaultspec-core vault feature archive

```bash
vaultspec-core vault feature archive FEATURE_TAG [OPTIONS]
```

Move all documents for a feature tag to the archive.

#### Options

| Option   | Default | Description                   |
| -------- | ------- | ----------------------------- |
| `--json` | off     | Emit machine-readable output. |

______________________________________________________________________

### vaultspec-core vault check

```bash
vaultspec-core vault check COMMAND [OPTIONS]
```

Run health checks on `.vault/`. Exits with code `1` if errors are found.

#### Shared options

| Option          | Short | Default | Description                      |
| --------------- | ----- | ------- | -------------------------------- |
| `--fix`         | -     | off     | Apply auto-fixes where supported |
| `--feature TAG` | `-f`  | None    | Limit to a specific feature      |
| `--verbose`     | `-v`  | off     | Show INFO-level diagnostics      |

#### Subcommands

| Subcommand    | `--fix` | `--feature` | Description                                                      |
| ------------- | ------- | ----------- | ---------------------------------------------------------------- |
| `all`         | partial | yes         | Run every check in sequence                                      |
| `body-links`  | no      | yes         | Find wiki-links and markdown path links in document body text    |
| `dangling`    | yes     | yes         | Find `related:` wiki-links that resolve to no document           |
| `frontmatter` | yes     | yes         | Validate frontmatter against vault schema                        |
| `links`       | yes     | yes         | Check wiki-links follow Obsidian convention (no `.md` extension) |
| `orphans`     | no      | yes         | Find documents with no incoming wiki-links                       |
| `features`    | no      | yes         | Check feature tag completeness (missing doc types)               |
| `references`  | yes     | yes         | Check cross-references within features                           |
| `schema`      | yes     | yes         | Enforce dependency rules (ADR refs research, plan refs ADR)      |
| `structure`   | yes     | no          | Check directory structure and filename conventions               |

`yes` = fully supported, `partial` = only the sub-checks that accept `--fix` apply fixes (`all` dispatches to every check), `no` = flag rejected with error. `structure` does not support `--feature` filtering.

Use `vaultspec-core vault repair` when the operator goal is end-to-end recovery
with generated index refresh, post-fix validation, and a final delta report.

### vaultspec-core vault plan

```bash
vaultspec-core vault plan COMMAND [OPTIONS] PATH ...
```

Inspect and manipulate plan documents per the plan-hardening convention. Plans declare a complexity tier (`L1`, `L2`, `L3`, `L4`) in frontmatter and are structured as `Epic > Wave > Phase > Step`. Every mutating operation goes through this surface. Canonical identifiers (`S##`, `P##`, `W##`) remain append-only and gap-no-reuse. `vaultspec-core vault plan check` flags hand-edits to checkbox glyphs or display paths.

#### Read commands

| Subcommand | Description                                                                              |
| ---------- | ---------------------------------------------------------------------------------------- |
| `status`   | Report plan health, structure, and completion. `--json` emits a machine-readable payload |
| `check`    | Validate convention compliance; with `--fix`, apply autofixable transformations          |
| `query`    | Filter Step rows by `--phase`/`--wave` scope and `--open`/`--closed` predicate           |

`vaultspec-core vault plan check` exits `1` when at least one ERROR-severity finding is present.

#### Step commands

| Subcommand | Description                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `add`      | Append a Step at the next-available `S##`. Requires `--action` and `--scope`      |
| `insert`   | Insert at a named position with `--before`/`--after`; parent inferred from anchor |
| `edit`     | Replace `--action`, `--scope`, or both without changing the canonical identifier  |
| `move`     | Re-parent (`--to-phase`), re-position (`--before`/`--after`), or both             |
| `remove`   | Retire the Step's canonical id permanently; the next-available counter skips it   |
| `check`    | Mark the Step closed (`[x]`); idempotent                                          |
| `uncheck`  | Mark the Step open (`[ ]`); idempotent                                            |
| `toggle`   | Flip the Step's checkbox state                                                    |

#### Phase commands

| Subcommand | Description                                                                   |
| ---------- | ----------------------------------------------------------------------------- |
| `add`      | Append a Phase at the next-available `P##`. Requires `--title` and `--intent` |
| `insert`   | Insert at a named position with `--before`/`--after`                          |
| `edit`     | Replace `--title`, `--intent`, or both in place                               |
| `move`     | Re-parent (`--to-wave`), re-position (`--before`/`--after`), or both          |
| `renumber` | Remediate a duplicated id via `--to <P##>`; refuses live / retired collisions |
| `remove`   | Retire the Phase plus every descendant Step (cascading retirement)            |

`phase renumber` is the audited remediation surface for collisions inherited from legacy plans. One example is a writer who treated `P##` as Wave-scoped rather than per-document. The verb retires the old id so it cannot be reused, then recomputes every descendant Step's display path against the new parent canonical id.

#### Wave commands

Identical shape to Phase, but the parent is implicit (Epic frame). Only `--before`/`--after` re-position. No `--to-epic` flag exists. Wave operations require `L3` or `L4`.

#### Epic intent (L4 only)

| Subcommand    | Description                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `intent show` | Print the Epic intent paragraph                                                                  |
| `intent edit` | Replace the Epic intent paragraph; `--text` must declare the project-management (PM) association |

#### Tier commands

| Subcommand | Description                                                                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show`     | Print the plan's declared tier                                                                                                                                                               |
| `promote`  | Advance the tier transitively, for example L1 -> L4 in one call. Synthesised containers use `--phase-title`/`--phase-intent`/`--wave-title`/`--wave-intent`/`--epic-intent` for placeholders |
| `demote`   | Step the tier down. Refuses with an error when the collapsing layer holds more than one container; pass `--force` to retire the dropped ids and proceed                                      |

#### Move-flag precedence

`step move` and `phase move` accept the re-parent flag (`--to-phase` / `--to-wave`) and the position flags (`--before` / `--after`) independently or together:

- Re-parent flag alone re-parents and appends to the destination tail.
- Position flag alone re-positions within the current parent; the anchor must share that parent.
- Both flags re-parent and position the item; the anchor must reside in the destination post-move.

A self-referential move (`step move S01 --before S01`) is rejected with the relevant `Move{Step,Phase,Wave}Error`.

#### Identifier retirement

`remove`, multi-step demotion, and Wave / Phase removal all add the retired canonical id to a hidden `<!-- RETIRED: ... -->` ledger embedded in the plan body. `next_available_*` consults this ledger so retired identifiers are never reused, even across `parse / serialise` round-trips invoked by `--fix`.

## Spec commands

Group command: `vaultspec-core spec COMMAND`

Spec subcommands that operate on a workspace accept `--target / -t DIR`. `--json` is command-specific and appears only on commands that support machine-readable output.

### vaultspec-core spec doctor

```bash
vaultspec-core spec doctor [OPTIONS]
```

Run diagnostic collectors across the framework, providers, builtins, `.gitignore`, and configuration files. Reports findings and exits with the highest severity observed.

#### Options

| Option         | Short | Default | Description                                      |
| -------------- | ----- | ------- | ------------------------------------------------ |
| `--target DIR` | `-t`  | cwd     | Diagnose a directory other than the current one. |
| `--json`       | -     | off     | Emit the diagnosis as JSON.                      |

Exit codes: `0` = all ok, `1` = warnings, `2` = errors.

______________________________________________________________________

### vaultspec-core spec rules / vaultspec-core spec skills / vaultspec-core spec agents

Create, read, update, and delete (CRUD) operations for framework resources. All three groups share the same subcommand structure.

```bash
vaultspec-core spec rules COMMAND
vaultspec-core spec skills COMMAND
vaultspec-core spec agents COMMAND
```

#### Subcommands

| Subcommand | Signature                           | Description                                                                               |
| ---------- | ----------------------------------- | ----------------------------------------------------------------------------------------- |
| `list`     | -                                   | List all resources                                                                        |
| `add`      | `--name NAME [--force] [--dry-run]` | Create a resource. Extra options vary per resource type (below).                          |
| `show`     | `NAME`                              | Print resource content to stdout                                                          |
| `edit`     | `NAME`                              | Open in configured editor (`VAULTSPEC_EDITOR`)                                            |
| `remove`   | `NAME [--yes\|--force]` (`-y`)      | Delete a resource. Prompts unless confirmed.                                              |
| `rename`   | `OLD_NAME NEW_NAME`                 | Rename a resource                                                                         |
| `sync`     | `[--dry-run] [--force]`             | Resource-scoped sync; use top-level `vaultspec-core sync` for a complete provider refresh |
| `revert`   | `FILENAME`                          | Revert to snapshotted original                                                            |

`add` accepts different body-content flags per resource type:

- `vaultspec-core spec rules add` accepts `--content TEXT`.
- `vaultspec-core spec skills add` accepts `--description TEXT` and `--template TEXT`.
- `vaultspec-core spec agents add` accepts `--description TEXT`.

`vaultspec-core spec <resource> sync` commands are narrow maintenance
surfaces. They do not guarantee that provider-facing config stubs such as
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.codex/config.toml` have been fully
refreshed. Run `vaultspec-core sync` after source-side changes when the goal is
a complete provider-facing workspace.

______________________________________________________________________

### vaultspec-core spec system

```bash
vaultspec-core spec system COMMAND
```

#### Subcommands

| Subcommand | Options                 | Description                                        |
| ---------- | ----------------------- | -------------------------------------------------- |
| `show`     | -                       | Display system prompt parts and generation targets |
| `sync`     | `[--dry-run] [--force]` | Resource-scoped system prompt sync                 |

______________________________________________________________________

### vaultspec-core spec hooks

```bash
vaultspec-core spec hooks COMMAND
```

#### Subcommands

| Subcommand | Signature             | Description                                                                                                           |
| ---------- | --------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `list`     | -                     | List hooks with name, status, event, and action count                                                                 |
| `run`      | `EVENT [--path PATH]` | Trigger enabled hooks for the given event. Valid events: `vault.document.created`, `config.synced`, `audit.completed` |

______________________________________________________________________

### vaultspec-core spec mcps

```bash
vaultspec-core spec mcps COMMAND
```

Manage MCP server definitions and the synced `.mcp.json` entries deployed for provider clients.
MCP sync updates `.mcp.json`; use top-level `vaultspec-core sync` for a
complete refresh across all provider-facing outputs.

#### Subcommands

| Subcommand | Signature                               | Description                                                    |
| ---------- | --------------------------------------- | -------------------------------------------------------------- |
| `list`     | -                                       | List all registered MCP server definitions                     |
| `add`      | `--name NAME [--config JSON] [--force]` | Add a new custom MCP server definition                         |
| `remove`   | `NAME [--force]`                        | Remove an MCP server definition (`--force` skips confirmation) |
| `sync`     | `[--dry-run] [--force]`                 | Sync MCP definitions to `.mcp.json`                            |

## Migration commands

Group command: `vaultspec-core migrations COMMAND`

Every migration subcommand also accepts the global `--target / -t DIR` and `--json` flags.

The migration registry runs every entry whose target version exceeds the workspace manifest's `vaultspec_version`, then bumps the manifest version on success. Migrations are idempotent and run lazily on every `vaultspec-core vault ...` command, on `vaultspec-core install --upgrade`, or explicitly through `vaultspec-core migrations run`.

### vaultspec-core migrations status

```bash
vaultspec-core migrations status [OPTIONS]
```

List registered migrations and which entries are pending against the current workspace manifest. Read-only; never mutates.

#### Options

| Option         | Short | Default | Description                                             |
| -------------- | ----- | ------- | ------------------------------------------------------- |
| `--target DIR` | `-t`  | cwd     | Inspect a workspace other than the current directory.   |
| `--json`       | -     | off     | Emit status, registered list, and pending list as JSON. |

Exit codes: `0` when up to date or workspace has no manifest, `1` when migrations are pending.

______________________________________________________________________

### vaultspec-core migrations run

```bash
vaultspec-core migrations run [OPTIONS]
```

Apply every pending migration in version order and bump the manifest's `vaultspec_version`. A migration that fails stops the run and leaves the manifest unchanged so the next invocation re-attempts it.

#### Options

| Option         | Short | Default | Description                                           |
| -------------- | ----- | ------- | ----------------------------------------------------- |
| `--target DIR` | `-t`  | cwd     | Migrate a workspace other than the current directory. |
| `--json`       | -     | off     | Emit per-entry summaries and counts as JSON.          |

Exit codes: `0` on success (including the no-pending no-op), `1` if any migration failed.

______________________________________________________________________

## Environment variables

All variables are prefixed `VAULTSPEC_`. Environment variables override defaults but are overridden by the `--target` flag.

| Variable                          | Type | Default      | Description                                                                                                                                                                                                       |
| --------------------------------- | ---- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VAULTSPEC_TARGET_DIR`            | path | cwd          | Root workspace directory (where `.vault/` and `.vaultspec/` live). Equivalent to `--target` on the CLI. Also used by `vaultspec-mcp` to locate the workspace. Defaults to the current working directory if unset. |
| `VAULTSPEC_DOCS_DIR`              | str  | `.vault`     | Vault directory name                                                                                                                                                                                              |
| `VAULTSPEC_FRAMEWORK_DIR`         | str  | `.vaultspec` | Framework directory name                                                                                                                                                                                          |
| `VAULTSPEC_CLAUDE_DIR`            | str  | `.claude`    | Claude tool directory name                                                                                                                                                                                        |
| `VAULTSPEC_GEMINI_DIR`            | str  | `.gemini`    | Gemini tool directory name                                                                                                                                                                                        |
| `VAULTSPEC_ANTIGRAVITY_DIR`       | str  | `.agents`    | Antigravity directory name                                                                                                                                                                                        |
| `VAULTSPEC_IO_BUFFER_SIZE`        | int  | `8192`       | I/O read buffer size in bytes                                                                                                                                                                                     |
| `VAULTSPEC_TERMINAL_OUTPUT_LIMIT` | int  | `1000000`    | Subprocess stdout capture limit in bytes                                                                                                                                                                          |
| `VAULTSPEC_LOG_LEVEL`             | str  | `INFO`       | Root log level for the CLI, for example `DEBUG`, `INFO`, or `WARNING`. Overridden by `--debug` when set.                                                                                                          |
| `VAULTSPEC_ALLOW_DEV_WRITES`      | bool | unset        | Bypass the development-write guard that blocks source-repo writes. Accepts `1`/`true`/`yes`. Use with care - intended for fixture and test automation only.                                                       |
| `VAULTSPEC_EDITOR`                | str  | `zed -w`     | Editor command for `vaultspec-core spec {rules\|skills\|agents} edit`. Set to your preferred editor, for example `code -w` or `vim`.                                                                              |

## See also

| Document                        | What it covers                                  |
| ------------------------------- | ----------------------------------------------- |
| [Framework manual](./README.md) | Development workflow, skills, and customization |
| [MCP reference](./MCP.md)       | MCP server tools, setup, and configuration      |

For bug reports and feature requests, open an issue on the [vaultspec-core issue tracker](https://github.com/wgergely/vaultspec-core/issues).
