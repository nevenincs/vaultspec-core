# vaultspec-core CLI reference

Complete command-line interface (CLI) reference for `vaultspec-core`. See the
[framework manual](./framework.md) for workflows and concepts.

## Entry points

| Command | Description | | ------------------------------------------------ |
\------------------------------------------------------------------------------------------------------
| | `vaultspec-core` | Workspace management, vault operations, resource sync. | |
`vaultspec-mcp` | Console script that launches the stdio Model Context Protocol (MCP)
server. | | `uv run python -m vaultspec_core.mcp_server.app` | Module invocation of the
MCP server (avoids binary locking on Windows). See [MCP reference](./MCP.md). |

## Global options

These options apply at the top level unless noted. `--debug` and `--version` are
top-level only. `--target` is accepted by target-aware workspace commands,
`vaultspec-core vault ...`, `vaultspec-core spec ...`, and
`vaultspec-core migrations ...`. `--json` is command-specific and appears only on
commands that support JavaScript Object Notation (JSON) output.

| Option | Short | Default | Description | | -------------- | ----- | ------- |
\--------------------------------------------------------------------------------------------------------------------------
| | `--target DIR` | `-t` | cwd | Target workspace directory. Overrides
`VAULTSPEC_TARGET_DIR`. Defaults to the current working directory if neither is set. | |
`--debug` | `-d` | off | Enable DEBUG-level logging (top-level flag). | | `--version` |
`-V` | - | Print version and exit (top-level flag). |

## Outcome vocabulary

State-changing commands report results with one shared seven-word vocabulary, so a
result reads the same regardless of which command produced it. Sync-shaped surfaces -
`vaultspec-core install`, `vaultspec-core sync`, the resource-scoped
`vaultspec-core spec <resource> sync` commands, and `vaultspec-core migrations run` -
print one glyph-prefixed line per item followed by a per-outcome count summary. With
`--json` the summary is nested inside the standard envelope (see "JSON output envelope"
below): `data.items` is the per-item array, each item carries its own `outcome`, and the
envelope's top-level `status` is the outcome for the whole invocation.

| Outcome | Glyph | Meaning | | ----------- | ----- |
\--------------------------------------------------------------------------- | |
`created` | `+` | A destination that did not exist now exists. | | `updated` | `~` | A
destination that existed was changed. | | `unchanged` | `=` | The destination already
matched the source; no write happened. | | `removed` | `-` | A destination that existed
no longer does. | | `restored` | `*` | A destination was reset to its canonical version.
| | `skipped` | `s` | A destination was not touched because a precondition or policy
excluded it. | | `failed` | `x` | A write was attempted and an error was encountered. |

A `--json` `status` of `mixed` means a single invocation produced items with more than
one distinct outcome. An `unchanged` status is the honest summary of a no-op run, not a
failure. A `skipped` outcome always carries a reason and is safe to interrogate. A
`failed` outcome is the only one that stops a pipeline.

## JSON output envelope

Every command that accepts `--json` emits one uniform envelope, so a consumer parses one
shape regardless of which command produced it:

```json
{
  "schema": "vaultspec.<command>.v1",
  "status": "<outcome word>",
  "data": { },
  "hints": { }
}
```

| Field | Required | Meaning | | -------- | -------- |
\------------------------------------------------------------------------------------------------
| | `schema` | yes | Namespaced identifier of the command plus a monotonic version
integer. | | `status` | yes | The canonical outcome word for the whole invocation (one
of the seven words above, or `mixed`). | | `data` | yes | The command-specific payload.
Read-only commands report their content here under stable keys. | | `hints` | no |
Structured next-step guidance. Absent when no hint applies; its presence never changes
`status`. |

The `schema` value follows the convention `vaultspec.<dotted-command-path>.v1` - for
example `vaultspec.sync.v1`, `vaultspec.vault.stats.v1`, or
`vaultspec.spec.rules.add.v1`. Every schema is currently at version `v1`. Adding new
keys under `data` is additive and does not bump the version; renaming or removing a key
bumps the integer (`v2`, ...). Schema bumps are recorded in the release notes.

Failures under `--json` emit the same envelope with the fixed schema
`vaultspec.error.v1` and `status` set to `failed`; `data.message` carries the
human-readable reason and `data.hint` carries remediation guidance when one is
available. A `status` of `failed` always pairs with a non-zero exit code.

Under `--json`, stdout carries only the envelope - no banners, no prose. Diagnostic
logging stays on stderr. The envelope is pretty-printed for readability. The single
question "did this run pass" is answered by the top-level `status` field alone, so a CI
gate reduces to inspecting that one key.

## Command signature contract

This block is generator-owned: run `vaultspec-core spec reference generate` to refresh
it. It is checked against the live Typer command tree by
`vaultspec-core spec reference generate --check`. Keep prose curated elsewhere in this
document, but do not hand-edit between the markers.

<!-- vaultspec:generated:begin command-inventory -->

```text
vaultspec-core install [OPTIONS] [PROVIDER]
vaultspec-core uninstall [OPTIONS] [PROVIDER]
vaultspec-core sync [OPTIONS] [PROVIDER]
vaultspec-core doctor [OPTIONS]
vaultspec-core status [OPTIONS] [TARGET]
vaultspec-core vault set-body [OPTIONS] REF
vaultspec-core vault set-frontmatter [OPTIONS] REF
vaultspec-core vault edit [OPTIONS] REF
vaultspec-core vault add [OPTIONS] DOC_TYPE
vaultspec-core vault stats [OPTIONS]
vaultspec-core vault list [OPTIONS] [DOC_TYPE]
vaultspec-core vault graph [OPTIONS]
vaultspec-core vault repair [OPTIONS]
vaultspec-core vault feature list [OPTIONS]
vaultspec-core vault feature index [OPTIONS]
vaultspec-core vault feature archive [OPTIONS] FEATURE_TAG
vaultspec-core vault feature unarchive [OPTIONS] FEATURE_TAG
vaultspec-core vault check all [OPTIONS]
vaultspec-core vault check body-links [OPTIONS]
vaultspec-core vault check annotations [OPTIONS]
vaultspec-core vault check dangling [OPTIONS]
vaultspec-core vault check orphans [OPTIONS]
vaultspec-core vault check frontmatter [OPTIONS]
vaultspec-core vault check modified-stamp [OPTIONS]
vaultspec-core vault check links [OPTIONS]
vaultspec-core vault check features [OPTIONS]
vaultspec-core vault check references [OPTIONS]
vaultspec-core vault check schema [OPTIONS]
vaultspec-core vault check structure [OPTIONS]
vaultspec-core vault check rename-integrity [OPTIONS]
vaultspec-core vault sanitize annotations [OPTIONS]
vaultspec-core vault rule promote [OPTIONS]
vaultspec-core vault adr supersede [OPTIONS] OLD_ADR
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
vaultspec-core vault plan trailer emit [OPTIONS]
vaultspec-core vault plan trailer validate [OPTIONS] MESSAGE_FILE
vaultspec-core vault link list [OPTIONS] [SRC]
vaultspec-core vault link add [OPTIONS] SRC DST
vaultspec-core vault link remove [OPTIONS] SRC DST
vaultspec-core spec doctor [OPTIONS]
vaultspec-core spec rules list [OPTIONS]
vaultspec-core spec rules add [OPTIONS] NAME
vaultspec-core spec rules show [OPTIONS] NAME
vaultspec-core spec rules edit [OPTIONS] NAME
vaultspec-core spec rules remove [OPTIONS] NAME
vaultspec-core spec rules rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec rules sync [OPTIONS] [PROVIDER]
vaultspec-core spec rules restore [OPTIONS] FILENAME
vaultspec-core spec rules status [OPTIONS]
vaultspec-core spec skills list [OPTIONS]
vaultspec-core spec skills add [OPTIONS] NAME
vaultspec-core spec skills show [OPTIONS] NAME
vaultspec-core spec skills edit [OPTIONS] NAME
vaultspec-core spec skills remove [OPTIONS] NAME
vaultspec-core spec skills rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec skills sync [OPTIONS] [PROVIDER]
vaultspec-core spec skills restore [OPTIONS] FILENAME
vaultspec-core spec skills status [OPTIONS]
vaultspec-core spec agents list [OPTIONS]
vaultspec-core spec agents add [OPTIONS] NAME
vaultspec-core spec agents show [OPTIONS] NAME
vaultspec-core spec agents edit [OPTIONS] NAME
vaultspec-core spec agents remove [OPTIONS] NAME
vaultspec-core spec agents rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec agents sync [OPTIONS] [PROVIDER]
vaultspec-core spec agents restore [OPTIONS] FILENAME
vaultspec-core spec agents status [OPTIONS]
vaultspec-core spec system show [OPTIONS]
vaultspec-core spec system sync [OPTIONS] [PROVIDER]
vaultspec-core spec hooks list [OPTIONS]
vaultspec-core spec hooks add [OPTIONS] NAME
vaultspec-core spec hooks show [OPTIONS] NAME
vaultspec-core spec hooks edit [OPTIONS] NAME
vaultspec-core spec hooks rename [OPTIONS] OLD_NAME NEW_NAME
vaultspec-core spec hooks remove [OPTIONS] NAME
vaultspec-core spec hooks restore [OPTIONS] FILENAME
vaultspec-core spec hooks sync [OPTIONS] [PROVIDER]
vaultspec-core spec hooks status [OPTIONS]
vaultspec-core spec hooks run [OPTIONS] EVENT
vaultspec-core spec mcps list [OPTIONS]
vaultspec-core spec mcps status [OPTIONS]
vaultspec-core spec mcps add [OPTIONS]
vaultspec-core spec mcps remove [OPTIONS] NAME
vaultspec-core spec mcps sync [OPTIONS] [PROVIDER]
vaultspec-core spec reference generate [OPTIONS]
vaultspec-core migrations status [OPTIONS]
vaultspec-core migrations run [OPTIONS]
vaultspec-core config get [OPTIONS] KEY
vaultspec-core config set [OPTIONS] KEY VALUE
vaultspec-core config unset [OPTIONS] KEY
vaultspec-core config list [OPTIONS]
```

