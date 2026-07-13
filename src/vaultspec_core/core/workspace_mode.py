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
import re
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .enums import InstallMode
from .exceptions import VaultSpecError
from .helpers import advisory_lock, atomic_write

WORKSPACE_FILENAME = "workspace.json"
WORKSPACE_SCHEMA_VERSION = "1.0"

#: Distribution name detection keys on; canonicalized per PEP 503 so that
#: ``vaultspec_core`` and ``vaultspec-core`` compare equal.
_DISTRIBUTION_NAME = "vaultspec-core"

#: Split a PEP 508 requirement string at the first character that terminates
#: the distribution name (version specifier, extras, marker, or whitespace).
_REQUIREMENT_NAME_BOUNDARY = re.compile(r"[<>=!~;\[\s(]")


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


def _canonical_distribution_name(name: str) -> str:
    """Canonicalize a distribution name for comparison per PEP 503.

    Lowercases and collapses any run of ``-``, ``_``, or ``.`` to a single
    ``-`` so that spellings such as ``vaultspec_core`` and ``VaultSpec-Core``
    all compare equal to :data:`_DISTRIBUTION_NAME`.

    Args:
        name: Raw distribution name token.

    Returns:
        The normalized name.
    """
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _requirement_names(entries: Iterable[Any]) -> Iterator[str]:
    """Yield the canonical distribution name of each PEP 508 requirement.

    Non-string entries (for example the ``{include-group = ...}`` tables a
    :pep:`735` dependency group may hold) are skipped rather than parsed, since
    detection only cares about direct requirement strings.

    Args:
        entries: Iterable of raw dependency entries from a parsed
            ``pyproject.toml``.

    Yields:
        The canonicalized leading distribution name of each string entry.
    """
    for entry in entries:
        if not isinstance(entry, str):
            continue
        head = _REQUIREMENT_NAME_BOUNDARY.split(entry.strip(), maxsplit=1)[0]
        if head:
            yield _canonical_distribution_name(head)


