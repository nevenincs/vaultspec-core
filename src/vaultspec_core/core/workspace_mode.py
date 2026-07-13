"""Read and write the committed workspace mode declaration.

Vaultspec-core is development-harness tooling, not a runtime dependency of the
projects it governs, so the choice between tool mode and dependency mode is a
decision the whole team must share. This module owns the committed
``.vaultspec/workspace.json`` declaration that records that choice, distinct
from the gitignored per-machine ``providers.json`` manifest: the declaration is
the source of truth every contributor and a fresh clone read, while the
manifest only echoes the locally resolved value for bookkeeping.

Reads are lenient about a missing file (there is simply no persisted choice
yet) and strict about a present but broken one: corrupt JSON or an
out-of-vocabulary mode raises a typed
:class:`~vaultspec_core.core.exceptions.VaultSpecError` rather than silently
falling back, because a silent fallback on an explicit-but-wrong declaration is
exactly the opaque-failure-later pattern the ``install-mode`` decision exists to
close. Writes are canonical and deterministic (sorted keys, two-space indent,
trailing newline, UTF-8) so the committed file diffs cleanly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .enums import InstallMode
from .exceptions import VaultSpecError
from .helpers import advisory_lock, atomic_write

WORKSPACE_FILENAME = "workspace.json"
WORKSPACE_SCHEMA_VERSION = "1.0"


@dataclass
class WorkspaceDeclaration:
    """The committed shared declaration of a workspace's provisioning mode.

    Attributes:
        install_mode: The resolved provisioning mode the whole team shares.
        minimum_vaultspec_version: Optional floor constraint; when set, an
            invocation whose running package version is below it is refused at
            invocation start per the ``install-mode`` version-skew handshake.
            ``None`` when the workspace declares no floor.
        schema_version: The declaration schema version string, forced to
            :data:`WORKSPACE_SCHEMA_VERSION` on write.
    """

    install_mode: InstallMode
    minimum_vaultspec_version: str | None = None
    schema_version: str = WORKSPACE_SCHEMA_VERSION


def _workspace_path(target: Path) -> Path:
    return target / ".vaultspec" / WORKSPACE_FILENAME


def read_workspace_declaration(target: Path) -> WorkspaceDeclaration | None:
    """Read the committed ``.vaultspec/workspace.json`` declaration.

    A missing file is lenient: it means no mode has been declared yet, so the
    precedence chain that resolves an effective mode can fall through to
    detection and the default. A present but broken file is strict: corrupt
    JSON or an unrecognized ``install_mode`` value raises rather than pretending
    no declaration exists, so an explicit but malformed choice never silently
    resolves to the default.

    Args:
        target: Workspace root directory.

    Returns:
        The parsed :class:`WorkspaceDeclaration`, or ``None`` when the file is
        absent.

    Raises:
        VaultSpecError: If the file exists but contains invalid JSON, is
            unreadable, or names an ``install_mode`` outside the canonical
            :class:`~vaultspec_core.core.enums.InstallMode` vocabulary.
    """
    path = _workspace_path(target)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise VaultSpecError(
            f"Corrupt workspace declaration at {path}: {e}",
            hint="Fix the JSON by hand or re-run 'vaultspec-core install --mode'.",
        ) from e

    if not isinstance(raw, dict):
        raise VaultSpecError(
            f"Malformed workspace declaration at {path}: expected a JSON object.",
            hint="Fix the JSON by hand or re-run 'vaultspec-core install --mode'.",
        )

    mode = InstallMode.from_token(raw.get("install_mode"))
    if mode is None:
        raise VaultSpecError(
            f"Invalid install_mode in workspace declaration at {path}: "
            f"{raw.get('install_mode')!r}.",
            hint="Set install_mode to 'tool' or 'dependency', "
            "or re-run 'vaultspec-core install --mode'.",
        )

    floor = raw.get("minimum_vaultspec_version")
    minimum = str(floor) if floor is not None else None

    return WorkspaceDeclaration(
        install_mode=mode,
        minimum_vaultspec_version=minimum,
        schema_version=str(raw.get("schema_version", WORKSPACE_SCHEMA_VERSION)),
    )


def write_workspace_declaration(
    target: Path, declaration: WorkspaceDeclaration
) -> None:
    """Serialize *declaration* to ``.vaultspec/workspace.json``.

    Forces :attr:`WorkspaceDeclaration.schema_version` to the current
    :data:`WORKSPACE_SCHEMA_VERSION` and writes canonically: sorted keys,
    two-space indent, and a trailing newline. The optional floor field is
    omitted entirely when unset so the committed file stays minimal. Wraps the
    read-modify-write cycle in an advisory lock so concurrent writers do not
    clobber each other.

    Args:
        target: Workspace root directory.
        declaration: :class:`WorkspaceDeclaration` instance to persist.
    """
    path = _workspace_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "install_mode": InstallMode(declaration.install_mode).value,
    }
    if declaration.minimum_vaultspec_version is not None:
        payload["minimum_vaultspec_version"] = declaration.minimum_vaultspec_version
    with advisory_lock(path):
        atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
