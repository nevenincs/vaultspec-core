# vaultspec-core CLI reference (bundled)

Machine-facing command reference for `vaultspec-core`, bundled into every consumer
project on install and seeded to `.vaultspec/rules/reference/cli.md`. This is a
locally-resident lookup for AI agents: command inventory, options, argument
enumerations, exit codes, and environment variables. The human-facing prose reference is
`docs/CLI.md` in the source repository.

This file is a reference document, not a rule. It is not assembled into any provider
configuration.

## Entry points

| Command                                          | Purpose                                             |
| ------------------------------------------------ | --------------------------------------------------- |
| `vaultspec-core`                                 | Workspace management, vault operations, sync.       |
| `vaultspec-mcp`                                  | Console script launching the stdio MCP server.      |
| `uv run python -m vaultspec_core.mcp_server.app` | Module invocation of the MCP server (Windows-safe). |

## Global options

| Option         | Short | Default | Description                                        |
| -------------- | ----- | ------- | -------------------------------------------------- |
| `--target DIR` | `-t`  | cwd     | Target workspace directory. Overrides the env var. |
| `--debug`      | `-d`  | off     | Enable DEBUG-level logging (top-level only).       |
| `--version`    | `-V`  | -       | Print version and exit (top-level only).           |
| `--help`       | -     | -       | Show help for any command or group.                |

`--target` is accepted by workspace commands and by every `vaultspec-core vault`,
`vaultspec-core spec`, and `vaultspec-core migrations` subcommand. `--json` is
command-specific.

## Command inventory

Every leaf-command signature, matching the live Typer usage lines.

```text
vaultspec-core install [OPTIONS] [PROVIDER]
vaultspec-core uninstall [OPTIONS] [PROVIDER]
vaultspec-core sync [OPTIONS] [PROVIDER]
vaultspec-core vault add [OPTIONS] DOC_TYPE
vaultspec-core vault stats [OPTIONS]
vaultspec-core vault list [OPTIONS] [DOC_TYPE]
vaultspec-core vault repair [OPTIONS]
vaultspec-core vault feature list [OPTIONS]
vaultspec-core vault feature index [OPTIONS]
vaultspec-core vault feature archive [OPTIONS] FEATURE_TAG
vaultspec-core vault check all [OPTIONS]
vaultspec-core vault check body-links [OPTIONS]
vaultspec-core vault check annotations [OPTIONS]
vaultspec-core vault check dangling [OPTIONS]
vaultspec-core vault check orphans [OPTIONS]
vaultspec-core vault check frontmatter [OPTIONS]
vaultspec-core vault check links [OPTIONS]
vaultspec-core vault check features [OPTIONS]
vaultspec-core vault check references [OPTIONS]
vaultspec-core vault check schema [OPTIONS]
vaultspec-core vault check structure [OPTIONS]
vaultspec-core vault sanitize annotations [OPTIONS]
vaultspec-core vault plan status [OPTIONS] PATH
vaultspec-core vault plan check [OPTIONS] PATH
vaultspec-core vault plan query [OPTIONS] PATH
vaultspec-core vault plan step toggle [OPTIONS] PATH STEP_ID
vaultspec-core vault plan step check [OPTIONS] PATH STEP_ID
vaultspec-core vault plan step uncheck [OPTIONS] PATH STEP_ID
vaultspec-core vault plan step add [OPTIONS] PATH
vaultspec-core vault plan step insert [OPTIONS] PATH
vaultspec-core vault plan step edit [OPTIONS] PATH STEP_ID
vaultspec-core vault plan step move [OPTIONS] PATH STEP_ID
vaultspec-core vault plan step remove [OPTIONS] PATH STEP_ID
vaultspec-core vault plan phase add [OPTIONS] PATH
vaultspec-core vault plan phase insert [OPTIONS] PATH
vaultspec-core vault plan phase edit [OPTIONS] PATH PHASE_ID
vaultspec-core vault plan phase move [OPTIONS] PATH PHASE_ID
vaultspec-core vault plan phase renumber [OPTIONS] PATH PHASE_ID
vaultspec-core vault plan phase remove [OPTIONS] PATH PHASE_ID
vaultspec-core vault plan wave add [OPTIONS] PATH
vaultspec-core vault plan wave insert [OPTIONS] PATH
vaultspec-core vault plan wave edit [OPTIONS] PATH WAVE_ID
vaultspec-core vault plan wave move [OPTIONS] PATH WAVE_ID
vaultspec-core vault plan wave remove [OPTIONS] PATH WAVE_ID
vaultspec-core vault plan epic intent show [OPTIONS] PATH
vaultspec-core vault plan epic intent edit [OPTIONS] PATH
vaultspec-core vault plan tier show [OPTIONS] PATH
vaultspec-core vault plan tier promote [OPTIONS] PATH
vaultspec-core vault plan tier demote [OPTIONS] PATH
vaultspec-core spec doctor [OPTIONS]
vaultspec-core spec rules list [OPTIONS]
vaultspec-core spec rules add [OPTIONS]
vaultspec-core spec rules show [OPTIONS] NAME
vaultspec-core spec rules edit [OPTIONS] NAME
vaultspec-core spec rules remove [OPTIONS] NAME
vaultspec-core spec rules rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec rules sync [OPTIONS]
vaultspec-core spec rules revert [OPTIONS] FILENAME
vaultspec-core spec skills list [OPTIONS]
vaultspec-core spec skills add [OPTIONS]
vaultspec-core spec skills show [OPTIONS] NAME
vaultspec-core spec skills edit [OPTIONS] NAME
vaultspec-core spec skills remove [OPTIONS] NAME
vaultspec-core spec skills rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec skills sync [OPTIONS]
vaultspec-core spec skills revert [OPTIONS] FILENAME
vaultspec-core spec agents list [OPTIONS]
vaultspec-core spec agents add [OPTIONS]
vaultspec-core spec agents show [OPTIONS] NAME
vaultspec-core spec agents edit [OPTIONS] NAME
vaultspec-core spec agents remove [OPTIONS] NAME
vaultspec-core spec agents rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec agents sync [OPTIONS]
vaultspec-core spec agents revert [OPTIONS] FILENAME
vaultspec-core spec system show [OPTIONS]
vaultspec-core spec system sync [OPTIONS]
vaultspec-core spec hooks list [OPTIONS]
vaultspec-core spec hooks run [OPTIONS] EVENT
vaultspec-core spec mcps list [OPTIONS]
vaultspec-core spec mcps status [OPTIONS]
vaultspec-core spec mcps add [OPTIONS]
vaultspec-core spec mcps remove [OPTIONS] NAME
vaultspec-core spec mcps sync [OPTIONS]
vaultspec-core migrations status [OPTIONS]
vaultspec-core migrations run [OPTIONS]
```