def _pyproject_declares_vaultspec_dependency(pyproject: Path) -> bool:
    """Return whether ``vaultspec-core`` is declared in *pyproject*.

    Probes leniently across every place a project can declare the dependency:
    :pep:`621` ``[project.dependencies]`` and ``[project.optional-dependencies]``,
    :pep:`735` ``[dependency-groups]``, and the legacy
    ``[tool.uv.dev-dependencies]`` list. A malformed or unreadable file is
    treated as "no dependency declared" rather than raising, because detection
    is advisory evidence layered beneath explicit and persisted precedence and
    must not turn a broken manifest into a hard failure.

    Args:
        pyproject: Path to the target's ``pyproject.toml``.

    Returns:
        ``True`` if any dependency set lists ``vaultspec-core``.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
        return False

    candidates: list[Any] = []

    project = data.get("project")
    if isinstance(project, dict):
        deps = project.get("dependencies")
        if isinstance(deps, list):
            candidates.extend(deps)
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    candidates.extend(group)

    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, list):
                candidates.extend(group)

    tool = data.get("tool")
    if isinstance(tool, dict):
        uv = tool.get("uv")
        if isinstance(uv, dict):
            dev = uv.get("dev-dependencies")
            if isinstance(dev, list):
                candidates.extend(dev)

    return any(name == _DISTRIBUTION_NAME for name in _requirement_names(candidates))


def resolve_install_mode(
    target: Path,
    explicit: InstallMode | None = None,
) -> InstallMode:
    """Resolve the effective provisioning mode via the Q5 precedence chain.

    Precedence, highest first:

    1. *explicit* - the ``--mode`` flag, when supplied.
    2. The persisted committed declaration
       (:func:`read_workspace_declaration`), when one exists.
    3. Detection against the target's ``pyproject.toml``.
    4. The default, :attr:`~vaultspec_core.core.enums.InstallMode.TOOL`.

    Detection reads two signals: the absence of any ``pyproject.toml`` forces
    :attr:`~vaultspec_core.core.enums.InstallMode.TOOL` because nothing exists to
    resolve a dependency against; the presence of ``vaultspec-core`` in the
    project's dependencies or any dev-dependency group is evidence of deliberate
    :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY` mode. Absent both,
    the default tool mode stands.

    Only impossible combinations refuse. Requesting
    :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY` in a target with no
    ``pyproject.toml`` has nothing to resolve the dependency against and raises,
    rather than silently falling back to tool mode and deferring the failure to
    hook or MCP runtime. An explicit mode that merely differs from detection
    evidence - a ``pyproject.toml`` exists but does not yet list
    ``vaultspec-core`` while ``--mode dependency`` is requested - is permitted,
    since the contributor may be about to add the dependency.

    The persisted declaration is read and validated once at the top, regardless
    of which precedence branch resolves the mode. This makes a corrupt
    ``.vaultspec/workspace.json`` fail fast here - at the same point as the
    impossible-combo refusal - rather than surfacing later inside
    :func:`_persist_resolved_mode` after migrations, builtin re-seeding, and
    provider sync have already run and left a partial-upgrade state. Callers may
    therefore treat a successful return as proof the declaration is
    well-formed.

    Args:
        target: Workspace root directory.
        explicit: The mode requested via ``--mode``, or ``None`` to fall through
            to the persisted declaration, detection, and default in turn.

    Returns:
        The resolved :class:`~vaultspec_core.core.enums.InstallMode`.

    Raises:
        VaultSpecError: If *explicit* is
            :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY` but the
            target has no ``pyproject.toml``, or if a present declaration is
            malformed (propagated from :func:`read_workspace_declaration`).
    """
    pyproject = target / "pyproject.toml"
    has_pyproject = pyproject.is_file()

    # Validate the persisted declaration first, on every path, so corruption
    # surfaces fail-fast rather than mid-provision. An explicit request still
    # outranks the parsed value; the read is for validation and the persisted
    # precedence branch below.
    declaration = read_workspace_declaration(target)

    if explicit is not None:
        if explicit is InstallMode.DEPENDENCY and not has_pyproject:
            raise VaultSpecError(
                f"Cannot provision in dependency mode: no pyproject.toml at {target}.",
                hint="Add a pyproject.toml that declares vaultspec-core as a "
                "dependency, or re-run with '--mode tool'.",
            )
        return explicit

    if declaration is not None:
        return declaration.install_mode

    if not has_pyproject:
        return InstallMode.TOOL
    if _pyproject_declares_vaultspec_dependency(pyproject):
        return InstallMode.DEPENDENCY
    return InstallMode.TOOL


def resolve_render_mode(target: Path) -> InstallMode:
    """Resolve the mode downstream renderers target for a provisioned workspace.

    Distinct from :func:`resolve_install_mode`, which resolves the mode at
    *provision* time and defaults an undeclared workspace to
    :attr:`~vaultspec_core.core.enums.InstallMode.TOOL`. This resolves the mode
    for *rendering* artifacts (the MCP launch command, the pre-commit hook
    entries) into an already-provisioned workspace, where the absence of a
    declaration carries the opposite meaning: the workspace predates the
    ``install-mode`` decision and was therefore provisioned in the only shape
    that existed before it, dependency mode.

    Returning :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY` on an
    absent declaration is the Q6 migration bridge: it keeps ``sync`` and
    ``doctor`` byte-identical to their pre-``install-mode`` output on a legacy
    workspace until ``install --upgrade`` infers and records a mode. Without
    it, syncing a legacy dependency-mode workspace would silently rewrite its
    ``uv run`` launch command and hook entries to the ``uvx`` tool-mode shape
    and diagnose the workspace as drifted against a mode it never chose.

    The provision-time entry points (fresh ``install``) pass their resolved
    mode explicitly rather than relying on this fallback, since the committed
    declaration is only written after scaffolding renders its artifacts.

    Args:
        target: Workspace root directory.

    Returns:
        The declared :class:`~vaultspec_core.core.enums.InstallMode` when a
        well-formed declaration exists, else
        :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY`.

    Raises:
        VaultSpecError: If a declaration exists but is malformed (propagated
            from :func:`read_workspace_declaration`).
    """
    declaration = read_workspace_declaration(target)
    if declaration is not None:
        return declaration.install_mode
    return InstallMode.DEPENDENCY
