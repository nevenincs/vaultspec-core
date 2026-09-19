"""Split ``.vaultspec/hooks/`` into provider hooks and lifecycle triggers.

Introduced for vaultspec-core 0.2.4. Until this release one directory held two
unrelated systems, told apart only by sniffing the ``event`` value: canonical
agent-runtime events (``pre_tool_use``, ``session_start``, ...) belonged to the
provider renderer, and vaultspec's own lifecycle events (``config.synced``,
...) belonged to the trigger engine. Two loaders reading one directory meant
each silently skipped the other's files, so ``spec hooks status`` under-reported
and the loaders' vocabularies could drift apart unnoticed.

After the split ``.vaultspec/hooks/`` is provider hooks alone and
``.vaultspec/triggers/`` is lifecycle triggers alone. Each loader reads its own
directory and warns on an event outside its own vocabulary, so a typo surfaces
instead of being silently reassigned to the other lane.

This migration relocates the lifecycle files. It is deliberately conservative:
only a file whose ``event`` is a known lifecycle event moves. A canonical
provider event stays, and so does anything unrecognised or unparseable - the
migration would rather leave a file where its author put it than guess a lane
from a typo.

Both lifecycle events retired in this same release (``vault.document.created``
and ``audit.completed``, neither of which was ever fired) are still recognised
here. They are lifecycle files by origin, and moving them puts them in front of
the trigger loader, which reports them as unsupported. Leaving them behind
would strand them in a directory whose loader has no opinion about them at all.

Consent is keyed by resolved directory path, so a relocated trigger loses its
grant and must be re-approved. That is the fail-closed design working as
intended, and the migration says so in its summary rather than trying to carry
the grant across.

See also:
    :mod:`vaultspec_core.migrations` for the registry driver.
    :mod:`vaultspec_core.triggers` for the lifecycle engine.
    :mod:`vaultspec_core.core.provider_hooks` for the provider renderer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import Migration, MigrationError, MigrationResult, MigrationScope

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MIGRATION", "migrate", "preview"]

logger = logging.getLogger(__name__)

_TARGET_VERSION = "0.2.4"
_NAME = "trigger_split"

# Pinned to the vocabulary as it stood when the directories were shared, not
# imported from the live engine. A migration classifies historical files, so it
# must keep recognising events the current release no longer supports.
_LIFECYCLE_EVENTS = frozenset(
    {
        "vault.document.created",
        "config.synced",
        "audit.completed",
    }
)

# Likewise pinned: the canonical provider events at the time of the split.
_PROVIDER_EVENTS = frozenset(
    {
        "pre_tool_use",
        "post_tool_use",
        "user_prompt_submit",
        "session_start",
        "session_end",
        "stop",
        "notification",
    }
)


def _event_of(path: Path) -> str | None:
    """Return the ``event`` value of a hook source file, or ``None``.

    ``None`` covers every case where the lane cannot be established from the
    file itself: unreadable, not valid YAML, not a mapping, or carrying no
    string ``event``. All of them leave the file in place.
    """
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Migration %s: cannot parse %s", _NAME, path.name, exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    event = data.get("event")
    return event if isinstance(event, str) else None


def _classify(hooks_dir: Path) -> tuple[list[Path], list[Path]]:
    """Partition the shared directory into files to move and files to leave.

    Returns ``(lifecycle, unclassified)``. Canonical provider files are in
    neither list: they are already where they belong and need no report.
    """
    lifecycle: list[Path] = []
    unclassified: list[Path] = []
    for ext in ("*.yaml", "*.yml"):
        for path in sorted(hooks_dir.glob(ext)):
            event = _event_of(path)
            if event in _LIFECYCLE_EVENTS:
                lifecycle.append(path)
            elif event not in _PROVIDER_EVENTS:
                unclassified.append(path)
    return lifecycle, unclassified


def preview(workspace: Path) -> list[Path]:
    """Return every path this migration would delete: always none.

    Relocation is a rename, so nothing is unlinked and no content is lost. The
    entry still declares a preview rather than leaving it unset, because an
    unset preview reads as "cannot say what it deletes" - which is a different
    and much weaker claim than "deletes nothing".

    Args:
        workspace: Workspace root directory.

    Returns:
        An empty list.
    """
    del workspace
    return []


def migrate(workspace: Path) -> MigrationResult:
    """Move lifecycle trigger files out of ``.vaultspec/hooks/``.

    Args:
        workspace: Workspace root directory.

    Returns:
        :class:`MigrationResult` whose ``counts`` carries ``moved`` and
        ``left`` - the latter being files whose lane could not be established.

    Raises:
        MigrationError: When a file cannot be moved, or when a name is already
            taken in the destination. The driver propagates the exception
            unchanged so the manifest version is not bumped and the next
            invocation retries.
    """
    from ..core.enums import Resource

    counts = {"moved": 0, "left": 0}

    vaultspec = workspace / ".vaultspec"
    hooks_dir = vaultspec / Resource.HOOKS.value
    triggers_dir = vaultspec / Resource.TRIGGERS.value

    if not hooks_dir.is_dir():
        return MigrationResult(
            name=_NAME,
            target_version=_TARGET_VERSION,
            summary="no .vaultspec/hooks/ directory; nothing to migrate",
            counts=counts,
        )

    lifecycle, unclassified = _classify(hooks_dir)
    counts["left"] = len(unclassified)

    if not lifecycle:
        summary = "no lifecycle triggers in .vaultspec/hooks/; nothing to move"
        if unclassified:
            summary += (
                f" ({len(unclassified)} file(s) left in place: "
                "event is neither a provider hook nor a lifecycle trigger)"
            )
        return MigrationResult(
            name=_NAME,
            target_version=_TARGET_VERSION,
            summary=summary,
            counts=counts,
        )

    for path in lifecycle:
        destination = triggers_dir / path.name
        if destination.exists():
            raise MigrationError(
                f"{_NAME}: cannot move {path.name} to "
                f"{Resource.TRIGGERS.value}/: destination already exists"
            )

    try:
        triggers_dir.mkdir(parents=True, exist_ok=True)
        for path in lifecycle:
            path.replace(triggers_dir / path.name)
    except OSError as exc:
        raise MigrationError(
            f"{_NAME}: failed to move lifecycle triggers into {triggers_dir}: {exc}"
        ) from exc

    counts["moved"] = len(lifecycle)
    summary = (
        f"moved {len(lifecycle)} lifecycle "
        f"{'trigger' if len(lifecycle) == 1 else 'triggers'} to "
        f".vaultspec/{Resource.TRIGGERS.value}/; "
        "re-approve them with `vaultspec-core spec triggers trust`"
    )
    if unclassified:
        summary += (
            f" ({len(unclassified)} file(s) left in place: "
            "event is neither a provider hook nor a lifecycle trigger)"
        )
    logger.info("Migration %s: %s", _NAME, summary)
    return MigrationResult(
        name=_NAME,
        target_version=_TARGET_VERSION,
        summary=summary,
        counts=counts,
    )


MIGRATION = Migration(
    target_version=_TARGET_VERSION,
    name=_NAME,
    migrate=migrate,
    preview=preview,
    # Deciding which directory a lifecycle trigger lives in is precisely what
    # decides where a freshly authored one lands, so an authoring verb runs
    # this and only this. It relocates within .vaultspec/ and touches no
    # .vault/ document; nothing is deleted, so no snapshot is needed.
    scope=MigrationScope.WRITE_PLACEMENT,
)