## Workspace commands

### vaultspec-core install

Deploy the framework into the target directory.

`PROVIDER` (default `all`): `all`, `core`, `claude`, `gemini`, `antigravity`, `codex`.
`core` installs `.vaultspec/` only.

| Option      | Default | Description                              |
| ----------- | ------- | ---------------------------------------- |
| `--upgrade` | off     | Re-sync builtins without re-scaffolding. |
| `--dry-run` | off     | Preview without writing.                 |
| `--force`   | off     | Overwrite an existing installation.      |
| `--skip`    | `[]`    | Skip a component (repeatable).           |
| `--json`    | off     | Emit machine-readable output.            |

### vaultspec-core uninstall

Remove the framework from the target directory.

`PROVIDER` (default `all`): `all`, `core`, `claude`, `gemini`, `antigravity`, `codex`.

| Option           | Default | Description                        |
| ---------------- | ------- | ---------------------------------- |
| `--remove-vault` | off     | Also remove `.vault/`.             |
| `--dry-run`      | off     | Preview without deleting.          |
| `--force`        | off     | Required to execute (destructive). |
| `--skip`         | `[]`    | Skip a component (repeatable).     |
| `--json`         | off     | Emit machine-readable output.      |

### vaultspec-core sync

Authoritative complete sync from `.vaultspec/` to enrolled provider outputs.

`PROVIDER` (default `all`): `all`, `claude`, `gemini`, `antigravity`, `codex`. `core` is
not a valid sync target.

