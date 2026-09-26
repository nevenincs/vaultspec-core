"""Configure process-wide logging for vault/spec-core entry surfaces.

This module centralizes RichHandler-based stderr logging setup and reset
behavior for CLI and MCP runtime entrypoints. It exists to keep diagnostic
output consistent without mixing it into normal user-facing stdout surfaces.

Usage:
    Call `configure_logging(...)` at process bootstrap to install the desired
    logging level, handler behavior, and output stream policy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from rich.console import Console
from rich.logging import RichHandler

from .config import VAULTSPEC_LOG_LEVEL, env_source, env_value
from .core.exceptions import ConfigurationError
from .env_values import rejection

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .config import ConfigVariable

__all__ = [
    "LOG_LEVELS",
    "configure_logging",
    "get_console",
    "reset_logging",
    "resolve_log_level",
]

#: The level names accepted anywhere a level is named, most verbose first.
LOG_LEVELS: Final = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Shared Rich console instance (stderr, no syntax highlighting)
_console: Console | None = None

# Global flag to prevent multiple configurations
_configured: bool = False


def get_console() -> Console:
    """Return the shared Rich console singleton (stderr, no highlighting).

    Creates the instance on first call.

    Returns:
        The shared :class:`rich.console.Console` writing to ``stderr``.
    """
    global _console
    if _console is None:
        _console = Console(stderr=True, highlight=False)
    return _console


def reset_logging() -> None:
    """Reset the logging configuration flag.

    Allows :func:`configure_logging` to be called again.  Primarily used for
    testing logging dispatch.
    """
    global _configured
    _configured = False


def resolve_log_level(
    *,
    debug: bool = False,
    verbose: bool = False,
    variable: ConfigVariable = VAULTSPEC_LOG_LEVEL,
    default: str = "WARNING",
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve the level a process logs at, over the one shared ladder.

    The invocation first - ``--debug``, then ``--verbose`` - then the session
    environment, then the caller's own default. A package passes its own
    level entry, whose framework fallback reaches ``VAULTSPEC_LOG_LEVEL``,
    and its own default: a daemon whose output is a managed log legitimately
    ships a more verbose one than a CLI a person is watching.

    Args:
        debug: Whether the invocation asked for debug logging.
        verbose: Whether the invocation asked for verbose logging. ``debug``
            outranks it: asking for both asks for the more verbose of the two.
        variable: The calling package's level entry.
        default: The level to use when nothing else names one.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        One of :data:`LOG_LEVELS`.

    Raises:
        ConfigurationError: If the variable names a level that does not
            exist. Silently logging at some other level would hide exactly
            the diagnostics the operator was asking for.
        ValueError: If *variable* is not a registered entry.
    """
    if debug:
        return "DEBUG"
    if verbose:
        return "INFO"
    supplied = env_value(variable, environ)
    if supplied is None:
        return default.upper()
    named = supplied.upper()
    if named not in LOG_LEVELS:
        entry = env_source(variable, environ) or variable
        accepted = "one of " + ", ".join(LOG_LEVELS)
        raise ConfigurationError(
            str(rejection(entry.env_name, accepted, supplied)),
            hint="Level names are not case-sensitive.",
        )
    return named


def configure_logging(
    level: str | int | None = None,
    debug: bool = False,
    quiet: bool = False,
) -> None:
    """Configure the root logger with a RichHandler.

    Sets the log level from the provided arguments, or through
    :func:`resolve_log_level` when none names one.  Prevents re-configuration
    unless :func:`reset_logging` is called.

    Args:
        level: Explicit log level (e.g. ``logging.INFO`` or ``"DEBUG"``).
        debug: When ``True``, forces level to ``DEBUG`` and enables rich
            tracebacks with local variables.
        quiet: When ``True``, forces level to ``WARNING``.
    """
    global _configured
    if _configured:
        return

    # 1. Resolve level
    if debug:
        resolved_level = logging.DEBUG
    elif quiet:
        resolved_level = logging.WARNING
    elif level is not None:
        if isinstance(level, str):
            resolved_level = getattr(logging, level.upper(), logging.INFO)
        else:
            resolved_level = level
    else:
        # Nothing was named here, so the shared ladder answers: the session
        # environment, then this surface's own shipped default.
        named = resolve_log_level(default=str(VAULTSPEC_LOG_LEVEL.default))
        resolved_level = getattr(logging, named)

    # 2. Configure root logger
    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Clear any existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # 3. Add RichHandler
    console = get_console()
    handler = RichHandler(
        console=console,
        show_time=debug,
        show_path=debug,
        rich_tracebacks=True,
        tracebacks_show_locals=debug,
        markup=False,
    )
    handler.setLevel(resolved_level)
    root.addHandler(handler)

    _configured = True
