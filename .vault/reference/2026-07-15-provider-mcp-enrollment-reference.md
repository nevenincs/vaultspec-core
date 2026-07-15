---
tags:
  - '#reference'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-04-11-mcp-registry-adr]]"
---

# `provider-mcp-enrollment` reference: Core MCP registry and native host configuration surfaces

This reference maps the current registry, install, status, configuration, and uninstall
paths and defines the public boundary needed by companion packages. The audit covers
the Core source, its real-behavior MCP tests, official Codex and Claude contracts, and
the installed host CLIs.

## Summary

### Existing source and rendering flow

`collect_mcp_servers` reads canonical JSON definitions and applies the package-aware
mode renderer. `_apply_mcp_merge` and `_sync_mcp_target` then assume every destination
is JSON with `mcpServers` and `_vaultspecManaged`. `mcp_sync` always targets root
`.mcp.json` and adds provider-native JSON targets declared through `ToolConfig`.
`mcp_status` inspects only root `.mcp.json`. `mcp_uninstall` repeats the JSON assumption.

Fresh install calls `mcp_sync` before provider names are persisted to the manifest, so
native target discovery through `installed_tool_configs` cannot see newly selected
providers. Ordinary sync runs configuration before MCP reconciliation and can share a
Codex TOML file safely only if MCP writes use their own managed block and one lock/write
transaction. Provider-specific `spec mcps sync` currently validates the provider but
does not pass it into `mcp_sync`.

### Reusable Core seams

`render_launch_for_mode` and `_render_definition_for_sync` already provide the correct
package-mode behavior and should remain the single launch authority. They must accept an
optional tool distribution spec independently of the declaring package: package remains
the workspace-mode lookup identity, while tool mode renders `uvx --from <tool-spec>`.
The metadata key `_vaultspec_mode_tool_spec` is stripped with the existing package and
module metadata before any host output. The tag engine's
comment-prefixed managed block supports byte-preserving Codex TOML ownership. The
provider manifest supplies enrolled providers, but persistent MCP ownership is a
separate concern and needs a dedicated sidecar because it is per provider, scope, and
target.

### Proposed stable public API

The implementation should export these typed contracts from `vaultspec_core.core`:

```python
class McpScope(StrEnum):
    PROJECT = "project"
    LOCAL = "local"
    USER = "user"

@dataclass(frozen=True)
class McpTarget:
    provider: Tool
    scope: McpScope
    path: Path
    format: McpTargetFormat

def resolve_mcp_targets(
    provider: Tool | str = "all",
    *,
    scope: McpScope = McpScope.PROJECT,
    target_dir: Path | None = None,
) -> tuple[McpTarget, ...]: ...

def mcp_sync(
    *,
    provider: Tool | str = "all",
    scope: McpScope = McpScope.PROJECT,
    dry_run: bool = False,
    force: bool = False,
    prune: bool = False,
    mode: InstallMode | None = None,
    force_managed: frozenset[str] = frozenset(),
) -> SyncResult: ...

def mcp_status(
    *,
    provider: Tool | str = "all",
    scope: McpScope = McpScope.PROJECT,
) -> dict[str, object]: ...

def mcp_uninstall(
    target_dir: Path,
    *,
    provider: Tool | str = "all",
    scope: McpScope = McpScope.PROJECT,
    dry_run: bool = False,
) -> SyncResult: ...
```

`mcp_sync` remains the provider-agnostic companion reconcile seam: RAG enrolls one
canonical definition, records its package mode through existing workspace declaration
logic, and invokes this public function with `force_managed={"vaultspec-rag"}` when a
mode transition must update already-owned entries. It must never call adapter-private
JSON or TOML functions. Its canonical definition keeps
`_vaultspec_mode_package: "vaultspec-rag"` and adds
`_vaultspec_mode_tool_spec: "vaultspec-rag[mcp]"`; dependency/dev render `uv run`, while
tool mode renders `uvx --from vaultspec-rag[mcp]`.

`SyncResult.per_tool` remains the result carrier for each provider. MCP status JSON must
add `scope` and a `providers` map; every provider entry reports `target`, `format`,
`configured`, `managed`, `external`, `missing`, `drifted`, `stale_managed`, and
`warnings`. Aggregate status is green only when every selected enrolled provider's
native target is synchronized.

### Migration and lifecycle insertion points

The JSON adapter migrates `_vaultspecManaged` to the sidecar under the same advisory
lock before deleting the legacy key. Without legacy ownership, name equality never
authorizes adoption. The TOML adapter owns only its comment-delimited MCP block and
must detect same-name tables outside it. Force can adopt a conflicting entry by removing
that complete table and rendering it in the managed block; default sync preserves it.

Install must supply the freshly selected provider set directly or persist the manifest
before MCP reconciliation. Upgrade passes resolved mode and the narrow
`force_managed` set. Provider sync passes its provider argument. Provider uninstall
removes only that provider/scope target; full uninstall defaults to all installed
project targets. User/local targets are touched only by an explicit scope request.

### Verification epicenters

- `src/vaultspec_core/core/mcps.py`
- `src/vaultspec_core/core/types.py`
- `src/vaultspec_core/core/enums.py`
- `src/vaultspec_core/core/config_gen.py`
- `src/vaultspec_core/core/commands.py`
- `src/vaultspec_core/core/manifest.py`
- `src/vaultspec_core/cli/spec_cmd.py`
- `tests/test_mcps.py`
- `tests/test_commands.py`