| Option      | Default | Description                                         |
| ----------- | ------- | --------------------------------------------------- |
| `--dry-run` | off     | Preview changes without writing.                    |
| `--force`   | off     | Prune stale files; overwrite user-authored content. |
| `--skip`    | `[]`    | Skip a component (repeatable).                      |
| `--json`    | off     | Emit machine-readable output.                       |

## Vault commands

### vaultspec-core vault add

Create a `.vault/` document from a template.

`DOC_TYPE`: `adr`, `audit`, `exec`, `plan`, `reference`, `research`.

| Option          | Short | Default  | Description                           |
| --------------- | ----- | -------- | ------------------------------------- |
| `--feature TAG` | `-f`  | required | Feature tag (kebab-case).             |
| `--date DATE`   | -     | today    | Override date (ISO 8601).             |
| `--title TITLE` | -     | None     | Document title.                       |
| `--related DOC` | `-r`  | None     | Related document(s). Repeatable.      |
| `--tags TAG`    | -     | None     | Additional freeform tags. Repeatable. |
| `--force`       | -     | off      | Overwrite an existing document.       |
| `--dry-run`     | -     | off      | Preview without writing.              |
| `--json`        | -     | off      | Emit machine-readable output.         |

### vaultspec-core vault list

List vault documents. `DOC_TYPE` filters by type.

| Option          | Short | Default | Description                   |
| --------------- | ----- | ------- | ----------------------------- |
| `--feature TAG` | `-f`  | None    | Filter by feature tag.        |
| `--date DATE`   | -     | None    | Filter by date.               |
| `--json`        | -     | off     | Emit machine-readable output. |

### vaultspec-core vault stats

Show vault statistics and document counts.

| Option          | Short | Default | Description                             |
| --------------- | ----- | ------- | --------------------------------------- |
| `--feature TAG` | `-f`  | None    | Filter by feature tag.                  |
| `--date DATE`   | -     | None    | Filter by date.                         |
| `--type TYPE`   | -     | None    | Filter by document type.                |
| `--invalid`     | -     | off     | Show only documents with invalid links. |
| `--orphaned`    | -     | off     | Show only orphaned documents.           |
| `--json`        | -     | off     | Emit machine-readable output.           |

### vaultspec-core vault graph

Signature: `vaultspec-core vault graph [OPTIONS] COMMAND [ARGS]...`. Hierarchical
dependency tree grouped by feature and type.

| Option          | Short | Default | Description                           |
| --------------- | ----- | ------- | ------------------------------------- |
| `--feature TAG` | `-f`  | None    | Scope to a single feature.            |
| `--json`        | -     | off     | Output as networkx node-link JSON.    |
| `--metrics`     | `-m`  | off     | Show aggregate graph metrics.         |
| `--ascii`       | -     | off     | Render ASCII topology.                |
| `--body`        | -     | off     | Include document body in JSON output. |

### vaultspec-core vault repair

Operator repair pipeline for `.vault/` content. Broader than
`vaultspec-core vault check all --fix`: owns generated index refresh, post-fix graph
rebuild, and final delta reporting.

| Option                       | Short | Default | Description                             |
| ---------------------------- | ----- | ------- | --------------------------------------- |
| `--dry-run`                  | -     | off     | Preview repair actions without writing. |
| `--include-index/--no-index` | -     | on      | Refresh generated feature indexes.      |
| `--feature TAG`              | `-f`  | None    | Scope repair and index refresh.         |
| `--verbose`                  | `-v`  | off     | Show INFO-level diagnostics.            |
| `--json`                     | -     | off     | Emit machine-readable payloads.         |

Phases: `preflight`, `check`, `fix`, `index`, `postcheck`, `summary`.

### vaultspec-core vault sanitize annotations

Strip generated template annotations from `.vault/` documents.

| Option          | Short | Default | Description                         |
| --------------- | ----- | ------- | ----------------------------------- |
| `--feature TAG` | `-f`  | None    | Sanitize documents for one feature. |
| `--dry-run`     | -     | off     | Preview annotation removals.        |
| `--verbose`     | `-v`  | off     | Show stripped files.                |
| `--json`        | -     | off     | Emit machine-readable payloads.     |

### vaultspec-core vault feature list

List feature tags in the vault.