<!-- vaultspec:generated:end command-inventory -->

## Workspace commands

### install

```bash
vaultspec-core install [OPTIONS] [PROVIDER]
```

Deploy the vaultspec framework into the target directory.

#### Arguments

| Argument | Default | Description | | ---------- | ------- |
--------------------------------------------------------- | | `PROVIDER` | `all` |
`all`, `core`, `claude`, `gemini`, `antigravity`, `codex` |

#### Options

| Option | Default | Description | | ----------- | ------- |
--------------------------------------- | | `--upgrade` | off | Re-sync builtins without
re-scaffolding | | `--dry-run` | off | Preview without writing | | `--force` | off |
Overwrite existing installation | | `--skip` | `[]` | Skip specific sync passes
(repeatable) | | `--json` | off | Emit machine-readable output |

`core` installs `.vaultspec/` only, without any provider config.

#### Examples

- **Install the framework for all supported AI provider layers in the current
  directory**:

  ```bash
  vaultspec-core install all
  ```

______________________________________________________________________

### uninstall

```bash
vaultspec-core uninstall [OPTIONS] [PROVIDER]
```

Remove the vaultspec framework from the target directory.

#### Arguments

| Argument | Default | Description | | ---------- | ------- |
--------------------------------------------------------- | | `PROVIDER` | `all` |
`all`, `core`, `claude`, `gemini`, `antigravity`, `codex` |

#### Options

| Option | Default | Description | | ---------------- | ------- |
---------------------------------------------- | | `--remove-vault` | off | Also remove
`.vault/` | | `--dry-run` | off | Preview without deleting | | `--force` | off |
Required to execute (uninstall is destructive) | | `--skip` | `[]` | Skip specific
removal passes (repeatable) | | `--json` | off | Emit machine-readable output |

`.vault/` is preserved by default. Pass `--remove-vault` to delete it.

#### Examples

- **Completely uninstall all framework files and delete all files in the vault**:

  ```bash
  vaultspec-core uninstall all --remove-vault --force
  ```

______________________________________________________________________

### sync

```bash
vaultspec-core sync [OPTIONS] [PROVIDER]
```

Authoritative complete sync from `.vaultspec/` to enrolled provider outputs: rules,
skills, agents, system prompts, provider config stubs, and MCP entries. After editing or
adding framework source files, this is the normal propagation command.

#### Arguments

| Argument | Default | Description | | ---------- | ------- |
------------------------------------------------- | | `PROVIDER` | `all` | `all`,
`claude`, `gemini`, `antigravity`, `codex` |

`core` is not a valid sync target because sync reads from `.vaultspec/`. Use
`vaultspec-core install --upgrade` or `vaultspec-core install --force` for
framework/provider scaffolding repair, not as the normal propagation path after source
edits.

#### Options

| Option | Default | Description | | ----------- | ------- |
----------------------------------------------------- | | `--dry-run` | off | Preview
changes without writing | | `--force` | off | Prune stale files and overwrite
user-authored content | | `--skip` | `[]` | Skip specific sync passes (repeatable) | |
`--json` | off | Emit machine-readable output |

#### Examples

- **Synchronize modified rule and agent source files to all provider workspaces**:

  ```bash
  vaultspec-core sync all
  ```

## Vault commands

Group command: `vaultspec-core vault [OPTIONS] COMMAND [ARGS]...`

### vaultspec-core vault add

```bash
vaultspec-core vault add [OPTIONS] DOC_TYPE
```

Create a new `.vault/` document from a template.

#### Arguments

| Argument | Description | | ---------- |
------------------------------------------------------- | | `DOC_TYPE` | `adr`, `audit`,
`exec`, `plan`, `reference`, `research` |

#### Options

| Option | Short | Default | Description | | --------------- | ----- | --------------- |
\------------------------------------------------------------------------------------- |
| `--feature TAG` | `-f` | None (required) | Feature tag (kebab-case, lowercase letters,
digits, hyphens). | | `--date DATE` | - | today | Override date (ISO 8601, e.g.,
YYYY-MM-DD). | | `--title TITLE` | - | None | Document title. For execution records,
overrides the default heading. | | `--related DOC` | `-r` | None | Related document(s).
Accepts path, filename, stem, or `[[wiki-link]]`. Repeatable. | | `--tags TAG` | - |
None | Additional tags beyond the required directory and feature tags. Repeatable. | |
`--force` | - | off | Overwrite an existing document at the resolved path. | |
`--dry-run` | - | off | Preview without writing files. | | `--json` | - | off | Emit
machine-readable JSON output in standard envelope. | | `--tier TIER` | - | L1 | Plan
tier (`L1`, `L2`, `L3`, `L4`). (Ignored for non-plan types). | | `--step STEP` | - |
None | Canonical ID or display path of a specific step to scaffold. (Only valid for
`exec`). | | `--all-steps` | - | off | Scaffold execution records for all steps in
parent plan. (Only valid for `exec`). |

#### Step-Aware Execution Scaffolding (`DOC_TYPE=exec`)

When adding an execution record (`exec`), the CLI supports step-aware mechanics to
target individual or bulk steps from the parent plan.

##### Option Gating and Fallbacks

- **Mutual Exclusion**: `--step` and `--all-steps` are strictly mutually exclusive. If
  both are provided, or if either is passed with a document type other than `exec`, the
  CLI aborts with exit code `1`.
