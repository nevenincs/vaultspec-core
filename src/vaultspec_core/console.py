"""Provide the shared Rich console used for user-facing CLI output.

Configures safe_box and encoding to prevent Unicode crashes on Windows
terminals that use cp1252 or similar legacy codepages.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from typing import TYPE_CHECKING, Any, TextIO

from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["configure_stdio", "get_console", "override_console", "reset_console"]

_console: Console | None = None


def _is_utf8_capable(stdout: TextIO | None = None) -> bool:
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


def _make_utf8_stdout(stdout: TextIO | None = None) -> io.TextIOWrapper:
    """Wrap stdout's underlying byte buffer with a UTF-8 text wrapper.

    This avoids UnicodeEncodeError when Rich writes Unicode characters
    (such as check-marks and block elements) to a cp1252-encoded console.
    """
    stream = sys.stdout if stdout is None else stdout
    return io.TextIOWrapper(
        stream.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )


def _console_kwargs(
    stdout: TextIO | None = None, environ: dict[str, str] | None = None
) -> dict[str, Any]:
    """Build Rich Console kwargs from real stream and environment inputs."""
    env = os.environ if environ is None else environ
    utf8 = _is_utf8_capable(stdout)
    kwargs: dict[str, Any] = {
        "highlight": False,
        "soft_wrap": True,
        "no_color": "NO_COLOR" in env,
        "safe_box": not utf8,
    }
    if not utf8:
        kwargs["file"] = _make_utf8_stdout(stdout)
        kwargs["legacy_windows"] = False
    # One terminal-geometry query per run: pin the console width at
    # construction so large render loops do not re-query the terminal size
    # for every printed line. Only pinned when a real terminal answers;
    # pipes and captured streams keep Rich's own fallback behaviour.
    if "COLUMNS" not in env:
        with contextlib.suppress(OSError, ValueError):
            kwargs["width"] = os.get_terminal_size().columns
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


@contextlib.contextmanager
def override_console(console: Console) -> Generator[None]:
    """Temporarily install ``console`` as the shared console singleton.

    Every :func:`get_console` call made anywhere in the process - including
    from code the caller does not control, such as CLI commands invoked
    in-process - returns ``console`` for the duration of the ``with``
    block. The previous singleton, including ``None`` when none had been
    constructed yet, is restored on exit, whether the block completes
    normally or raises.

    Intended for callers that need to redirect CLI output into a
    caller-owned :class:`~rich.console.Console` - for example, a recording
    console (``record=True``) used to capture ANSI output for rendering
    README screenshots or GIFs - without leaving the shared singleton
    mutated for whatever runs next in the same process.

    This mutates a bare module global with no lock or contextvar, so it is
    not safe for concurrent or reentrant use across threads or overlapping
    async tasks; nested calls on a single thread restore correctly, but
    overlapping overrides from different threads or tasks will clobber
    each other's saved state.

    Args:
        console: The console instance to install for the duration of the
            context.

    Yields:
        None.
    """
    global _console
    previous = _console
    _console = console
    try:
        yield
    finally:
        _console = previous