| Option        | Default | Description                                |
| ------------- | ------- | ------------------------------------------ |
| `--date DATE` | None    | Filter by date.                            |
| `--orphaned`  | off     | Show only features with no incoming links. |
| `--type TYPE` | None    | Filter by document type.                   |
| `--json`      | off     | Emit machine-readable output.              |

### vaultspec-core vault feature index

Generate or update `<feature>.index.md` files in `.vault/index/`.

| Option          | Short | Default | Description                            |
| --------------- | ----- | ------- | -------------------------------------- |
| `--feature TAG` | `-f`  | None    | Generate index for a specific feature. |
| `--json`        | -     | off     | Emit machine-readable output.          |

### vaultspec-core vault feature archive

`vaultspec-core vault feature archive [OPTIONS] FEATURE_TAG` — move all documents for a
feature tag to the archive. Option: `--json`.

### vaultspec-core vault check

Signature: `vaultspec-core vault check [OPTIONS] COMMAND [ARGS]...`. Run health checks
on `.vault/`. Exits `1` if errors are found.

Shared options: `--fix` (apply auto-fixes), `--feature TAG` / `-f` (limit to a feature),
`--verbose` / `-v` (INFO diagnostics).

Subcommands: `all`, `annotations`, `body-links`, `dangling`, `frontmatter`, `links`,
`orphans`, `features`, `references`, `schema`, `structure`. The `structure` subcommand
does not support `--feature`.

### vaultspec-core vault plan

Signature: `vaultspec-core vault plan [OPTIONS] COMMAND [ARGS]...`. Inspect and
manipulate plan documents. Every mutating operation goes through this surface; canonical
identifiers (`S##`, `P##`, `W##`) are append-only and gap-no-reuse.

Read commands: `status`, `check` (accepts `--fix`), `query` (accepts `--phase`,
`--wave`, `--open`, `--closed`).

Step commands operate on `PATH STEP_ID`: `add`, `insert`, `edit`, `move`, `remove`,
`check`, `uncheck`, `toggle`. The `add` command requires `--action` and `--scope`. The
`insert` command takes `--before` / `--after`. The `edit` command takes `--action`
and/or `--scope`. The `move` command takes `--to-phase`, `--before`, `--after`.

Phase commands operate on `PATH PHASE_ID`: `add`, `insert`, `edit`, `move`, `renumber`,
`remove`. The `add` command requires `--title` and `--intent`. The `edit` command takes
`--title` and/or `--intent`. The `move` command takes `--to-wave`, `--before`,
`--after`. The `renumber` command takes `--to`.

Wave commands operate on `PATH WAVE_ID`: `add`, `insert`, `edit`, `move`, `remove`. Same
flag shape as Phase minus the re-parent flag. Wave operations require tier `L3` or `L4`.

Epic intent (`L4` only): `epic intent show`, `epic intent edit`. The `intent edit`
command takes `--text`.

Tier commands: `tier show`, `tier promote`, `tier demote`. The `promote` command takes
`--phase-title`, `--phase-intent`, `--wave-title`, `--wave-intent`, `--epic-intent` for
synthesised containers. The `demote` command takes `--force`.

## Spec commands

Signature: `vaultspec-core spec [OPTIONS] COMMAND [ARGS]...`. Framework resource
management.

### vaultspec-core spec doctor

Run diagnostic collectors across the framework, providers, builtins, `.gitignore`, vault
content, and configuration files.

| Option         | Short | Default | Description                 |
| -------------- | ----- | ------- | --------------------------- |
| `--target DIR` | `-t`  | cwd     | Diagnose another directory. |
| `--json`       | -     | off     | Emit the diagnosis as JSON. |

### vaultspec-core spec rules

The `vaultspec-core spec rules`, `vaultspec-core spec skills`, and
`vaultspec-core spec agents` groups share an identical CRUD subcommand shape:

| Subcommand | Signature                           | Description                       |
| ---------- | ----------------------------------- | --------------------------------- |
| `list`     | -                                   | List all resources.               |
| `add`      | `--name NAME [--force] [--dry-run]` | Create a resource.                |
| `show`     | `NAME`                              | Print resource content to stdout. |
| `edit`     | `NAME`                              | Open in `VAULTSPEC_EDITOR`.       |
| `remove`   | `NAME [--yes` / `-y` / `--force]`   | Delete a resource (prompts).      |
| `rename`   | `OLD_NAME NEW_NAME`                 | Rename a resource.                |
| `sync`     | `[--dry-run] [--force]`             | Resource-scoped sync.             |
| `revert`   | `FILENAME`                          | Revert to snapshotted original.   |

