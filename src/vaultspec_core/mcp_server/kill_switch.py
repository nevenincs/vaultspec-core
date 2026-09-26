"""Reading of the operator switch that disarms the stdio lifetime watchdog.

Separate from :mod:`~vaultspec_core.mcp_server.watchdog` because that module
is loaded by path, under a bare interpreter with no vaultspec-core on its
path, by the orphan workers that exercise it; it can therefore import nothing
at all beyond the standard library, not even the shared value vocabulary. The
interpretation lives here, one layer up, where the environment is read anyway.
"""

from __future__ import annotations

import logging

from ..env_values import BOOL_SHAPE, is_blank, parse_bool, rejection

__all__ = ["watchdog_disabled"]

logger = logging.getLogger(__name__)

#: The switch, named in the one message that reports a value unusable.
_KILL_SWITCH_NAME = "VAULTSPEC_STDIO_WATCHDOG"


def watchdog_disabled(kill_switch: str | None) -> bool:
    """Return whether the operator kill switch disarms the watchdog.

    A value the boolean vocabulary does not recognise warns and leaves the
    watchdog armed, rather than refusing the process as every other setting
    does. This is a protective switch: what it guards against is a server
    that outlives its client, and a typo must not be what turns the guard
    off.

    Args:
        kill_switch: The switch's value, or ``None`` when unset. Unset and
            blank both leave the watchdog armed.

    Returns:
        ``True`` only when the switch carries a false word.
    """
    if is_blank(kill_switch):
        return False
    parsed = parse_bool(str(kill_switch))
    if parsed is None:
        logger.warning(
            "watchdog: %s; the watchdog stays armed",
            rejection(_KILL_SWITCH_NAME, BOOL_SHAPE, kill_switch),
        )
        return False
    return not parsed