- **Legacy Fallback**: If neither option is provided when creating an `exec` document,
  the CLI displays a yellow warning:
  `Deprecation Warning: Scaffolding flat (non-step-aware) execution records is deprecated. Use --step or --all-steps.`
  It then falls back to scaffolding a flat record routed to
  `.vault/exec/{date_str}-{feature}-exec.md` without nested folders.

##### Parent Plan Resolution

To resolve step definitions, the CLI searches for the parent plan using a two-tiered
lookup:

1. **Explicit (`--related` option)**: Scans user-supplied `--related` arguments. If
   multiple resolved links are provided, the CLI iterates over them and uses the first
   resolved plan document found.
1. **Implicit (Unique Feature Lookup)**: Scans the entire vault for plan documents
   tagged with the corresponding feature tag.

- **Resolution Failures**:
  - If zero plans are found, the CLI aborts with exit code `1` and prints:
    `No plan found for feature '{feat}'. Create a plan document before adding execution records.`
  - If multiple plans are found, the CLI aborts with exit code `1` and prints:
    `Multiple plans found for feature '{feat}': {names}. Specify the parent plan using --related.`

##### Custom Directory Routing

Step-aware execution records are written to a nested folder structure:
`.vault/exec/{plan-date}-{feature}/{plan-date}-{feature}-{suffix}.md` where `{suffix}`
is the step's display path with all dots replaced by hyphens (e.g., display path
`P01.S01` is saved with suffix `P01-S01`).

##### Parent Plan Link Hydration

The CLI automatically prepends the resolved parent plan's filename stem as a wiki-link
(e.g., `[[2026-05-17-test-feature-plan]]`) as the first entry in the YAML frontmatter
`related:` list.

##### Template Placeholder Hydration Rules

The scaffolding engine populates the following placeholders in the execution template:

- `{step_id}`: Hydrated with the step's canonical ID (e.g., `S01`).

- `{plan_stem}`: Hydrated with the parent plan's filename stem (e.g.,
  `2026-05-17-test-feature-plan`).

- `{heading}`: Hydrated with the step action. If a title is explicitly passed via
  `--title`, it overrides this heading. Defaults to `{feature} <display-path>` if
  neither is available.

- `{scope_block}`: If the step defines a scope (e.g., `src/foo.py; src/bar.py`), parses
  comma/semicolon-separated values and hydrates a clean list block:

  ````markdown
  ```markdown
  ## Scope

  - `src/foo.py`
  - `src/bar.py`
  ```
  ````

This block is omitted entirely if the step defines no scope.

##### Bulk Scaffolding & Idempotency

- `--all-steps` iterates over **all steps** (both checked and unchecked) listed in the
  resolved parent plan.
- **Idempotency**: Existing files are skipped and reported as `skipped; exists` unless
  the `--force` flag is supplied, which overwrites them.
- **Outcome Reporting**: Emits a structured outcome list. Plain-text lists files tagged
  with lowercase outcome words: `created`, `skipped`, or `updated`. JSON output
  (`--json`) emits a machine-readable payload adhering to the `vaultspec.vault.add.v1`
  envelope schema listing details for each file.

##### Examples

- **Scaffold all execution records for a feature plan (Bulk Scaffolding)**:

```bash
vaultspec-core vault add exec --feature test-feature --all-steps
```

- **Scaffold an execution record for a specific step**:

```bash
vaultspec-core vault add exec --feature test-feature --step P01.S01
```

______________________________________________________________________

### vaultspec-core status

```bash
vaultspec-core status [OPTIONS] [TARGET]
```

Orient in a vaultspec vault: rollup or a grounding trace for a target. This is the
top-level zeroth move. Read-only - it never writes and produces no artifact.

**Rollup mode** (no `TARGET`): reports plans in flight, each with a one-line overview
(tier, completed waves and phases, step completion, and the next open step); plans
recently completed; recent changes grouped by type with execution records collapsed per
feature; active features; and vault totals. Outcome semantics: always `unchanged`
(read-only verb). Advisory hints point at the targeted form and at
`vaultspec-core spec doctor` for framework health.

**Targeted mode** (`TARGET` is a plan stem, plan path, or feature handle): renders the
grounding trace - a plan-line header, then each step (display path, checkbox state, a
cursor on the next open step) mapped to its execution-record stem, or `no record` for
open steps without one, or `unlinked` for exec records that reference the plan but lack
a resolvable `step_id:`. Grounding documents are grouped by type beneath the step list.
A feature handle traces every plan under that feature.

`vaultspec-core status` is orientation, not auditing: it describes what exists without
judging conformance. Use `vaultspec-core vault check` to audit and
`vaultspec-core spec doctor` for framework health.

#### Options

| Option | Default | Description | | ---------------- | ------- |
-------------------------------------------------------------- | | `--limit N` | `10` |
Recently modified documents to show, per type. | | `--since N` | None | Show documents
modified within the last N days. | | `--paths` | off | Show each referenced document's
path (targeted mode). | | `--verbose-exec` | off | List execution records instead of
collapsing them per feature. | | `--json` | off | Emit machine-readable output
(`vaultspec.vault.status.v1`). | | `--no-hints` | off | Suppress next-step advisory
hints. |

`--limit` and `--since` apply only in rollup mode. `--since` switches from a last-N
count to a day-window query.

#### Examples

- **Get a vault-wide orientation rollup (in-flight plans and recent changes)**:

  ```bash
  vaultspec-core status
  ```

- **Trace a specific plan to its execution records and grounding documents**:

  ```bash
  vaultspec-core status 2026-05-17-test-feature-plan
  ```

- **Show only documents modified in the last 7 days**:

  ```bash
  vaultspec-core status --since 7
  ```

______________________________________________________________________

### vaultspec-core vault list

```bash
vaultspec-core vault list [OPTIONS] [DOC_TYPE]
```

List vault documents.

#### Arguments

| Argument | Default | Description | | ---------- | ------- | ----------------------- |
| `DOC_TYPE` | None | Filter by document type |

#### Options

| Option | Short | Default | Description | | --------------- | ----- | ------- |
----------------------------- | | `--feature TAG` | `-f` | None | Filter by feature tag
| | `--date DATE` | - | None | Filter by date | | `--json` | - | off | Emit
machine-readable output. |

#### Examples

- **List all plans in the vault for a specific feature**:

  ```bash
  vaultspec-core vault list plan --feature test-feature
  ```

______________________________________________________________________

### vaultspec-core vault stats

```bash
vaultspec-core vault stats [OPTIONS]
```

Show vault statistics and document counts.

#### Options

| Option | Short | Default | Description | | --------------- | ----- | ------- |
-------------------------------------- | | `--feature TAG` | `-f` | None | Filter by
feature tag | | `--date DATE` | - | None | Filter by date | | `--type TYPE` | - | None |
Filter by document type | | `--invalid` | - | off | Show only documents with invalid
links | | `--orphaned` | - | off | Show only orphaned documents | | `--json` | - | off |
Emit machine-readable output. |

#### Examples

- **Display vault-wide statistics with details for orphaned and invalid-link
  documents**:

  ```bash
  vaultspec-core vault stats --invalid --orphaned
  ```

______________________________________________________________________

### vaultspec-core vault graph

```bash
vaultspec-core vault graph [OPTIONS]
```

Outputs a hierarchical tree grouped by feature and type.

#### Options

| Option | Short | Default | Description | | ------------------------ | ----- | -------
| ------------------------------------------------ | | `--feature TAG` | `-f` | None |
Scope to a single feature | | `--json` | - | off | Output as networkx node-link JSON | |
`--metrics` | `-m` | off | Show aggregate graph metrics | | `--ascii` | - | off | Render
ASCII topology | | `--body` | - | off | Include document body in JSON output | |
`--node STEM` | - | None | Scope JSON to a node's local (ego) neighbourhood | |
`--depth N` | - | 1 | Ego-graph radius in hops; only used with --node | |
`--derived/--no-derived` | - | on | Include the derived relatedness edge set in JSON |

