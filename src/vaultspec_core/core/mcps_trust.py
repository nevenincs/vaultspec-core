"""Host-local consent for exact workspace MCP definitions and rendered launches.

Ownership records are not approval. Every stdio definition, including files
named ``.builtin.json``, needs a grant before sync can enroll or refresh it.
The grant binds the parsed file snapshot and normalized provider configuration;
neither a later read nor a workspace's ownership metadata can widen consent.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .helpers import atomic_write
from .home import core_home_layout
from .mcps_ownership import target_lock

if TYPE_CHECKING:
    from .types import McpTarget, SyncResult

__all__ = ["McpApproval", "approved_sources", "grant", "revoke", "trust_file_path"]


def _local_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


@dataclass(frozen=True)
class McpApproval:
    """Immutable identity of the definition and launch shown for approval."""

    workspace: str
    source: str
    provider: str
    scope: str
    target: str
    name: str
    definition_digest: str
    launch: str

    @classmethod
    def capture(
        cls,
        root: Path,
        target: McpTarget,
        name: str,
        path: Path,
        config: dict[str, Any],
        digest: str,
    ) -> McpApproval:
        """Bind consent to normalized launch semantics, without rereading input."""
        launch = json.dumps(
            {
                "command": config["command"],
                "args": config.get("args", []),
                "env": config.get("env", {}),
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return cls(
            _local_path(root),
            _local_path(path),
            target.provider.value,
            target.scope.value,
            _local_path(target.path),
            name,
            digest,
            launch,
        )

    @property
    def key(self) -> str:
        """Stable host-local identity, independent of executable contents."""
        return json.dumps(
            [
                self.workspace,
                self.source,
                self.provider,
                self.scope,
                self.target,
                self.name,
            ]
        )

    @property
    def digest(self) -> str:
        """Pin both definition bytes and the actual rendered executable content."""
        content = json.dumps([self.definition_digest, self.launch]).encode("utf-8")
        return "sha256:" + hashlib.sha256(content).hexdigest()


def trust_file_path(home: Path | None = None) -> Path:
    """Resolve the ledger outside the repository, under the operator's home."""
    return core_home_layout(home).root / "mcp-trust.json"


def _read(home: Path | None) -> dict[str, str]:
    try:
        raw: object = json.loads(trust_file_path(home).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    document = cast("dict[str, object]", raw)
    if type(document.get("version")) is not int or document["version"] != 1:
        return {}
    grants = document.get("grants")
    if not isinstance(grants, dict):
        return {}
    return {
        key: value
        for key, value in cast("dict[str, object]", grants).items()
        if isinstance(value, str)
    }


def _write(grants: dict[str, str], home: Path | None) -> Path:
    path = trust_file_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps({"version": 1, "grants": grants}, indent=2) + "\n")
    return path


def grant(approvals: list[McpApproval], home: Path | None = None) -> Path:
    """Persist only the snapshots explicitly reviewed by the CLI operator."""
    with target_lock(trust_file_path(home), dry_run=False):
        grants = _read(home)
        grants.update({approval.key: approval.digest for approval in approvals})
        return _write(grants, home)


def revoke(root: Path, home: Path | None = None) -> int:
    """Withdraw this workspace's grants; existing native entries are untouched."""
    with target_lock(trust_file_path(home), dry_run=False):
        grants = _read(home)
        prefix = json.dumps([_local_path(root)])[:-1] + ","
        kept = {
            key: value for key, value in grants.items() if not key.startswith(prefix)
        }
        removed = len(grants) - len(kept)
        if removed:
            _write(kept, home)
        return removed


def approved_sources(
    sources: dict[str, tuple[Path, dict[str, Any]]],
    digests: dict[Path, str],
    root: Path,
    target: McpTarget,
    result: SyncResult,
    home: Path | None = None,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Fail closed before any add, adoption, or refresh reaches native config."""
    grants = _read(home)
    approved: dict[str, tuple[Path, dict[str, Any]]] = {}
    for name, (path, config) in sources.items():
        digest = digests.get(path)
        if digest is not None:
            approval = McpApproval.capture(root, target, name, path, config, digest)
            if grants.get(approval.key) == approval.digest:
                approved[name] = (path, config)
                continue
        result.skipped += 1
        result.items.append((name, "[SKIP]"))
        result.warnings.append(
            f"MCP server '{name}' is not approved for {target.provider.value} "
            f"({target.scope.value}); review it at a terminal with "
            f"vaultspec-core spec mcps trust {target.provider.value} "
            f"--scope {target.scope.value}, then sync again. "
            "--force does not grant executable consent."
            " For top-level sync --target with CWD sources, approve with "
            "--source-from-cwd and the same --target."
        )
    return approved
