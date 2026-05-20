"""Shared anchor-resolution helper for plan command handlers.

The ``insert_*`` handlers in :mod:`.step_ops`, :mod:`.phase_ops` and
:mod:`.wave_ops` - plus ``move_wave`` - all accept a mutually-exclusive
``--before`` / ``--after`` pair. This module owns the single copy of
that validation so the call sites cannot drift apart.
"""

from __future__ import annotations


def resolve_exactly_one_anchor(
    before: str | None,
    after: str | None,
    *,
    op: str,
    error: type[Exception],
) -> str:
    """Return the single anchor id from a mutually-exclusive pair.

    Args:
        before: The ``--before`` anchor id, or ``None``.
        after: The ``--after`` anchor id, or ``None``.
        op: Handler name used in error messages (e.g. ``"insert_step"``).
        error: Exception type raised when the pair is invalid.

    Returns:
        The non-``None`` anchor id.

    Raises:
        error: When neither or both of *before* / *after* are supplied.
    """
    if before is None and after is None:
        raise error(f"{op} requires either --before or --after")
    if before is not None and after is not None:
        raise error(f"{op} accepts at most one of --before / --after")

    anchor_id = before if before is not None else after
    if anchor_id is None:  # unreachable; satisfies the type checker
        raise error(f"{op} received None anchor after exactly-one validation")
    return anchor_id