The `--json` payload (schema `vaultspec.vault.graph.v2`) carries typed weighted explicit
edges (`kind`, `multiplicity`, `weight`), node-size hints (`pagerank`, `in_degree`), and
a separate `derived_edges` array of implicit relatedness edges kept out of the canonical
`edges` array. A missing `--node` stem exits 1 with a `failed` envelope.

#### Examples

- **Visualize the vault hierarchy and structure as an ASCII tree scoped to a feature**:

  ```bash
  vaultspec-core vault graph --feature test-feature --ascii
  ```

______________________________________________________________________

### vaultspec-core vault repair

```bash
vaultspec-core vault repair [OPTIONS]
```

Run the operator repair pipeline for `.vault/` content. This is the guided recovery
surface for degraded vaults. It reports preflight and migration state, runs the health
checks, applies supported mechanical fixes unless `--dry-run` is set, refreshes
generated feature indexes unless `--no-index` is set, rebuilds graph state, and runs a
postcheck pass.

`vaultspec-core vault repair` is broader than `vaultspec-core vault check all --fix`.
The check-level fixer remains available for compatibility, but it does not own generated
index refresh, post-fix graph rebuild, root-cause grouping, or final delta reporting. It
also strips standalone annotation comments during the fix phase. Inline HTML comments
embedded in prose are preserved.

#### Options

| Option | Short | Default | Description | | ---------------------------- | ----- |
------- | ------------------------------------------------ | | `--dry-run` | - | off |
Preview repair actions without writing | | `--include-index/--no-index` | - | on |
Refresh generated feature indexes during repair | | `--feature TAG` | `-f` | None |
Scope repair and index refresh to one feature | | `--verbose` | `-v` | off | Show
INFO-level diagnostics and detailed paths | | `--json` | - | off | Emit machine-readable
phase and summary payloads |

#### Phases

| Phase | Purpose | | ----------- |
--------------------------------------------------------------------- | | `preflight` |
Report migration status and platform path behavior | | `check` | Run the current vault
health suite without mutation | | `fix` | Apply supported safe check-level fixes, or
report planned fixes | | `index` | Refresh or preview generated
`.vault/index/<feature>.index.md` files | | `postcheck` | Rebuild graph state and rerun
checks after mutation | | `summary` | Report changed files, generated indexes,
unresolved work, root causes |

Dry-run mode never writes generated indexes or check fixes. If migrations are pending,
dry-run reports that state instead of entering the vault scan path that would apply lazy
migrations on first use.

#### Examples

- **Scan and apply all safe automatic repairs to a degraded vault**:

  ```bash
  vaultspec-core vault repair
  ```

______________________________________________________________________

### vaultspec-core vault sanitize annotations

```bash
vaultspec-core vault sanitize annotations [OPTIONS]
```

Strip generated template annotations from `.vault/` documents. Template hydration keeps
agent-facing instructions in newly created documents; this command removes those
instructions only when explicitly requested. Use `--dry-run` to see which files would be
stripped without mutating the vault. The sanitizer removes YAML frontmatter comment
directives, standalone HTML comment blocks, and malformed standalone `<-- ... -->`
annotation blocks. It preserves fenced examples, inline HTML comments embedded in prose,
and machine-owned comments such as retired plan markers.

#### Options

| Option | Short | Default | Description | | --------------- | ----- | ------- |
------------------------------------ | | `--feature TAG` | `-f` | None | Sanitize
documents for one feature | | `--dry-run` | - | off | Preview annotation removals | |
`--verbose` | `-v` | off | Show stripped files | | `--json` | - | off | Emit
machine-readable check payloads |

#### Examples

- **Strip all default template instructions and annotations from a feature's
  documents**:

  ```bash
  vaultspec-core vault sanitize annotations --feature test-feature
  ```

______________________________________________________________________

### vaultspec-core vault feature list

```bash
vaultspec-core vault feature list [OPTIONS]
```

List all feature tags in the vault.

#### Options

| Option | Default | Description | | ------------- | ------- |
----------------------------------------- | | `--date DATE` | None | Filter by date | |
`--orphaned` | off | Show only features with no incoming links | | `--type TYPE` | None
| Filter by document type | | `--json` | off | Emit machine-readable output. |

#### Examples

- **List all active feature tags in the vault**:

  ```bash
  vaultspec-core vault feature list
  ```

______________________________________________________________________

### vaultspec-core vault feature index

```bash
vaultspec-core vault feature index [OPTIONS]
```

Generate or update `<feature>.index.md` files in `.vault/index/`. Each index links to
every document sharing that feature tag, making implicit feature clusters explicit in
the graph. Indexes carry the `#index` directory tag plus the feature tag and are
auto-managed.

#### Options

| Option | Short | Default | Description | | --------------- | ----- | ------- |
------------------------------------- | | `--feature TAG` | `-f` | None | Generate index
for a specific feature | | `--json` | - | off | Emit machine-readable output. |

#### Examples

- **Rebuild or generate the index document for a specific feature**:

  ```bash
  vaultspec-core vault feature index --feature test-feature
  ```

______________________________________________________________________

### vaultspec-core vault feature archive

```bash
vaultspec-core vault feature archive [OPTIONS] FEATURE_TAG
```

Move all documents for a feature tag to the archive.

#### Options

| Option | Short | Default | Description | | ----------- | ----- | ------- |
-------------------------------------------------------- | | `--dry-run` | - | off |
Preview planned changes. | | `--json` | - | off | Emit machine-readable output. | |
`--target` | `-t` | None | Target directory (defaults to current working directory) |

#### Examples

- **Archive all documents for a completed feature tag**:

  ```bash
  vaultspec-core vault feature archive test-feature
  ```

______________________________________________________________________

### vaultspec-core vault feature unarchive

```bash
vaultspec-core vault feature unarchive [OPTIONS] FEATURE_TAG
```

Restore all archived documents for a feature tag.

#### Options

| Option | Short | Default | Description | | ----------- | ----- | ------- |
-------------------------------------------------------- | | `--dry-run` | - | off |
Preview planned changes. | | `--json` | - | off | Emit machine-readable output. | |
`--target` | `-t` | None | Target directory (defaults to current working directory) |

#### Examples

- **Restore and unarchive all documents for a previously archived feature**:

  ```bash
  vaultspec-core vault feature unarchive test-feature
  ```

______________________________________________________________________

### vaultspec-core vault adr supersede

```bash
vaultspec-core vault adr supersede [OPTIONS] OLD_ADR
```

Supersede an old ADR with a new ADR.

#### Arguments

| Argument | Description | | --------- | ------------------------- | | `OLD_ADR` | Old
ADR stem to supersede |

#### Options

| Option | Short | Default | Description | | ----------- | ----- | ------- |
-------------------------------------------------------- | | `--by` | - | None | New ADR
stem that supersedes the old one | | `--dry-run` | - | off | Preview without writing | |
`--json` | - | off | Output as JSON | | `--target` | `-t` | None | Target directory
(defaults to current working directory) |

#### Examples

- **Supersede an outdated ADR with a newly created one**:

  ```bash
  vaultspec-core vault adr supersede 2026-05-17-old-adr-stem --by 2026-05-26-new-adr-stem
  ```

______________________________________________________________________

### vaultspec-core vault rule promote

```bash
vaultspec-core vault rule promote [OPTIONS]
```

Promote an audit finding to a project-level rule.

#### Options

