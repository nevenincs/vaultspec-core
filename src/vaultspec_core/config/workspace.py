"""Workspace topology resolution and layout validation for vaultspec.

Determines how a target directory maps to ``.vault/`` and ``.vaultspec/``
roots across standalone, explicit, git, worktree, and ``.gt/`` container modes.
Key exports: :func:`resolve_target`, :func:`resolve_workspace`,
:func:`discover_git`, :class:`WorkspaceLayout`, :class:`GitInfo`,
:class:`LayoutMode`, :class:`WorkspaceError`. Re-exported via
:mod:`vaultspec_core.config`; consumed by :mod:`vaultspec_core.cli.root` and
:mod:`vaultspec_core.core.types`.

:func:`resolve_target` covers the two rungs that name a root - the invocation
and the session environment - and leaves discovery to
:func:`resolve_workspace`. Every package resolves its root through it, passing
its own package-scoped entry, so one order holds everywhere.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from vaultspec_core.core.exceptions import ConfigurationError, VaultSpecError
from vaultspec_core.env_values import rejection

from .config import VAULTSPEC_TARGET_DIR, env_source, env_value

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .config import ConfigVariable

logger = logging.getLogger(__name__)

__all__ = [
    "GitInfo",
    "LayoutMode",
    "ResolvedTarget",
    "TargetSource",
    "WorkspaceError",
    "WorkspaceLayout",
    "discover_git",
    "resolve_target",
    "resolve_workspace",
]


class LayoutMode(Enum):
    """How the workspace layout was resolved.

    Attributes:
        STANDALONE: No explicit target override; root was inferred from git
            detection or cwd.
        EXPLICIT: Target directory was provided via ``--target`` or
            ``VAULTSPEC_TARGET_DIR``.
    """

    STANDALONE = "standalone"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class GitInfo:
    """Discovered git repository metadata.

    Attributes:
        git_dir: Resolved path to the ``.git`` directory (or bare git dir).
        repo_root: The root of the main repository.
        is_worktree: ``True`` if the current working directory is a linked worktree.
        is_bare: ``True`` if the repository uses a bare ``.gt/`` layout.
        worktree_root: Root of the linked worktree, or ``None``.
        container_root: Root of the ``.gt/`` container repo, or ``None``.
    """

    git_dir: Path
    repo_root: Path
    is_worktree: bool
    is_bare: bool
    worktree_root: Path | None
    container_root: Path | None


@dataclass(frozen=True)
class WorkspaceLayout:
    """Fully resolved, validated workspace paths.

    Attributes:
        target_dir: The root directory for the workspace (where .vault/ and
            .vaultspec/ live).
        vault_dir: Path to the ``.vault/`` documentation directory.
        vaultspec_dir: Path to the ``.vaultspec/`` framework directory.
        mode: How the layout was resolved (standalone or explicit).
        git: Discovered git repository metadata, or ``None`` if not in a repo.
    """

    target_dir: Path
    vault_dir: Path
    vaultspec_dir: Path
    mode: LayoutMode
    git: GitInfo | None


def _strip_unc(path: Path) -> Path:
    """Strip Windows ``\\\\?\\`` UNC prefix if present.

    Args:
        path: Path that may carry a ``\\\\?\\`` prefix from ``Path.resolve()``
            on Windows.

    Returns:
        The same path with the UNC prefix removed, or the original path
        unchanged if no prefix was found.
    """
    s = str(path)
    if s.startswith("\\\\?\\"):
        return Path(s[4:])
    return path


def _parse_git_pointer(git_path: Path) -> Path | None:
    """Parse a ``.git`` file containing ``gitdir: <path>``.

    Args:
        git_path: Path to the ``.git`` file (not directory) to read.

    Returns:
        Resolved absolute path to the real git directory, or ``None`` if the
        file cannot be read or does not contain a valid ``gitdir:`` pointer.
    """
    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Failed to read git pointer %s: %s", git_path, e)
        return None

    if not content.startswith("gitdir:"):
        return None

    raw = content[len("gitdir:") :].strip()
    target = Path(raw)

    if not target.is_absolute():
        target = (git_path.parent / target).resolve()
    else:
        target = target.resolve()

    return _strip_unc(target)


def _walk_up_for_git(start: Path) -> tuple[Path, bool] | None:
    """Walk up from *start* looking for ``.git`` (file or directory).

    Args:
        start: Directory to begin the upward search from.

    Returns:
        ``(dot_git_path, is_file)`` where ``dot_git_path`` is the found
        ``.git`` entry and ``is_file`` indicates whether it is a file (linked
        worktree pointer) rather than a directory. Returns ``None`` if no
        ``.git`` entry is found before reaching the filesystem root.
    """
    current = start.resolve()
    current = _strip_unc(current)

    while True:
        dot_git = current / ".git"
        if dot_git.exists():
            return (dot_git, dot_git.is_file())

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _find_container_root(git_dir: Path) -> Path | None:
    """Return the container root for a git_dir inside a ``.gt/`` bare repo.

    Handles both direct ``.gt/`` refs and ``.gt/worktrees/<name>/``
    sub-paths.

    Args:
        git_dir: Resolved path to the git directory, which may be inside a
            ``.gt/`` bare repository tree.

    Returns:
        The parent directory of ``.gt/`` (i.e., the container root), or
        ``None`` if no ``.gt/`` component is found in the path.
    """
    parts = git_dir.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == ".gt":
            return Path(*parts[:i]) if i > 0 else Path(parts[0])
    return None


def discover_git(start: Path) -> GitInfo | None:
    """Walk up from start to find and classify the git repository.

    Handles standard repos (``.git/`` dir), linked worktrees (``.git`` file
    with gitdir pointer), container mode (``.gt/`` bare repo), and bare repos.

    Args:
        start: The directory to begin searching from.

    Returns:
        A populated ``GitInfo`` instance, or ``None`` if no git repository
        was found.
    """
    resolved_start = _strip_unc(start.resolve())

    # --- Check for .gt/ container at start or walking up ---
    current = resolved_start
    while True:
        gt = current / ".gt"
        if gt.is_dir():
            return GitInfo(
                git_dir=gt,
                repo_root=current,
                is_worktree=False,
                is_bare=True,
                worktree_root=None,
                container_root=current,
            )
        parent = current.parent
        if parent == current:
            break
        current = parent

    # --- Check for .git (file or directory) ---
    result = _walk_up_for_git(resolved_start)
    if result is None:
        return None

    dot_git, is_file = result

    if not is_file:
        # Standard .git/ directory
        return GitInfo(
            git_dir=dot_git,
            repo_root=dot_git.parent,
            is_worktree=False,
            is_bare=False,
            worktree_root=None,
            container_root=None,
        )

    # .git is a file -- linked worktree
    real_git_dir = _parse_git_pointer(dot_git)
    if real_git_dir is None:
        return None

    worktree_root = dot_git.parent

    # Check if this points into a .gt/ bare repo (container mode)
    container = _find_container_root(real_git_dir)
    if container is not None:
        return GitInfo(
            git_dir=real_git_dir,
            repo_root=container,
            is_worktree=True,
            is_bare=True,
            worktree_root=worktree_root,
            container_root=container,
        )

    # Standard linked worktree -- trace back to main repo root.
    # real_git_dir is typically <repo>/.git/worktrees/<name>
    # The main repo root is the grandparent of the ``worktrees/`` dir.
    if real_git_dir.parent.name == "worktrees":
        main_git_dir = real_git_dir.parent.parent
        return GitInfo(
            git_dir=real_git_dir,
            repo_root=main_git_dir.parent,
            is_worktree=True,
            is_bare=False,
            worktree_root=worktree_root,
            container_root=None,
        )

    # Fallback: cannot determine main repo root from pointer
    return GitInfo(
        git_dir=real_git_dir,
        repo_root=worktree_root,
        is_worktree=True,
        is_bare=False,
        worktree_root=worktree_root,
        container_root=None,
    )


class WorkspaceError(VaultSpecError):
    """Raised when workspace layout resolution or validation fails.

    Typically indicates a missing ``.vaultspec/`` directory or an unreachable
    target path.  Caught by the CLI root callback and converted to an error exit.
    """


def _validate(layout: WorkspaceLayout) -> None:
    """Validate a resolved ``WorkspaceLayout``.

    Args:
        layout: The workspace layout to validate.

    Raises:
        WorkspaceError: If ``vaultspec_dir`` is not an existing directory or
            ``target_dir`` does not exist.
    """
    if not layout.vaultspec_dir.is_dir():
        raise WorkspaceError(
            f"vaultspec_dir does not exist or is not a directory: "
            f"{layout.vaultspec_dir}\n"
            f"Ensure your --target directory contains a .vaultspec/ folder."
        )

    if not layout.target_dir.exists():
        raise WorkspaceError(
            f"target_dir does not exist: {layout.target_dir}\n"
            f"Provide a valid directory via --target."
        )


class TargetSource(StrEnum):
    """Which rung supplied a workspace root.

    Attributes:
        INVOCATION: The call itself named it - a ``--target`` flag, a tool
            argument, or a programmatic override.
        ENVIRONMENT: A registered variable named it, the package-scoped name
            first and the framework name behind it.
        DISCOVERY: Nothing named it, so it is discovered from the working
            directory by :func:`resolve_workspace`.
    """

    INVOCATION = "invocation"
    ENVIRONMENT = "environment"
    DISCOVERY = "discovery"


@dataclass(frozen=True)
class ResolvedTarget:
    """A workspace root and the rung that supplied it.

    Attributes:
        path: The absolute root, or ``None`` when no rung named one and the
            caller should discover it from the working directory.
        source: Which rung supplied :attr:`path`.
        variable: The environment variable that supplied it, or ``None`` for
            any other rung. A diagnostic names the variable the operator
            actually set, which may be the framework name behind a
            package-scoped one.
    """

    path: Path | None
    source: TargetSource
    variable: str | None = None

    def __post_init__(self) -> None:
        has_variable = self.variable is not None
        from_environment = self.source is TargetSource.ENVIRONMENT
        if has_variable != from_environment:
            raise ValueError(
                "variable is set if and only if source is ENVIRONMENT: "
                f"got source={self.source!r}, variable={self.variable!r}"
            )


def _absolute(path: Path, base: Path) -> Path:
    """Return *path* as an absolute path, relative ones taken against *base*."""
    absolute = path if path.is_absolute() else base / path
    return _strip_unc(absolute.resolve())


def resolve_target(
    explicit: Path | None = None,
    *,
    package_root: ConfigVariable | None = None,
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> ResolvedTarget:
    """Resolve the workspace root from the invocation and the environment.

    The two rungs that can *name* a root, in order: the invocation, then the
    session environment. A package passes its own root entry, whose framework
    fallback reaches ``VAULTSPEC_TARGET_DIR``; a package without one gets
    ``VAULTSPEC_TARGET_DIR`` itself. Neither rung naming a root is not a
    failure: it means discovery, which :func:`resolve_workspace` performs when
    handed no override.

    Args:
        explicit: The root the invocation named, or ``None``.
        package_root: The calling package's root entry. ``None`` reads
            ``VAULTSPEC_TARGET_DIR`` directly.
        environ: The environment to read; ``None`` reads the process's own.
        cwd: The directory a relative root is taken against; ``None`` uses
            the process's own working directory.

    Returns:
        The resolved root paired with the rung that supplied it.

    Raises:
        ConfigurationError: If a variable names a directory that does not
            exist. A root that is not there cannot be discovered past: the
            operator asked for one workspace and would silently get another.
        ValueError: If *package_root* is not a registered entry.
    """
    base = _strip_unc((cwd or Path.cwd()).resolve())
    if explicit is not None:
        return ResolvedTarget(_absolute(explicit, base), TargetSource.INVOCATION)

    entry = VAULTSPEC_TARGET_DIR if package_root is None else package_root
    raw = env_value(entry, environ)
    if raw is None:
        return ResolvedTarget(None, TargetSource.DISCOVERY)

    supplier = env_source(entry, environ)
    name = entry.env_name if supplier is None else supplier.env_name
    root = _absolute(Path(raw), base)
    if not root.is_dir():
        raise ConfigurationError(
            str(rejection(name, "an existing directory", raw)),
            hint=f"Point {name} at a directory that exists, or unset it.",
        )
    return ResolvedTarget(root, TargetSource.ENVIRONMENT, name)


def resolve_workspace(
    *,
    target_override: Path | None = None,
    framework_dir_name: str = ".vaultspec",
    framework_root: Path | None = None,
    cwd: Path | None = None,
) -> WorkspaceLayout:
    """Resolve the complete workspace layout.

    Resolution priority: explicit overrides → git detection → structural
    fallback → cwd-based last resort.

    Args:
        target_override: Explicit target directory (``--target`` /
            ``VAULTSPEC_TARGET_DIR``).
        framework_dir_name: Name of the framework directory (default ``".vaultspec"``).
        framework_root: Structurally-known location of the ``.vaultspec/``
            directory. Never derived from env vars.
        cwd: Override for ``Path.cwd()``  - intended for testing.

    Returns:
        A fully resolved and validated ``WorkspaceLayout``.

    Raises:
        WorkspaceError: If the resolved layout fails validation.
    """
    effective_cwd = (cwd or Path.cwd()).resolve()
    effective_cwd = _strip_unc(effective_cwd)

    # --- EXPLICIT mode: target provided ---
    if target_override is not None:
        target_dir = target_override.resolve()
        target_dir = _strip_unc(target_dir)

        fw_root = framework_root or (target_dir / framework_dir_name)

        layout = WorkspaceLayout(
            target_dir=target_dir,
            vault_dir=target_dir / ".vault",
            vaultspec_dir=fw_root,
            mode=LayoutMode.EXPLICIT,
            git=discover_git(target_dir),
        )
        _validate(layout)
        return layout

    # --- STANDALONE: No overrides, try git detection from cwd ---
    git = discover_git(effective_cwd)

    if git is not None:
        # Prefer container_root, then worktree_root, then repo_root
        root = git.container_root or git.worktree_root or git.repo_root
        root = _strip_unc(root)
        fw_root = framework_root or (root / framework_dir_name)

        layout = WorkspaceLayout(
            target_dir=root,
            vault_dir=root / ".vault",
            vaultspec_dir=fw_root,
            mode=LayoutMode.STANDALONE,
            git=git,
        )
        _validate(layout)
        return layout

    # --- Structural fallback: derive from framework_root ---
    if framework_root is not None:
        root = framework_root.parent
        root = _strip_unc(root)

        layout = WorkspaceLayout(
            target_dir=root,
            vault_dir=root / ".vault",
            vaultspec_dir=framework_root,
            mode=LayoutMode.STANDALONE,
            git=discover_git(root),
        )
        _validate(layout)
        return layout

    # --- Last resort: cwd-based ---
    root = effective_cwd
    fw_root = root / framework_dir_name

    layout = WorkspaceLayout(
        target_dir=root,
        vault_dir=root / ".vault",
        vaultspec_dir=fw_root,
        mode=LayoutMode.STANDALONE,
        git=None,
    )
    _validate(layout)
    return layout
