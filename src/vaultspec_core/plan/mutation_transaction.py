"""Lock-scoped transaction boundary for plan read-modify-write operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def _project_root_for_plan(path: Path) -> Path:
    """Return the project root that owns *path*, or a safe local fallback."""
    from vaultspec_core.config import get_config

    resolved = path.resolve()
    docs_dir_name = Path(get_config().docs_dir).name
    for candidate in (resolved.parent, *resolved.parents):
        if candidate.name == docs_dir_name:
            return candidate.parent
    return resolved.parent


def run_plan_mutation[T](
    path: Path,
    *,
    dry_run: bool,
    operation: Callable[[], T],
) -> T:
    """Run *operation* while holding the plan's per-document advisory lock.

    The callback owns the complete load, parse, mutate, guard, write, and
    verification sequence. Keeping that whole callback inside this boundary prevents
    two VaultSpec writers from deriving replacements from the same on-disk revision.

    Dry runs take the lock when its runtime directory already exists, but never create
    that directory solely for a preview. Applying a mutation materializes the ignored
    lock directory before acquisition so locking cannot silently degrade to a no-op.
    """
    from vaultspec_core.core.helpers import advisory_lock
    from vaultspec_core.vaultcore.edit_engine import document_lock_target

    root_dir = _project_root_for_plan(path)
    lock_target = document_lock_target(path.resolve(), root_dir)
    if not dry_run:
        lock_target.parent.mkdir(parents=True, exist_ok=True)

    with advisory_lock(lock_target):
        return operation()