| Option | Short | Default | Description | | ----------- | ----- | ------- |
-------------------------------------------------------- | | `--from` | - | None | Audit
stem to promote from (required) | | `--as` | - | None | Kebab-case name of the promoted
rule (required) | | `--force` | - | off | Overwrite existing rule source | | `--dry-run`
| - | off | Preview without writing | | `--json` | - | off | Output as JSON | |
`--target` | `-t` | None | Target directory (defaults to current working directory) |

#### Examples

- **Promote a specific finding from an audit file into a project-shared rule**:

  ```bash
  vaultspec-core vault rule promote --from 2026-05-17-feature-audit --as project-rule-name
  ```

______________________________________________________________________

### vaultspec-core vault check

```bash
vaultspec-core vault check [OPTIONS] COMMAND [ARGS]...
```

Run health checks on `.vault/`. Exits with code `1` if errors are found.

#### Shared options

| Option | Short | Default | Description | | --------------- | ----- | ------- |
-------------------------------- | | `--fix` | - | off | Apply auto-fixes where
supported | | `--feature TAG` | `-f` | None | Limit to a specific feature | |
`--verbose` | `-v` | off | Show INFO-level diagnostics |

#### Subcommands

| Subcommand | `--fix` | `--feature` | Description | | ------------------ | ------- |
\----------- |
\------------------------------------------------------------------------------------------
| | `all` | partial | yes | Run every check in sequence | | `annotations` | yes | yes |
Find generated template annotations | | `body-links` | no | yes | Find wiki-links and
markdown path links in document body text | | `dangling` | yes | yes | Find `related:`
wiki-links that resolve to no document | | `frontmatter` | yes | yes | Validate
frontmatter against vault schema | | `links` | yes | yes | Check wiki-links follow
Obsidian convention (no `.md` extension) | | `orphans` | no | yes | Find documents with
no incoming wiki-links | | `features` | no | yes | Check feature tag completeness
(missing doc types) | | `modified-stamp` | yes | yes | Flag missing, unparseable, or
stale `modified:` stamps; `--fix` normalizes to `yyyy-mm-dd` | | `references` | yes |
yes | Check cross-references within features | | `schema` | yes | yes | Enforce
dependency rules (ADR refs research, plan refs ADR) | | `structure` | yes | no | Check
directory structure and filename conventions | | `rename-integrity` | yes | no | Check
name/filename integrity for rules, skills, and agents |

`yes` = fully supported, `partial` = only the sub-checks that accept `--fix` apply fixes
(`all` dispatches to every check), `no` = flag rejected with error. `structure` does not
support `--feature` filtering.

Use `vaultspec-core vault repair` when the operator goal is end-to-end recovery with
generated index refresh, post-fix validation, and a final delta report.

#### Examples

- **Run all vault health checks to verify link integrity and directory structure**:

  ```bash
  vaultspec-core vault check all
  ```

- **Audit and automatically repair dangling wiki-links**:

  ```bash
  vaultspec-core vault check dangling --fix
  ```

- **Check feature completeness for a specific feature tag**:

  ```bash
  vaultspec-core vault check features --feature test-feature
  ```

- **Scan for and report any generated template instructions or annotations**:

  ```bash
  vaultspec-core vault check annotations --feature test-feature
  ```

- **Verify Obsidian-style wiki links in body text resolved against the vault**:

  ```bash
  vaultspec-core vault check body-links
  ```

- **Audit rule, skill, and agent filenames for matching name tags**:

  ```bash
  vaultspec-core vault check rename-integrity
  ```

- **Find all unreferenced (orphaned) documents in the vault**:

  ```bash
  vaultspec-core vault check orphans
  ```

- **Validate document frontmatter fields against required templates**:

  ```bash
  vaultspec-core vault check frontmatter --fix
  ```

- **Check wiki-link formats (ensuring no .md file extensions are used)**:

  ```bash
  vaultspec-core vault check links
  ```

- **Enforce architectural schema dependency rules**:

  ```bash
  vaultspec-core vault check schema
  ```

- **Verify all external references are valid and up to date**:

  ```bash
  vaultspec-core vault check references
  ```

- **Check directory structure and naming conventions for rules, skills, and agents**:

  ```bash
  vaultspec-core vault check structure
  ```

### vaultspec-core vault plan

```bash
vaultspec-core vault plan [OPTIONS] COMMAND [ARGS]...
```

Inspect and manipulate plan documents per the plan-hardening convention. Plans declare a
complexity tier (`L1`, `L2`, `L3`, `L4`) in frontmatter and are structured as
`Epic > Wave > Phase > Step`. Every mutating operation goes through this surface.
Canonical identifiers (`S##`, `P##`, `W##`) remain append-only and gap-no-reuse.
`vaultspec-core vault plan check` flags hand-edits to checkbox glyphs or display paths.

#### Examples

- **Query all open steps in a plan**:

  ```bash
  vaultspec-core vault plan query .vault/plan/2026-05-17-test-feature-plan.md --open
  ```

- **Append a new step to the active phase of a plan**:

  ```bash
  vaultspec-core vault plan step add --action "Implement login authentication handler" --scope "src/auth.py" .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Toggle completion checkbox of a step**:

  ```bash
  vaultspec-core vault plan step toggle .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Renumber a phase to resolve duplicate identifier conflicts**:

  ```bash
  vaultspec-core vault plan phase renumber --to P02 .vault/plan/2026-05-17-test-feature-plan.md P01
  ```

- **Validate the formatting and structure of an existing plan file**:

  ```bash
  vaultspec-core vault plan check .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Mark a plan step completed (idempotent check)**:

  ```bash
  vaultspec-core vault plan step check .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Mark a plan step incomplete (idempotent uncheck)**:

  ```bash
  vaultspec-core vault plan step uncheck .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Insert a new step before an existing anchor step**:

  ```bash
  vaultspec-core vault plan step insert --action "Validate input arguments" --before S02 .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Edit an existing step's action prose and code scope**:

  ```bash
  vaultspec-core vault plan step edit --action "New auth handler" --scope "src/auth.py" .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Move a step to a different phase inside the plan**:

  ```bash
  vaultspec-core vault plan step move --to-phase P02 .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Retire a plan step permanently**:

  ```bash
  vaultspec-core vault plan step remove .vault/plan/2026-05-17-test-feature-plan.md S01
  ```

- **Append a new phase to the current wave of a plan**:

  ```bash
  vaultspec-core vault plan phase add --title "Authentication Layer" --intent "Set up secure login/signup" .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Insert a phase before an existing anchor phase**:

  ```bash
  vaultspec-core vault plan phase insert --title "Database Setup" --before P02 .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Edit a phase's title or intent prose in place**:

  ```bash
  vaultspec-core vault plan phase edit --title "Updated Auth Setup" .vault/plan/2026-05-17-test-feature-plan.md P01
  ```

- **Move a phase to a different wave in the plan**:

  ```bash
  vaultspec-core vault plan phase move --to-wave W02 .vault/plan/2026-05-17-test-feature-plan.md P01
  ```

- **Retire a phase along with all of its descendant steps**:

  ```bash
  vaultspec-core vault plan phase remove .vault/plan/2026-05-17-test-feature-plan.md P01
  ```

- **Append a new wave to a plan**:

  ```bash
  vaultspec-core vault plan wave add --title "Advanced Features" --intent "Add AI features" .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Insert a wave after an existing anchor wave**:

  ```bash
  vaultspec-core vault plan wave insert --title "Optimization Wave" --after W01 .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Edit a wave's title or intent prose in place**:

  ```bash
  vaultspec-core vault plan wave edit --title "Updated Core Wave" .vault/plan/2026-05-17-test-feature-plan.md W01
  ```

