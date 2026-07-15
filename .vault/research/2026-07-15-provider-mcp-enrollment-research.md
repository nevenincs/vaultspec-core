---
tags:
  - '#research'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-04-11-mcp-registry-adr]]"
  - "[[2026-03-28-mcp-installation-patterns-research]]"
---

# `provider-mcp-enrollment` research: provider-native MCP enrollment scopes and ownership

The MCP registry has one canonical desired-state source but its deployed state is not
provider-agnostic. Claude Code consumes project MCPs from `.mcp.json`; Codex consumes
them from trusted `.codex/config.toml`. The current shared-JSON assumption therefore
produces a false-green Codex status. Current host contracts favor typed native targets,
project scope as Vaultspec's safe default, explicit authorization for user or local
scope, and ownership state outside host schemas.

## Findings

### Codex has project and user configuration layers, not a shared JSON registry

Codex stores MCP tables as `[mcp_servers.<name>]` in `config.toml`. Its user layer is
`$CODEX_HOME/config.toml`, defaulting to `~/.codex/config.toml`; a trusted repository
may override it with `.codex/config.toml`. The installed `codex-cli@0.144.4` exposes
`mcp add`, `get`, `list`, and `remove`, but no scope flag: `mcp add` is a user-config
writer while project enrollment is a direct project-config operation. Official Codex
configuration precedence places trusted project layers above user configuration.

### Claude has three scopes with two physical configuration stores

Claude Code `2.1.210` exposes `--scope local|user|project`, defaulting its own add
command to local. Project scope is shared through the workspace `.mcp.json`. Local and
user scope both live in `~/.claude.json`; local entries are nested under the current
project path while user entries apply across projects. Project MCPs remain subject to
workspace trust and per-server approval. Vaultspec's existing project `.mcp.json`
output is therefore the correct Claude project target and must be preserved.

### Vaultspec needs a stricter default than each host CLI

An explicit workspace install already authorizes project-local scaffolding, matching
the conclusion in `2026-03-28-mcp-installation-patterns-research`. It does not authorize
writes to a user's cross-project configuration. Project must remain the default for
install, sync, status, prune, and uninstall. Claude local and both hosts' user scope
require an explicit scope option. Codex has no distinct local scope, so that matrix
cell must fail rather than silently aliasing project or user scope.

| Provider | Scope   | Native target                              | Vaultspec policy |
| -------- | ------- | ------------------------------------------ | ---------------- |
| Claude   | project | workspace `.mcp.json`                      | default          |
| Claude   | local   | user `.claude.json`, current-project entry | explicit only    |
| Claude   | user    | user `.claude.json`, cross-project entry   | explicit only    |
| Codex    | project | trusted workspace `.codex/config.toml`     | default          |
| Codex    | user    | `$CODEX_HOME/config.toml`                  | explicit only    |
| Codex    | local   | unsupported                                | reject           |

### Ownership metadata must not enter host schemas

The current JSON merger writes `_vaultspecManaged` beside `mcpServers`. That key is
Vaultspec state, not Claude's MCP schema, and cannot be translated into Codex TOML as a
configuration key. Project ownership can live in a Vaultspec sidecar under
`.vaultspec/`; explicitly requested user-scope ownership can live in user Vaultspec
state. A Codex comment-delimited managed block additionally gives byte-preserving
round-trip control without creating an interpreted key. Ownership records need only
provider, scope, target identity, managed names, and observed fingerprints; desired
configuration remains exclusively in `.vaultspec/mcps/*.json`.

### Migration must prove ownership instead of inferring it from a name

Legacy `_vaultspecManaged` is affirmative ownership evidence and can migrate to the
sidecar before the invalid host key is removed. A same-name host entry without that
evidence is user-owned, even when it currently equals a source definition. Default sync
must preserve and report it; explicit force may adopt it. This is stricter than the
current name-intersection migration and is necessary for safe uninstall and pruning.

### One normalized definition can render to both native schemas

The built-in Core and RAG definitions are stdio launches using `command`, `args`, and
optional environment values. These fields translate directly to Claude JSON and Codex
TOML while retaining Core's dependency/dev `uv run` and tool `uvx --from` rendering.
Provider adapters should reject or report unsupported provider-specific fields rather
than copying arbitrary JSON into every host. The normalized definition and target types
belong above the JSON/TOML writers so companion packages call one public reconcile seam.

Package mode identity and the tool-mode distribution requirement can differ. RAG owns
mode state under package `vaultspec-rag`, but its MCP server dependencies are supplied
by the optional `mcp` extra. Canonical definition metadata therefore needs a distinct
optional tool distribution spec that renders only the `uvx --from` operand. Dependency
and dev mode continue to resolve the module through the workspace's `uv run` environment.

### Real host CLIs are the compatibility oracle

Parser-only tests can reproduce the original false green. Isolated acceptance must run
`claude mcp get/list` against project `.mcp.json` and `codex mcp get/list --json`
against trusted project `.codex/config.toml`. User-scope acceptance must redirect host
configuration homes to temporary directories so tests never mutate operator state.

## Sources

- https://developers.openai.com/codex/mcp/
- https://developers.openai.com/codex/config-basic/
- https://developers.openai.com/codex/config-advanced/
- https://code.claude.com/docs/en/mcp
- `codex-cli@0.144.4`
- `claude-code@2.1.210`
- `src/vaultspec_core/core/mcps.py:561`
- `src/vaultspec_core/core/mcps.py:55`
- `src/vaultspec_core/core/mcps.py:794`
- `src/vaultspec_core/core/types.py:31`
- `src/vaultspec_core/core/config_gen.py:329`
- `src/vaultspec_core/core/commands.py:981`
