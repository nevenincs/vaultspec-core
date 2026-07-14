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
from .helpers import advisory_lock, atomic_write, parse_version_tuple

WORKSPACE_FILENAME = "workspace.json"

#: Current declaration schema version. Schema 2.0 is the per-package ``packages``
#: map that lets one committed ``workspace.json`` carry a mode (and optional
#: version floor) for each provisioned distribution independently.
WORKSPACE_SCHEMA_VERSION = "2.0"

#: The legacy single-key schema (``install_mode`` plus an optional
#: ``minimum_vaultspec_version`` at the top level) that ``install-mode`` shipped.
#: Files in this shape are recognized on read and folded into the schema 2.0
#: ``packages`` map keyed to :data:`_DISTRIBUTION_NAME`, then rewritten in the
#: current shape on the next write.
_LEGACY_SCHEMA_VERSION = "1.0"

#: Distribution name detection keys on; canonicalized per PEP 503 so that
#: ``vaultspec_core`` and ``vaultspec-core`` compare equal.
_DISTRIBUTION_NAME = "vaultspec-core"

#: Split a PEP 508 requirement string at the first character that terminates
#: the distribution name (version specifier, extras, marker, or whitespace).
_REQUIREMENT_NAME_BOUNDARY = re.compile(r"[<>=!~;\[\s(]")


@dataclass
class PackageDeclaration:
    """One provisioned distribution's entry in the schema 2.0 ``packages`` map.

    Each provisioned package (``vaultspec-core``, ``vaultspec-rag``, ...) owns an
    independent entry, so a workspace can declare, for example, core in
    dependency mode and rag in tool mode without the two choices colliding on a
    single shared key.

    Attributes:
        install_mode: The provisioning mode declared for this package.
        minimum_version: Optional floor constraint for this package; when set, an
            invocation whose running package version is below it is refused per
            the ``install-mode`` version-skew handshake. ``None`` when the
            package declares no floor. This is the per-package rename of the
            legacy top-level ``minimum_vaultspec_version`` key: now that the floor
            lives inside a named package entry it is package-relative, so the
            distribution-qualified name is redundant.
    """

    install_mode: InstallMode
    minimum_version: str | None = None


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


def _parse_package_entry(path: Path, name: object, entry: Any) -> PackageDeclaration:
    """Parse one schema 2.0 ``packages`` entry into a :class:`PackageDeclaration`.

    Strict about a present but broken entry: a non-object entry or an
    out-of-vocabulary ``install_mode`` raises rather than silently dropping the
    package, matching the fail-loud contract the top-level read already honors.

    Args:
        path: The declaration file, named in error messages.
        name: The package key the entry sits under, named in error messages.
        entry: The raw entry value parsed from JSON.

    Returns:
        The parsed :class:`PackageDeclaration`.

    Raises:
        VaultSpecError: If *entry* is not an object or names an ``install_mode``
            outside the canonical :class:`~vaultspec_core.core.enums.InstallMode`
            vocabulary.
    """
    if not isinstance(entry, dict):
        raise VaultSpecError(
            f"Malformed package entry for {name!r} in workspace declaration at "
            f"{path}: expected a JSON object.",
            hint="Fix the JSON by hand or re-run 'vaultspec-core install --mode'.",
        )
    mode = InstallMode.from_token(entry.get("install_mode"))
    if mode is None:
        raise VaultSpecError(
            f"Invalid install_mode for package {name!r} in workspace declaration "
            f"at {path}: {entry.get('install_mode')!r}.",
            hint="Set install_mode to 'tool', 'dependency', or 'dev', "
            "or re-run 'vaultspec-core install --mode'.",
        )
    floor = entry.get("minimum_version")
    minimum = str(floor) if floor is not None else None
    return PackageDeclaration(install_mode=mode, minimum_version=minimum)