- **Move a wave to reposition it within the plan**:

  ```bash
  vaultspec-core vault plan wave move --after W02 .vault/plan/2026-05-17-test-feature-plan.md W01
  ```

- **Retire a wave along with all of its descendant phases and steps**:

  ```bash
  vaultspec-core vault plan wave remove .vault/plan/2026-05-17-test-feature-plan.md W01
  ```

- **Display the plan's high-level Epic intent paragraph**:

  ```bash
  vaultspec-core vault plan epic intent show .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Update the plan's Epic intent paragraph**:

  ```bash
  vaultspec-core vault plan epic intent edit --text "Epic intent text associating PM issues" .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Display the plan's current complexity tier**:

  ```bash
  vaultspec-core vault plan tier show .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Promote a plan's complexity tier to L4**:

  ```bash
  vaultspec-core vault plan tier promote --target L4 --epic-intent "Epic goal" .vault/plan/2026-05-17-test-feature-plan.md
  ```

- **Demote a plan's complexity tier to L1**:

  ```bash
  vaultspec-core vault plan tier demote --target L1 --force .vault/plan/2026-05-17-test-feature-plan.md
  ```

#### Read commands

| Subcommand | Description | | ---------- |
\----------------------------------------------------------------------------------------
| | `status` | Report plan health, structure, and completion. `--json` emits a
machine-readable payload | | `check` | Validate convention compliance; with `--fix`,
apply autofixable transformations | | `query` | Filter Step rows by `--phase`/`--wave`
scope and `--open`/`--closed` predicate |

`vaultspec-core vault plan check` exits `1` when at least one ERROR-severity finding is
present.

______________________________________________________________________

#### vaultspec-core vault plan status

```bash
vaultspec-core vault plan status [OPTIONS] PATH
```

Report plan health, structure, completion percentages, and identify missing execution
records.

##### Arguments

| Argument | Description | | -------- | ------------------------------------------------
| | `PATH` | Path to the `.vault/plan/...-plan.md` plan file. |

##### Options

| Option | Short | Default | Description | | -------- | ----- | ------- |
------------------------------------- | | `--json` | - | off | Emit machine-readable
status payload. |

##### General Output

When run without `--json`, the command renders a console summary displaying:

- **Plan Path & Complexity Tier**: Declared level (`L1` to `L4`).
- **Container Counts**: Total count of Epic, Waves, Phases, and Steps.
- **Completion Status**: Checked vs. unchecked steps and total progress percentage.

##### Execution Record Verification (`exec-missing`)

The status command performs an active sanity check on execution records:

- If a step is checked (`[x]`) in the plan but no step-aware execution record (e.g.
  `.vault/exec/{plan-date}-{feature}/{plan-date}-{feature}-P01-S01.md`) exists in the
  vault, the CLI generates a yellow warning block:

  ```text
  ! exec-missing: checked steps lacking execution records: S01, S02
  ```

- This warning does not block execution or raise exit codes; the command still exits
  with code `0`.

##### Machine-Readable Output (`--json`)

When passed `--json`, the output utilizes the uniform `vaultspec.vault.plan.status.v1`
schema envelope:

```json
{
  "schema": "vaultspec.vault.plan.status.v1",
  "status": "unchanged",
  "data": {
    "path": ".vault/plan/2026-05-17-test-feature-plan.md",
    "tier": "L2",
    "waves": 0,
    "phases": 1,
    "steps": 5,
    "checked_steps": 2,
    "completion_pct": 40.0,
    "exec_missing_ids": ["S01", "S02"]
  }
}
```

##### Examples

- **Check the progress and execution record status of a plan**:

  ```bash
  vaultspec-core vault plan status .vault/plan/2026-05-17-test-feature-plan.md
  ```

______________________________________________________________________

#### Step commands

| Subcommand | Description | | ---------- |
\--------------------------------------------------------------------------------- | |
`add` | Append a Step at the next-available `S##`. Requires `--action` and `--scope` | |
`insert` | Insert at a named position with `--before`/`--after`; parent inferred from
anchor | | `edit` | Replace `--action`, `--scope`, or both without changing the
canonical identifier | | `move` | Re-parent (`--to-phase`), re-position
(`--before`/`--after`), or both | | `remove` | Retire the Step's canonical id
permanently; the next-available counter skips it | | `check` | Mark the Step closed
(`[x]`); idempotent | | `uncheck` | Mark the Step open (`[ ]`); idempotent | | `toggle`
| Flip the Step's checkbox state |

#### Phase commands

| Subcommand | Description | | ---------- |
----------------------------------------------------------------------------- | | `add`
| Append a Phase at the next-available `P##`. Requires `--title` and `--intent` | |
`insert` | Insert at a named position with `--before`/`--after` | | `edit` | Replace
`--title`, `--intent`, or both in place | | `move` | Re-parent (`--to-wave`),
re-position (`--before`/`--after`), or both | | `renumber` | Remediate a duplicated id
via `--to <P##>`; refuses live / retired collisions | | `remove` | Retire the Phase plus
every descendant Step (cascading retirement) |

`phase renumber` is the audited remediation surface for collisions inherited from legacy
plans. One example is a writer who treated `P##` as Wave-scoped rather than
per-document. The verb retires the old id so it cannot be reused, then recomputes every
descendant Step's display path against the new parent canonical id.

#### Wave commands

Identical shape to Phase, but the parent is implicit (Epic frame). Only
`--before`/`--after` re-position. No `--to-epic` flag exists. Wave operations require
`L3` or `L4`.

#### Epic intent (L4 only)

| Subcommand | Description | | ------------- |
\------------------------------------------------------------------------------------------------
| | `intent show` | Print the Epic intent paragraph | | `intent edit` | Replace the Epic
intent paragraph; `--text` must declare the project-management (PM) association |

#### Tier commands

| Subcommand | Description | | ---------- |
\--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
| | `show` | Print the plan's declared tier | | `promote` | Advance the tier
transitively, for example L1 -> L4 in one call. Synthesized containers use
`--phase-title`/`--phase-intent`/`--wave-title`/`--wave-intent`/`--epic-intent` for
placeholders | | `demote` | Step the tier down. Refuses with an error when the
collapsing layer holds more than one container; pass `--force` to retire the dropped ids
and proceed |

#### Move-flag precedence

`step move` and `phase move` accept the re-parent flag (`--to-phase` / `--to-wave`) and
the position flags (`--before` / `--after`) independently or together:

- Re-parent flag alone re-parents and appends to the destination tail.
- Position flag alone re-positions within the current parent; the anchor must share that
  parent.
- Both flags re-parent and position the item; the anchor must reside in the destination
  post-move.

A self-referential move (`step move S01 --before S01`) is rejected with the relevant
`Move{Step,Phase,Wave}Error`.

#### Identifier retirement

`remove`, multi-step demotion, and Wave / Phase removal all add the retired canonical id
to a hidden `<!-- RETIRED: ... -->` ledger embedded in the plan body. `next_available_*`
consults this ledger so retired identifiers are never reused, even across
`parse / serialize` round-trips invoked by `--fix`.

## Spec commands

Group command: `vaultspec-core spec [OPTIONS] COMMAND [ARGS]...`

Spec subcommands that operate on a workspace accept `--target / -t DIR`. `--json` is
command-specific and appears only on commands that support machine-readable output.

### vaultspec-core spec doctor

```bash
vaultspec-core spec doctor [OPTIONS]
```

Run diagnostic collectors across the framework, providers, builtins, `.gitignore`, vault
content, and configuration files. Reports findings and exits with the highest severity
observed. The vault content row is read-only; when generated template annotations are
present, doctor reports a warning and points to
`vaultspec-core vault sanitize annotations`. Unreadable vault markdown files are
reported as warnings and are not modified.

#### Options

