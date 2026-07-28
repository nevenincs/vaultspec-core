"""Persist and query which native MCP entries vaultspec owns.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.

Ownership is recorded outside host schemas (``.vaultspec/mcp-ownership.json``)
so unrelated entries in a provider's native configuration remain untouched. A
name is recorded alongside a content fingerprint, which is what lets
:func:`~vaultspec_core.core.mcps_sync.mcp_sync` distinguish an entry that
merely drifted from vaultspec's own last write (safe to refresh without
``--force``) from a hand-edited or unverifiable entry (still requires
``--force``).
"""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .enums import McpScope
from .exceptions import VaultSpecError
from .helpers import advisory_lock, atomic_write, ensure_dir

if TYPE_CHECKING:
    from .types import McpTarget

_OWNERSHIP_VERSION = 1
_OWNERSHIP_FILENAME = "mcp-ownership.json"


def _ownership_path(root: Path, scope: McpScope) -> Path:
    if scope in {McpScope.PROJECT, McpScope.LOCAL}:
        return root / ".vaultspec" / _OWNERSHIP_FILENAME
    return Path.home() / ".vaultspec" / _OWNERSHIP_FILENAME


def _ownership_target_key(target: McpTarget) -> str:
    base = f"{target.provider.value}:{target.scope.value}"
    if target.scope is McpScope.USER:
        return f"{base}:{target.path.resolve()}"
    return base


def _read_ownership(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": _OWNERSHIP_VERSION, "targets": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise VaultSpecError(
            f"Cannot read MCP ownership state at {path}: {exc}",
            hint="Repair or remove the corrupt sidecar before reconciling MCPs.",
        ) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("targets"), dict):
        raise VaultSpecError(
            f"Invalid MCP ownership state at {path}.",
            hint="Expected an object with a 'targets' object.",
        )
    version = raw.get("version")
    if version != _OWNERSHIP_VERSION:
        raise VaultSpecError(f"Unsupported MCP ownership version at {path}: {version}")
    return raw


def _write_ownership(path: Path, state: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    atomic_write(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


def _target_lock(path: Path, *, dry_run: bool) -> Any:
    """Return a no-op context for previews and a real advisory lock for writes."""
    return nullcontext() if dry_run else advisory_lock(path)


def _fingerprint(config: dict[str, Any]) -> str:
    """Return the stable observed-content fingerprint stored in ownership state."""
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _owned_names(state: dict[str, Any], target: McpTarget) -> set[str]:
    raw = state["targets"].get(_ownership_target_key(target), {})
    managed = raw.get("managed", {}) if isinstance(raw, dict) else {}
    if isinstance(managed, dict):
        return {str(name) for name in managed}
    return set()


def _owned_fingerprints(state: dict[str, Any], target: McpTarget) -> dict[str, str]:
    """Return the recorded name-to-fingerprint map for one target's managed entries.

    A name present here with a matching current fingerprint proves the deployed
    entry is byte-identical to what vaultspec last wrote, so it is safe to
    refresh to the current canonical shape without ``--force``. A name absent
    from this map (legacy name-only ownership record) cannot be verified and
    keeps the existing skip-and-warn behavior.
    """
    raw = state["targets"].get(_ownership_target_key(target), {})
    managed = raw.get("managed", {}) if isinstance(raw, dict) else {}
    if isinstance(managed, dict):
        return {
            str(name): value
            for name, value in managed.items()
            if isinstance(value, str)
        }
    return {}


def _launch_repr(config: dict[str, Any]) -> str:
    """Return a human-readable one-line rendering of a server's launch command."""
    command = str(config.get("command", ""))
    args = config.get("args", [])
    parts = (
        [command, *(str(item) for item in args)]
        if isinstance(args, list)
        else [command]
    )
    return " ".join(part for part in parts if part)


def _set_owned_names(
    state: dict[str, Any], target: McpTarget, servers: dict[str, dict[str, Any]]
) -> None:
    key = _ownership_target_key(target)
    if not servers:
        state["targets"].pop(key, None)
        return
    state["targets"][key] = {
        "provider": target.provider.value,
        "scope": target.scope.value,
        "path": str(target.path.resolve()),
        "managed": {
            name: _fingerprint(config) for name, config in sorted(servers.items())
        },
    }


def _discard_owned_names(
    state: dict[str, Any], target: McpTarget, names: set[str]
) -> None:
    key = _ownership_target_key(target)
    record = state["targets"].get(key)
    if not isinstance(record, dict):
        return
    managed = record.get("managed")
    if not isinstance(managed, dict):
        state["targets"].pop(key, None)
        return
    for name in names:
        managed.pop(name, None)
    if not managed:
        state["targets"].pop(key, None)