def _read_packages_map(target: Path) -> dict[str, PackageDeclaration] | None:
    """Read every package entry from the committed ``workspace.json``.

    The single parse point behind the whole read surface. A missing file is
    lenient (returns ``None``); a present but broken file is strict (raises).
    Two on-disk shapes are recognized: the schema 2.0 ``packages`` map is parsed
    entry by entry, and the legacy schema 1.0 single-key shape
    (``install_mode`` plus optional ``minimum_vaultspec_version`` at the top
    level) is folded into a one-entry map keyed to :data:`_DISTRIBUTION_NAME`,
    renaming the top-level ``minimum_vaultspec_version`` floor to the
    package-relative ``minimum_version``. The fold happens purely in memory; the
    next write persists the file in schema 2.0 shape.

    Package keys are canonicalized per PEP 503 so callers can look an entry up by
    any spelling of a distribution name.

    Args:
        target: Workspace root directory.

    Returns:
        A mapping of canonicalized distribution name to
        :class:`PackageDeclaration`, or ``None`` when the file is absent.

    Raises:
        VaultSpecError: If the file exists but contains invalid JSON, is
            unreadable, is not an object, or names an ``install_mode`` outside
            the canonical :class:`~vaultspec_core.core.enums.InstallMode`
            vocabulary.
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

    packages_raw = raw.get("packages")
    if packages_raw is not None:
        if not isinstance(packages_raw, dict):
            raise VaultSpecError(
                f"Malformed 'packages' map in workspace declaration at {path}: "
                "expected a JSON object.",
                hint="Fix the JSON by hand or re-run 'vaultspec-core install --mode'.",
            )
        return {
            _canonical_distribution_name(str(name)): _parse_package_entry(
                path, name, entry
            )
            for name, entry in packages_raw.items()
        }

    # Legacy schema 1.0 single-key shape: fold into the default package entry,
    # renaming the top-level minimum_vaultspec_version floor to the
    # package-relative minimum_version.
    mode = InstallMode.from_token(raw.get("install_mode"))
    if mode is None:
        raise VaultSpecError(
            f"Invalid install_mode in workspace declaration at {path}: "
            f"{raw.get('install_mode')!r}.",
            hint="Set install_mode to 'tool', 'dependency', or 'dev', "
            "or re-run 'vaultspec-core install --mode'.",
        )
    floor = raw.get("minimum_vaultspec_version")
    minimum = str(floor) if floor is not None else None
    return {
        _DISTRIBUTION_NAME: PackageDeclaration(
            install_mode=mode, minimum_version=minimum
        )
    }


def read_workspace_declaration(target: Path) -> WorkspaceDeclaration | None:
    """Read the ``vaultspec-core`` view of the committed ``workspace.json``.

    The backward-compatible facade over the schema 2.0 ``packages`` map: it
    returns the ``vaultspec-core`` package's entry projected onto the
    single-package :class:`WorkspaceDeclaration` shape every existing caller
    already consumes. A legacy schema 1.0 file folds into exactly this entry, so
    the facade is byte-transparent to callers written against the single-key
    schema.

    A missing file is lenient (returns ``None``, meaning no mode declared yet).
    A file that exists but declares no ``vaultspec-core`` entry - a workspace
    that provisioned only a companion package - also returns ``None`` here, since
    core has no declaration of its own to report. A present but broken file is
    strict and raises.

    Args:
        target: Workspace root directory.

    Returns:
        The ``vaultspec-core`` entry as a :class:`WorkspaceDeclaration`, or
        ``None`` when the file is absent or carries no ``vaultspec-core`` entry.

    Raises:
        VaultSpecError: If the file exists but contains invalid JSON, is
            unreadable, or names an ``install_mode`` outside the canonical
            :class:`~vaultspec_core.core.enums.InstallMode` vocabulary.
    """
    packages = _read_packages_map(target)
    if packages is None:
        return None
    entry = packages.get(_DISTRIBUTION_NAME)
    if entry is None:
        return None
    return WorkspaceDeclaration(
        install_mode=entry.install_mode,
        minimum_vaultspec_version=entry.minimum_version,
        schema_version=WORKSPACE_SCHEMA_VERSION,
    )


def _write_packages_map(target: Path, packages: dict[str, PackageDeclaration]) -> None:
    """Serialize *packages* to ``.vaultspec/workspace.json`` in schema 2.0 shape.

    The single lock-free write primitive. Emits the ``{"schema_version": "2.0",
    "packages": {...}}`` envelope canonically: ``json.dumps`` with
    ``sort_keys=True`` orders the package names and every nested key
    deterministically, two-space indent and a trailing newline keep the
    committed file diff-clean. Each package entry carries its ``install_mode``
    and, only when set, its ``minimum_version`` floor, so an unset floor never
    writes a null. Callers that must not race a concurrent writer wrap this in
    :func:`~vaultspec_core.core.helpers.advisory_lock`; this primitive itself
    takes no lock so it can be composed inside a caller's own read-modify-write
    critical section without re-entering a non-reentrant lock.

    Args:
        target: Workspace root directory.
        packages: Mapping of distribution name to :class:`PackageDeclaration`.
    """
    path = _workspace_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    packages_payload: dict[str, dict[str, str]] = {}
    for name, decl in packages.items():
        entry: dict[str, str] = {"install_mode": InstallMode(decl.install_mode).value}
        if decl.minimum_version is not None:
            entry["minimum_version"] = decl.minimum_version
        packages_payload[name] = entry
    payload = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "packages": packages_payload,
    }
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_workspace_declaration(
    target: Path, declaration: WorkspaceDeclaration
) -> None:
    """Persist the ``vaultspec-core`` view to ``.vaultspec/workspace.json``.

    The backward-compatible facade over the schema 2.0 write path: it upserts the
    ``vaultspec-core`` entry in the ``packages`` map from a single-package
    :class:`WorkspaceDeclaration` while leaving every companion package's entry
    untouched. The whole read-modify-write cycle runs under a single advisory
    lock so a concurrent writer of a sibling package's entry is serialized rather
    than clobbered. The file is always rewritten in schema 2.0 shape, so a legacy
    single-key file is migrated on the first write. The declaration's own
    ``schema_version`` field is ignored on write; the on-disk version is always
    :data:`WORKSPACE_SCHEMA_VERSION`.

    Args:
        target: Workspace root directory.
        declaration: :class:`WorkspaceDeclaration` instance to persist as the
            ``vaultspec-core`` entry.
    """
    path = _workspace_path(target)
    entry = PackageDeclaration(
        install_mode=InstallMode(declaration.install_mode),
        minimum_version=declaration.minimum_vaultspec_version,
    )
    with advisory_lock(path):
        packages = _read_packages_map(target) or {}
        packages[_DISTRIBUTION_NAME] = entry
        _write_packages_map(target, packages)


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


def evaluate_version_floor(
    target: Path, running_version: str
) -> tuple[str, str] | None:
    """Evaluate the committed floor constraint against *running_version*.

    Reads the committed ``.vaultspec/workspace.json`` declaration's
    ``minimum_vaultspec_version`` and compares it to *running_version*. This is
    the single shared comparator behind both refuse-and-tell on install/sync
    (which raises on a violation) and report-on-doctor (which renders a row
    without raising), so the two surfaces cannot diverge on what "below the
    floor" means.

    A workspace that declares no floor, or whose versions cannot be parsed,
    imposes no constraint and returns ``None``. A corrupt declaration
    propagates :class:`~vaultspec_core.core.exceptions.VaultSpecError` from
    :func:`read_workspace_declaration`; callers decide whether to surface or
    swallow it.

    Args:
        target: Workspace root directory.
        running_version: The running ``vaultspec-core`` package version string.

    Returns:
        ``(running_version, floor)`` when the running version is strictly below
        the declared floor, else ``None``.

    Raises:
        VaultSpecError: If a declaration exists but is malformed (propagated
            from :func:`read_workspace_declaration`).
    """
    declaration = read_workspace_declaration(target)
    if declaration is None or declaration.minimum_vaultspec_version is None:
        return None

    floor = declaration.minimum_vaultspec_version
    try:
        if parse_version_tuple(running_version) < parse_version_tuple(floor):
            return running_version, floor
    except Exception:
        return None
    return None


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