| Option | Short | Default | Description | | -------------- | ----- | ------- |
------------------------------------------------ | | `--target DIR` | `-t` | cwd |
Diagnose a directory other than the current one. | | `--json` | - | off | Emit the
diagnosis as JSON. |

Exit codes: `0` = all ok, `1` = warnings, `2` = errors.

#### Examples

- **Diagnose overall workspace health across configuration, git, and vault**:

  ```bash
  vaultspec-core spec doctor
  ```

______________________________________________________________________

### vaultspec-core spec rules / vaultspec-core spec skills / vaultspec-core spec agents

Create, read, update, and delete (CRUD) operations for framework resources. All three
groups share the same subcommand structure.

```bash
vaultspec-core spec rules [OPTIONS] COMMAND [ARGS]...
vaultspec-core spec skills [OPTIONS] COMMAND [ARGS]...
vaultspec-core spec agents [OPTIONS] COMMAND [ARGS]...
```

#### Subcommands

| Subcommand | Signature | Description | | ---------- |
\------------------------------------------------------------- |
\--------------------------------------------------------------------------------------------
| | `list` | - | List all resources | | `add` |
`NAME [--body BODY] [--from-file FILE] [--force] [--dry-run]` | Create a resource. | |
`show` | `NAME` | Print resource content to stdout | | `edit` | `NAME [--editor EDITOR]`
| Open in configured editor. Resolution order: --editor flag, local config, VISUAL,
EDITOR, vi | | `remove` | `NAME [--yes\|--force]` (`-y`) | Delete a resource. Prompts
unless confirmed. | | `rename` | `OLD_NAME NEW_NAME` | Rename a resource | | `sync` |
`[--dry-run] [--force]` | Resource-scoped sync; use top-level `vaultspec-core sync` for
a complete provider refresh | | `restore` | `FILENAME` | Restore to snapshotted original
| | `status` | `[--json]` | Report dry-run sync with prune enabled, returning
missing/drifted/stale status |

`edit` accepts the `--editor` option to override the editor binary for this invocation.
`add` accepts the unified `--body` flag for direct content or `--from-file` to read from
a file.