Body-content flags on `add` vary by resource: `vaultspec-core spec rules add` takes
`--content TEXT`; `vaultspec-core spec skills add` takes `--description TEXT` and
`--template TEXT`; `vaultspec-core spec agents add` takes `--description TEXT`.

### vaultspec-core spec system

The `vaultspec-core spec system show` command displays system prompt parts and
generation targets. The `vaultspec-core spec system sync` command
(`[--dry-run] [--force]`) runs a resource-scoped system prompt sync.

### vaultspec-core spec hooks

The `vaultspec-core spec hooks list` command lists hooks with name, status, event, and
action count. The signature `vaultspec-core spec hooks run [OPTIONS] EVENT` triggers
enabled hooks; it takes `--path PATH`. Valid events: `vault.document.created`,
`config.synced`, `audit.completed`.

### vaultspec-core spec mcps

Signature: `vaultspec-core spec mcps [OPTIONS] COMMAND [ARGS]...`. Manage MCP server
definitions and synced `.mcp.json` entries.

| Subcommand | Signature                               | Description                   |
| ---------- | --------------------------------------- | ----------------------------- |
| `list`     | -                                       | List MCP server definitions.  |
| `status`   | `[--json]`                              | Validate against `.mcp.json`. |
| `add`      | `--name NAME [--config JSON] [--force]` | Add a custom MCP definition.  |
| `remove`   | `NAME [--force]`                        | Remove an MCP definition.     |
| `sync`     | `[--dry-run] [--force]`                 | Sync definitions to config.   |

## Migration commands

Signature: `vaultspec-core migrations [OPTIONS] COMMAND [ARGS]...`. Schema migration
registry. Both subcommands accept `--target` / `-t` and `--json`.

The `vaultspec-core migrations status` command lists registered migrations and pending
entries; it is read-only.

The `vaultspec-core migrations run` command applies every pending migration in version
order and bumps the manifest version.

## Exit codes

| Command                            | Codes                                                  |
| ---------------------------------- | ------------------------------------------------------ |
| `vaultspec-core vault check`       | `0` clean, `1` errors found.                           |
| `vaultspec-core vault plan check`  | `0` clean, `1` at least one ERROR-severity finding.    |
| `vaultspec-core spec doctor`       | `0` all ok, `1` warnings, `2` errors.                  |
| `vaultspec-core spec mcps status`  | `0` config status ok, `1` otherwise.                   |
| `vaultspec-core migrations status` | `0` up to date or no manifest, `1` migrations pending. |
| `vaultspec-core migrations run`    | `0` success (including no-op), `1` a migration failed. |

## Environment variables

All prefixed `VAULTSPEC_`. Env vars override defaults but are overridden by `--target`.

| Variable                          | Type | Default      | Description                          |
| --------------------------------- | ---- | ------------ | ------------------------------------ |
| `VAULTSPEC_TARGET_DIR`            | path | cwd          | Root workspace directory.            |
| `VAULTSPEC_DOCS_DIR`              | str  | `.vault`     | Vault directory name.                |
| `VAULTSPEC_FRAMEWORK_DIR`         | str  | `.vaultspec` | Framework directory name.            |
| `VAULTSPEC_CLAUDE_DIR`            | str  | `.claude`    | Claude tool directory name.          |
| `VAULTSPEC_GEMINI_DIR`            | str  | `.gemini`    | Gemini tool directory name.          |
| `VAULTSPEC_ANTIGRAVITY_DIR`       | str  | `.agents`    | Antigravity directory name.          |
| `VAULTSPEC_IO_BUFFER_SIZE`        | int  | `8192`       | I/O read buffer size in bytes.       |
| `VAULTSPEC_TERMINAL_OUTPUT_LIMIT` | int  | `1000000`    | Subprocess stdout capture limit.     |
| `VAULTSPEC_LOG_LEVEL`             | str  | `INFO`       | Root log level for the CLI.          |
| `VAULTSPEC_EDITOR`                | str  | `zed -w`     | Editor command for resource editing. |
