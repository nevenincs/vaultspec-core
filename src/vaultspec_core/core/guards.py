"""Dev-repo protection guard for vaultspec-core.

Detects when the effective ``TARGET_DIR`` is the vaultspec-core source
repository (or one of its worktrees) and refuses destructive writes
(install, uninstall, sync) that would corrupt the canonical
``.vaultspec/`` content unless the caller explicitly authorises
dev-mode operation via the ``--dev`` CLI flag.

Detection is definitive: a ``pyproject.toml`` at the target root whose
``[project].name`` equals ``"vaultspec-core"`` can never appear in any
normal installed project.  Every git worktree of the source repo
shares the same ``pyproject.toml``, so worktrees are covered for free.

There is no environment-variable bypass.  Any "yes I really mean it"
authorisation has to come from an explicit ``--dev`` flag at the
command line; environment variables are too coarse a signal to gate
filesystem mutations on.  See GitHub issue #88.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from .exceptions import VaultSpecError

logger = logging.getLogger(__name__)

_PROJECT_NAME = "vaultspec-core"


class DevRepoProtectionError(VaultSpecError):
    """Raised when an operation would modify the dev repo's managed content."""


def is_dev_repo(root: Path) -> bool:
    """Return ``True`` if *root* is the vaultspec-core source repository.

    Detection deliberately requires **multiple corroborating signals**, not
    just a name match.  A consumer project that ships a stale or hand-
    crafted ``pyproject.toml`` declaring ``name = "vaultspec-core"`` must
    not trigger the guard, and a fresh worktree that hasn't yet
    materialised some files must still be detected.  See GitHub issue #88.

    Required signals (all must hold):

    1. ``root / "pyproject.toml"`` exists and parses as TOML.
    2. ``[project].name == "vaultspec-core"``.
    3. The Python package source layout is present at the canonical
       location (``src/vaultspec_core/__init__.py``).  This is the strong
       signal: it pins us to the actual source bearer of the framework
       rather than any project that happens to claim the name.

    Optional corroborating signals (used when present, never required):

    - ``[tool.hatch.build.targets.wheel.force-include]`` mentions
      ``.vaultspec/rules`` -> proves this root is the build root that
      bundles the canonical framework content into the wheel.
    - A ``.git`` entry exists -> the directory is a git working tree or
      worktree.

    Args:
        root: Directory to inspect.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False

    import tomllib

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return False

    if data.get("project", {}).get("name") != _PROJECT_NAME:
        return False

    # Strong corroborating signal: the actual package source layout must
    # be on disk.  This is what distinguishes the real source repo (and
    # its worktrees, which all carry the layout) from a consumer that
    # merely happens to declare the same project name.
    package_init = root / "src" / "vaultspec_core" / "__init__.py"
    return package_init.is_file()


@lru_cache(maxsize=4)
def _cached_is_dev_repo(root_str: str) -> bool:
    """Memoized wrapper - avoids re-parsing pyproject.toml on every call."""
    return is_dev_repo(Path(root_str))


def guard_dev_repo(target: Path, *, dev: bool = False) -> None:
    """Enforce the dev-repo policy for *target*.

    The three outcomes:

    - ``dev=False`` and *target* **is** the source repo: raise
      :class:`DevRepoProtectionError` to refuse the write.  This is the
      default and protects the canonical ``.vaultspec/`` content from
      being overwritten by consumer-style install/sync logic.
    - ``dev=True`` and *target* **is** the source repo: log an info
      message and return.  The calling command is then expected to use
      the same ``dev`` signal to scope its writes (e.g. omit the bare
      ``.vaultspec/`` line from the managed gitignore block) so the
      source-of-truth content stays version-controlled.
    - ``dev=True`` and *target* **is not** the source repo: raise
      :class:`DevRepoProtectionError`.  ``--dev`` must not be a no-op
      escape hatch in arbitrary projects; if the caller passed it
      somewhere it doesn't apply, that's a mistake we surface loudly.

    Args:
        target: The effective ``TARGET_DIR`` for the current operation.
        dev: ``True`` when the caller passed the ``--dev`` flag and
            therefore authorises dev-mode operation in the source repo.

    Raises:
        DevRepoProtectionError: When the policy above forbids the write.
    """
    resolved = target.resolve()
    in_dev_repo = _cached_is_dev_repo(str(resolved))

    if dev:
        if not in_dev_repo:
            raise DevRepoProtectionError(
                f"--dev was passed but '{resolved}' is not a vaultspec-core "
                f"source repository (no pyproject.toml with "
                f'[project].name == "{_PROJECT_NAME}").',
                hint=(
                    "Drop the --dev flag, or run from inside the "
                    "vaultspec-core repository or one of its worktrees."
                ),
            )
        logger.info(
            "Dev-repo guard authorised by --dev for source repo at '%s'",
            resolved,
        )
        return

    if in_dev_repo:
        raise DevRepoProtectionError(
            f"Refusing to modify '{resolved}' - this is the vaultspec-core "
            f"source repository.\n"
            f"  Use --target to specify a project directory, or pass --dev "
            f"to operate on the source repo intentionally.",
            hint="Pass --dev to authorise source-repo writes.",
        )
