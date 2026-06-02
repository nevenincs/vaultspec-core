"""Provide the shared Rich console used for user-facing CLI output.

Configures safe_box and encoding to prevent Unicode crashes on Windows
terminals that use cp1252 or similar legacy codepages.
"""

from __future__ import annotations

import io
import os
import sys

from rich.console import Console

__all__ = ["configure_stdio", "get_console", "reset_console"]

_console: Console | None = None


def _is_utf8_capable(stdout=None) -> bool:
    """Check if stdout can handle UTF-8 output."""
    stream = sys.stdout if stdout is None else stdout
    encoding = getattr(stream, "encoding", None) or ""
    if not encoding:
        return True
    return encoding.lower().replace("-", "") in ("utf8", "utf_8")


def configure_stdio() -> None:
    """Reconfigure ``sys.stdout``/``sys.stderr`` to UTF-8 at the CLI entry.

    The shared Rich console (:func:`get_console`) already wraps stdout in a
    UTF-8 writer, but ``typer.echo`` / ``click.echo`` write directly to the
    interpreter's ``sys.stdout``. On a Windows console whose encoding is
    ``cp1252`` (the default), echoing user-controlled content that contains
    non-ASCII glyphs (such as ``->`` rendered as ``\\u2192`` from plan
    ``action`` strings) raised :class:`UnicodeEncodeError` and crashed the
    command (issue #111).

    Reconfiguring the standard streams to UTF-8 with ``errors="replace"`` once,
    at the process entry point, makes every ``typer.echo`` call safe without
    routing each through the Rich console. Streams already UTF-8 (the common
    POSIX case and redirected pipes) are left untouched, and streams that do
    not support reconfiguration are skipped silently.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None or _is_utf8_capable(stream):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            # Stream does not support reconfiguration (already detached, a
            # non-seekable wrapper, or a captured test buffer); leave it as-is.
            continue


def _make_utf8_stdout(stdout=None) -> io.TextIOWrapper:
    """Wrap stdout's underlying byte buffer with a UTF-8 text wrapper.

    This avoids UnicodeEncodeError when Rich writes Unicode characters
    (such as check-marks and block elements) to a cp1252-encoded console.
    """
    stream = sys.stdout if stdout is None else stdout
    return io.TextIOWrapper(
        stream.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )


def _console_kwargs(stdout=None, environ: dict[str, str] | None = None) -> dict:
    """Build Rich Console kwargs from real stream and environment inputs."""
    env = os.environ if environ is None else environ
    utf8 = _is_utf8_capable(stdout)
    kwargs: dict = {
        "highlight": False,
        "soft_wrap": True,
        "no_color": "NO_COLOR" in env,
        "safe_box": not utf8,
    }
    if not utf8:
        kwargs["file"] = _make_utf8_stdout(stdout)
        kwargs["legacy_windows"] = False
    return kwargs


def get_console() -> Console:
    """Return the shared stdout Rich console singleton.

    On non-UTF-8 terminals, wraps stdout in a UTF-8 writer and enables
    safe_box to prevent UnicodeEncodeError from box-drawing and symbol
    characters.
    """
    global _console
    if _console is None:
        _console = Console(**_console_kwargs())
    return _console


def reset_console() -> None:
    """Reset the stdout console singleton.

    Allows a fresh Console to be created on the next get_console() call.
    Primarily useful in tests that need a specific terminal width.
    """
    global _console
    _console = None