`vaultspec-core spec <resource> sync` commands are narrow maintenance surfaces. They do
not guarantee that provider-facing config stubs such as `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, or `.codex/config.toml` have been fully refreshed. Run
`vaultspec-core sync` after source-side changes when the goal is a complete
provider-facing workspace.

#### Examples

- **List all rules, skills, or agents configured in the current project**:

  ```bash
  vaultspec-core spec rules list
  ```

- **Create a new custom project-level rule**:

  ```bash
  vaultspec-core spec rules add enforce-newline --body "All workspace source files must end with a single trailing newline."
  ```

- **Create a new custom skill from a local template**:

  ```bash
  vaultspec-core spec skills add unit-test-runner --description "Run python pytest suite" --template "templates/skill_template.md"
  ```

- **Create a new custom agent persona**:

  ```bash
  vaultspec-core spec agents add database_expert --description "An expert database optimization agent"
  ```

- **Display the content of a project rule**:

  ```bash
  vaultspec-core spec rules show enforce-newline
  ```

- **Edit a project skill using a specified editor command**:

  ```bash
  vaultspec-core spec skills edit unit-test-runner --editor zed
  ```

- **Delete a project agent persona**:

  ```bash
  vaultspec-core spec agents remove database_expert --force
  ```

- **Rename a project-level rule atomically**:

  ```bash
  vaultspec-core spec rules rename old-rule-name new-rule-name
  ```

- **Synchronize local rules changes to enrolled provider output stubs**:

  ```bash
  vaultspec-core spec rules sync
  ```

- **Report parsing and synchronization status of project skills**:

  ```bash
  vaultspec-core spec skills status
  ```

- **Restore a default rule to its original snapshotted version**:

  ```bash
  vaultspec-core spec rules restore enforce-newline.builtin.md
  ```

______________________________________________________________________

### vaultspec-core spec system

```bash
vaultspec-core spec system [OPTIONS] COMMAND [ARGS]...
```

#### Subcommands

| Subcommand | Options | Description | | ---------- | ----------------------- |
-------------------------------------------------- | | `show` | - | Display system
prompt parts and generation targets | | `sync` | `[--dry-run] [--force]` |
Resource-scoped system prompt sync |

#### Examples

- **Display assembled system prompt configuration and composition**:

  ```bash
  vaultspec-core spec system show
  ```

- **Synchronize system prompts and stubs to AI provider workspaces**:

  ```bash
  vaultspec-core spec system sync
  ```

______________________________________________________________________

### vaultspec-core spec hooks

```bash
vaultspec-core spec hooks [OPTIONS] COMMAND [ARGS]...
```

#### Subcommands

| Subcommand | Signature | Description | | ---------- |
\-----------------------------------------------------------------------------------------------
|
\---------------------------------------------------------------------------------------------------------------------
| | `list` | - | List hooks with name, status, event, and action count | | `add` |
`[NAME] [--event EVENT] [--command CMD] [--body BODY] [--from-file FILE] [--force] [--dry-run]`
| Add a new custom hook definition. | | `show` | `NAME` | Display a hook's content. | |
`edit` | `NAME [--editor EDITOR]` | Open a hook in the configured editor. | | `rename` |
`OLD_NAME NEW_NAME` | Rename an existing hook atomically. | | `remove` |
`NAME [--yes\|--force]` | Delete a hook. | | `restore` | `FILENAME` | Restore a hook
(not supported for custom hooks, exits with error 1). | | `sync` |
`[--dry-run] [--force]` | Sync only hooks files. | | `status` | `[--json]` | Report
declarative hooks parsing and taxonomy compliance status. | | `run` |
`EVENT [--path PATH]` | Trigger enabled hooks for the given event. Valid events:
`vault.document.created`, `config.synced`, `audit.completed` |

#### Examples

- **Run all hooks registered for the document creation event**:

  ```bash
  vaultspec-core spec hooks run vault.document.created
  ```

- **List all registered hooks and their enabled/disabled status**:

  ```bash
  vaultspec-core spec hooks list
  ```

- **Add a new custom hook triggered on document creation**:

  ```bash
  vaultspec-core spec hooks add log-created --event vault.document.created --command "echo Created"
  ```

- **Display the definition and command block of a hook**:

  ```bash
  vaultspec-core spec hooks show log-created
  ```

- **Edit an existing hook definition using a configured editor**:

  ```bash
  vaultspec-core spec hooks edit log-created
  ```

- **Rename an existing hook atomically**:

  ```bash
  vaultspec-core spec hooks rename log-created document-logger
  ```

- **Remove/delete an obsolete hook**:

  ```bash
  vaultspec-core spec hooks remove document-logger --force
  ```

- **Check and report overall parsing and compliance status of hooks**:

  ```bash
  vaultspec-core spec hooks status
  ```

- **Synchronize local hook definitions**:

  ```bash
  vaultspec-core spec hooks sync
  ```

- **Restore a default hook to its original snapshotted version**:

  ```bash
  vaultspec-core spec hooks restore some-default-hook.json
  ```

______________________________________________________________________

### vaultspec-core spec mcps

```bash
vaultspec-core spec mcps [OPTIONS] COMMAND [ARGS]...
```

Manage MCP server definitions and the synced `.mcp.json` entries deployed for provider
clients. MCP sync updates `.mcp.json`; use top-level `vaultspec-core sync` for a
complete refresh across all provider-facing outputs.

#### Subcommands

| Subcommand | Signature | Description | | ---------- |
\--------------------------------------- |
-------------------------------------------------------------- | | `list` | - | List all
registered MCP server definitions | | `status` | `[--json]` | Validate MCP definitions
against `.mcp.json` | | `add` | `--name NAME [--config JSON] [--force]` | Add a new
custom MCP server definition | | `remove` | `NAME [--force]` | Remove an MCP server
definition (`--force` skips confirmation) | | `sync` | `[--dry-run] [--force]` | Sync
MCP definitions to `.mcp.json` |

`vaultspec-core spec mcps status` exits `0` only when MCP config status is `ok`,
otherwise `1`. It checks config health only and does not start or probe MCP server
processes.

#### Examples

- **Verify the health and synchronization status of MCP server definitions**:

  ```bash
  vaultspec-core spec mcps status
  ```

- **List all registered MCP server definitions**:

  ```bash
  vaultspec-core spec mcps list
  ```

- **Sync registered MCP definitions to deployment files**:

  ```bash
  vaultspec-core spec mcps sync
  ```

- **Register a new custom MCP server definition**:

  ```bash
  vaultspec-core spec mcps add --name sqlite-mcp --config "{\"command\": \"npx\", \"args\": [\"@modelcontextprotocol/server-sqlite\"]}"
  ```

- **Remove a registered MCP server definition**:

  ```bash
  vaultspec-core spec mcps remove sqlite-mcp --force
  ```

### vaultspec-core spec reference

```bash
vaultspec-core spec reference generate [OPTIONS]
```

Regenerate the generator-owned regions of the bundled machine-facing CLI reference
(`src/vaultspec_core/builtins/reference/cli.md`) from the live Typer command surface.
The reference is a hybrid of hand-written prose and generator-owned zones delimited by
`vaultspec:generated` HTML-comment markers; this verb rewrites only the managed zones
and leaves the prose untouched.

| Option | Default | Description | | --------- | ------- |
\---------------------------------------------------------------------------------------------
| | `--check` | off | Render in memory, diff against the committed file, exit non-zero
on mismatch without writing. | | `--json` | off | Emit machine-readable output. |

Default (write) mode rewrites the bundled reference in place when the managed regions
have drifted. `--check` mode is the CI and pre-commit entry point: it renders into
memory, prints a unified diff on mismatch, and exits non-zero, leaving the file
untouched (exit 0 when already in sync).

- **Refresh the bundled reference after a command or flag change**:

  ```bash
  vaultspec-core spec reference generate
  ```

- **Verify the bundled reference is up to date (CI gate)**:

  ```bash
  vaultspec-core spec reference generate --check
  ```

## Migration commands

Group command: `vaultspec-core migrations [OPTIONS] COMMAND [ARGS]...`

Every migration subcommand also accepts the global `--target / -t DIR` and `--json`
flags.

The migration registry runs every entry whose target version exceeds the workspace
manifest's `vaultspec_version`, then bumps the manifest version on success. Migrations
are idempotent and run lazily on every `vaultspec-core vault ...` command, on
`vaultspec-core install --upgrade`, or explicitly through
`vaultspec-core migrations run`.

### vaultspec-core migrations status

```bash
vaultspec-core migrations status [OPTIONS]
```

List registered migrations and which entries are pending against the current workspace
manifest. Read-only; never mutates.

#### Options

| Option | Short | Default | Description | | -------------- | ----- | ------- |
------------------------------------------------------- | | `--target DIR` | `-t` | cwd
| Inspect a workspace other than the current directory. | | `--json` | - | off | Emit
status, registered list, and pending list as JSON. |

Exit codes: `0` when up to date or workspace has no manifest, `1` when migrations are
pending.

#### Examples

- **List all registered schema migrations and check for pending entries**:

  ```bash
  vaultspec-core migrations status
  ```

______________________________________________________________________

### vaultspec-core migrations run

```bash
vaultspec-core migrations run [OPTIONS]
```

Apply every pending migration in version order and bump the manifest's
`vaultspec_version`. A migration that fails stops the run and leaves the manifest
unchanged so the next invocation re-attempts it.

#### Options

| Option | Short | Default | Description | | -------------- | ----- | ------- |
----------------------------------------------------- | | `--target DIR` | `-t` | cwd |
Migrate a workspace other than the current directory. | | `--json` | - | off | Emit
per-entry summaries and counts as JSON. |

Exit codes: `0` on success (including the no-pending no-op), `1` if any migration
failed.

#### Examples

- **Execute all pending schema migrations and upgrade the workspace**:

  ```bash
  vaultspec-core migrations run
  ```

______________________________________________________________________

## Config commands

Group command: `vaultspec-core config [OPTIONS] COMMAND [ARGS]...`

Manage local project configuration settings stored in `.vaultspec/config.toml` at the
workspace root.

Every config subcommand also accepts the global `--target / -t DIR` and `--json` flags.

### vaultspec-core config get

```bash
vaultspec-core config get [OPTIONS] KEY
```

Read a local configuration value.

#### Examples

- **Retrieve the local project-level editor setting**:

  ```bash
  vaultspec-core config get editor
  ```

### vaultspec-core config set

```bash
vaultspec-core config set [OPTIONS] KEY VALUE
```

Write a local configuration value. Supported keys: `editor`.

#### Examples

- **Configure the local project-level editor command to Zed**:

  ```bash
  vaultspec-core config set editor zed
  ```

### vaultspec-core config unset

```bash
vaultspec-core config unset [OPTIONS] KEY
```

Clear a local configuration entry.

#### Examples

- **Clear the local project-level editor configuration**:

  ```bash
  vaultspec-core config unset editor
  ```

### vaultspec-core config list

```bash
vaultspec-core config list [OPTIONS]
```

Enumerate all known configuration entries and current values.

#### Examples

- **Enumerate all local project-level configuration settings and values**:

  ```bash
  vaultspec-core config list
  ```

______________________________________________________________________

## Environment variables

All variables are prefixed `VAULTSPEC_`. Environment variables override defaults but are
overridden by the `--target` flag.

| Variable | Type | Default | Description | | --------------------------------- | ---- |
\------------ |
\---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
| | `VAULTSPEC_TARGET_DIR` | path | cwd | Root workspace directory (where `.vault/` and
`.vaultspec/` live). Equivalent to `--target` on the CLI. Also used by `vaultspec-mcp`
to locate the workspace. Defaults to the current working directory if unset. | |
`VAULTSPEC_DOCS_DIR` | str | `.vault` | Vault directory name | |
`VAULTSPEC_FRAMEWORK_DIR` | str | `.vaultspec` | Framework directory name | |
`VAULTSPEC_CLAUDE_DIR` | str | `.claude` | Claude tool directory name | |
`VAULTSPEC_GEMINI_DIR` | str | `.gemini` | Gemini tool directory name | |
`VAULTSPEC_ANTIGRAVITY_DIR` | str | `.agents` | Antigravity directory name | |
`VAULTSPEC_IO_BUFFER_SIZE` | int | `8192` | I/O read buffer size in bytes | |
`VAULTSPEC_TERMINAL_OUTPUT_LIMIT` | int | `1000000` | Subprocess stdout capture limit in
bytes | | `VAULTSPEC_LOG_LEVEL` | str | `INFO` | Root log level for the CLI, for example
`DEBUG`, `INFO`, or `WARNING`. Overridden by `--debug` when set. | | `VAULTSPEC_EDITOR`
| str | `zed -w` | Editor command for
`vaultspec-core spec {rules\|skills\|agents} edit`. Overridden by the project-local
config `editor` value, and the `--editor` flag. Resolved in order: `--editor` flag,
project config, `$VISUAL`, `$EDITOR`/`VAULTSPEC_EDITOR`, `vi`. |

## See also

| Document | What it covers | | ---------------------------------- |
----------------------------------------------- | | [Framework manual](./framework.md) |
Development workflow, skills, and customization | | [MCP reference](./MCP.md) | MCP
server tools, setup, and configuration |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/wgergely/vaultspec-core/issues).
