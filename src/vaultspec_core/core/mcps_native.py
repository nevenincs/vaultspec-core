"""Low-level native MCP configuration parsing/rendering shared by status, sync,
and uninstall.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .enums import McpScope, Tool
from .exceptions import VaultSpecError
from .helpers import atomic_write, ensure_dir
from .tags import find_blocks

if TYPE_CHECKING:
    from .types import McpTarget, SyncResult

LEGACY_MANAGED_KEY = "_vaultspecManaged"
TOML_BLOCK_TYPE = "mcps"
_STDIO_FIELDS = frozenset({"command", "args", "env"})

__all__ = [
    "LEGACY_MANAGED_KEY",
    "TOML_BLOCK_TYPE",
    "json_server_map",
    "managed_toml_content",
    "normalized_sources",
    "render_codex_servers",
    "strip_external_codex_server",
    "toml_servers",
    "write_json_target",
]


def normalized_sources(
    sources: dict[str, tuple[Path, dict[str, Any]]],
    target: McpTarget,
    result: SyncResult,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Validate canonical stdio definitions before a provider adapter sees them."""
    normalized: dict[str, tuple[Path, dict[str, Any]]] = {}
    for name, (path, config) in sources.items():
        unsupported = sorted(set(config) - _STDIO_FIELDS)
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})
        if unsupported:
            result.warnings.append(
                f"MCP server '{name}' has fields unsupported by "
                f"{target.provider.value}: {unsupported}; skipping this target."
            )
            continue
        if not isinstance(command, str):
            result.warnings.append(
                f"MCP server '{name}' has a non-string command; skipping "
                f"{target.provider.value}."
            )
            continue
        if not isinstance(args, list):
            result.warnings.append(
                f"MCP server '{name}' has non-string args; skipping "
                f"{target.provider.value}."
            )
            continue
        args = cast("list[Any]", args)
        if not all(isinstance(item, str) for item in args):
            result.warnings.append(
                f"MCP server '{name}' has non-string args; skipping "
                f"{target.provider.value}."
            )
            continue
        if not isinstance(env, dict):
            result.warnings.append(
                f"MCP server '{name}' has a non-string environment map; skipping "
                f"{target.provider.value}."
            )
            continue
        env = cast("dict[Any, Any]", env)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env.items()
        ):
            result.warnings.append(
                f"MCP server '{name}' has a non-string environment map; skipping "
                f"{target.provider.value}."
            )
            continue
        definition: dict[str, Any] = {"command": command}
        if "args" in config:
            definition["args"] = list(args)
        if "env" in config:
            definition["env"] = dict(env)
        normalized[name] = (path, definition)
    return normalized


def json_server_map(
    raw: dict[str, Any], target: McpTarget, root: Path
) -> dict[str, Any]:
    """Return the native JSON server map for a Claude/Antigravity target."""
    container = raw
    if target.provider is Tool.CLAUDE and target.scope is McpScope.LOCAL:
        projects = raw.setdefault("projects", {})
        if not isinstance(projects, dict):
            raise VaultSpecError(
                "Claude configuration field 'projects' is not an object."
            )
        projects = cast("dict[str, Any]", projects)
        project = projects.setdefault(root.resolve().as_posix(), {})
        if not isinstance(project, dict):
            raise VaultSpecError("Claude local project configuration is not an object.")
        container = cast("dict[str, Any]", project)
    servers = container.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise VaultSpecError(f"MCP server map in {target.path} is not an object.")
    return cast("dict[str, Any]", servers)


