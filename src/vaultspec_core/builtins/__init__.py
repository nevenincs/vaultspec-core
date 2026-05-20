"""Bundled builtin resources deployed during ``vaultspec-core install``.

Contains canonical rules, skills, agents, system prompts, templates, and hooks
seeded into ``.vaultspec/rules/`` on first install. Consumed by
:mod:`vaultspec_core.cli.root` via :func:`seed_builtins` and :func:`list_builtins`.
Uses :mod:`importlib.resources` for package-relative file access.
"""

from __future__ import annotations

import logging
import shutil
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


def _builtins_root() -> Path:
    """Return the filesystem path to the bundled builtins directory.

    For installed (wheel) builds the content lives alongside this module.
    For editable / development installs the content is not copied into
    ``src/``; instead we resolve the canonical ``.vaultspec/rules/``
    directory at the repository root.
    """
    pkg_dir = Path(str(resources.files(__package__)))

    # Quick probe: a wheel build will contain at least the 'templates' dir.
    if (pkg_dir / "templates").is_dir():
        return pkg_dir

    # Editable install -- walk up to the repo root and use the canonical
    # source directly.  The repo root is identified by pyproject.toml.
    candidate = pkg_dir
    for _ in range(10):
        candidate = candidate.parent
        if (candidate / "pyproject.toml").is_file():
            rules = candidate / ".vaultspec" / "rules"
            if rules.is_dir():
                return rules
            break

    # Fallback: return the package directory regardless.
    return pkg_dir


def seed_builtins(
    target_rules_dir: Path, *, force: bool = False
) -> list[tuple[str, str]]:
    """Copy bundled builtins into a target ``.vaultspec/rules/`` directory.

    Files that already exist are left untouched unless *force* is True.

    Args:
        target_rules_dir: The ``.vaultspec/rules/`` directory to populate.
        force: Overwrite existing files.

    Returns:
        List of ``(relative_path, action)`` pairs for every builtin the
        call acted on, where ``action`` is ``[ADD]`` (newly written),
        ``[UPDATE]`` (overwritten with changed content) or
        ``[UNCHANGED]`` (already current). Builtins skipped because they
        exist and *force* is False are omitted.
    """
    src = _builtins_root()
    results: list[tuple[str, str]] = []

    # Walk the bundled builtins tree
    for src_file in sorted(src.rglob("*")):
        if not src_file.is_file():
            continue
        # Skip Python package artifacts
        if src_file.name in ("__init__.py", "__pycache__") or "__pycache__" in str(
            src_file
        ):
            continue

        rel = src_file.relative_to(src)
        dest = target_rules_dir / rel
        rel_str = str(rel).replace("\\", "/")

        if dest.exists() and not force:
            continue

        try:
            src_bytes = src_file.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read builtin %s: %s", rel, exc)
            continue

        if not dest.exists():
            action = "[ADD]"
        else:
            try:
                action = (
                    "[UNCHANGED]" if dest.read_bytes() == src_bytes else "[UPDATE]"
                )
            except OSError:
                action = "[UPDATE]"

        if action != "[UNCHANGED]":
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest)
            except OSError as exc:
                logger.warning("Failed to seed %s: %s", rel, exc)
                continue
        results.append((rel_str, action))

    return results


def list_builtins() -> list[str]:
    """Return relative paths of all bundled builtin files.

    Returns:
        Sorted list of relative paths (forward-slash separated).
    """
    src = _builtins_root()
    paths: list[str] = []
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        if f.name in ("__init__.py", "__pycache__") or "__pycache__" in str(f):
            continue
        paths.append(str(f.relative_to(src)).replace("\\", "/"))
    return paths


def check_outdated(target_rules_dir: Path) -> list[str]:
    """Compare bundled builtins against a deployed ``.vaultspec/rules/`` tree.

    Returns:
        List of relative paths (forward-slash separated) present in the
        package but missing or content-different at the target.
    """
    src = _builtins_root()
    outdated: list[str] = []
    for src_file in sorted(src.rglob("*")):
        if not src_file.is_file():
            continue
        if src_file.name in ("__init__.py", "__pycache__") or "__pycache__" in str(
            src_file
        ):
            continue
        rel = src_file.relative_to(src)
        dest = target_rules_dir / rel
        if not dest.exists():
            outdated.append(str(rel).replace("\\", "/"))
            continue
        try:
            if src_file.read_bytes() != dest.read_bytes():
                outdated.append(str(rel).replace("\\", "/"))
        except OSError:
            outdated.append(str(rel).replace("\\", "/"))
    return outdated