def _drop_empty_json_server_map(
    raw: dict[str, Any], target: McpTarget, root: Path
) -> None:
    """Remove empty native containers while retaining unrelated host settings."""
    if target.provider is Tool.CLAUDE and target.scope is McpScope.LOCAL:
        projects = raw.get("projects")
        if not isinstance(projects, dict):
            return
        projects = cast("dict[str, Any]", projects)
        project_key = root.resolve().as_posix()
        project = projects.get(project_key)
        if isinstance(project, dict):
            project = cast("dict[str, Any]", project)
            if not project.get("mcpServers"):
                project.pop("mcpServers", None)
                if not project:
                    projects.pop(project_key, None)
        if not projects:
            raw.pop("projects", None)
        return
    if not raw.get("mcpServers"):
        raw.pop("mcpServers", None)


def write_json_target(
    path: Path, raw: dict[str, Any], target: McpTarget, root: Path
) -> None:
    _drop_empty_json_server_map(raw, target, root)
    if raw:
        ensure_dir(path.parent)
        atomic_write(path, json.dumps(raw, indent=2) + "\n")
    elif path.exists():
        path.unlink()


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return repr(value)
    if isinstance(value, list):
        items = cast("list[Any]", value)
        return "[" + ", ".join(_toml_value(item) for item in items) + "]"
    if isinstance(value, dict):
        mapping = cast("dict[Any, Any]", value)
        pairs = (
            f"{json.dumps(str(key))} = {_toml_value(item)}"
            for key, item in sorted(mapping.items())
        )
        return "{ " + ", ".join(pairs) + " }"
    raise VaultSpecError(
        f"Codex MCP configuration contains unsupported value: {value!r}"
    )


def render_codex_servers(servers: dict[str, dict[str, Any]]) -> str:
    sections: list[str] = []
    for name, config in sorted(servers.items()):
        lines = [f"[mcp_servers.{json.dumps(name, ensure_ascii=False)}]"]
        lines.extend(
            f"{key} = {_toml_value(value)}" for key, value in sorted(config.items())
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def toml_servers(content: str) -> dict[str, dict[str, Any]]:
    if not content.strip():
        return {}
    parsed = tomllib.loads(content)
    raw = parsed.get("mcp_servers", {})
    if not isinstance(raw, dict):
        raise VaultSpecError("Codex 'mcp_servers' field is not a table.")
    raw = cast("dict[str, Any]", raw)
    servers: dict[str, dict[str, Any]] = {}
    for name, config in raw.items():
        if not isinstance(config, dict):
            raise VaultSpecError(f"Codex MCP server '{name}' is not a table.")
        servers[str(name)] = dict(cast("dict[str, Any]", config))
    return servers


def managed_toml_content(content: str) -> str:
    for block in find_blocks(content):
        if block.block_type == TOML_BLOCK_TYPE:
            lines = content.splitlines()
            return "\n".join(lines[block.content_start - 1 : block.content_end])
    return ""


_TOML_TABLE_RE = re.compile(r"^\s*\[(?!\[)(?P<header>.+)]\s*(?:#.*)?$")


def _toml_header_path(header: str) -> tuple[str, ...] | None:
    """Parse one TOML table header into its semantic key path."""
    try:
        parsed = tomllib.loads(f"[{header}]\n_vaultspec_probe = true\n")
    except tomllib.TOMLDecodeError:
        return None
    path: list[str] = []
    current: Any = parsed
    while isinstance(current, dict) and "_vaultspec_probe" not in current:
        current = cast("dict[Any, Any]", current)
        if len(current) != 1:
            return None
        key, current = next(iter(current.items()))
        path.append(str(key))
    return tuple(path) if isinstance(current, dict) else None


def strip_external_codex_server(content: str, name: str) -> str:
    """Remove one external Codex server's table sections without reformatting."""
    kept: list[str] = []
    removing = False
    for line in content.splitlines():
        match = _TOML_TABLE_RE.match(line)
        if match:
            path = _toml_header_path(match.group("header"))
            removing = bool(
                path and len(path) >= 2 and path[0] == "mcp_servers" and path[1] == name
            )
        if not removing:
            kept.append(line)
    rendered = "\n".join(kept)
    if rendered and content.endswith("\n"):
        rendered += "\n"
    return rendered
