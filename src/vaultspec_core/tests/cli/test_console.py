"""Tests for console singleton."""

from __future__ import annotations

import io
import sys

import pytest
import typer

from vaultspec_core.console import (
    _console_kwargs,
    configure_stdio,
    get_console,
    reset_console,
)


@pytest.mark.unit
class TestConsole:
    def setup_method(self):
        reset_console()

    def test_console_singleton_returns_same_instance(self):
        c1 = get_console()
        c2 = get_console()
        assert c1 is c2

    def test_console_reset_creates_new_instance(self):
        c1 = get_console()
        reset_console()
        c2 = get_console()
        assert c1 is not c2

    def test_console_can_print_unicode(self, capsys):
        """Console must handle Unicode without UnicodeEncodeError."""
        console = get_console()
        # These are the exact characters that caused the cp1252 crash
        console.print("\u2713")  # check mark
        console.print("\u26a0")  # warning
        console.print("\u2588")  # full block
        console.print("\u2591")  # light shade
        # If we get here without UnicodeEncodeError, the test passes

    def test_safe_box_on_non_utf8_terminal(self):
        """safe_box must be True when terminal encoding is not UTF-8."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        kwargs = _console_kwargs(stdout=stream, environ={})

        assert kwargs["safe_box"] is True
        assert kwargs["legacy_windows"] is False

    def test_unknown_encoding_stream_uses_rich_default_capture(self):
        """Streams without an encoding should not be wrapped away from capture."""
        stream = io.StringIO()
        kwargs = _console_kwargs(stdout=stream, environ={})

        assert kwargs["safe_box"] is False
        assert "file" not in kwargs

    def test_no_color_env_var(self):
        """no_color must be True when NO_COLOR env var is set."""
        kwargs = _console_kwargs(environ={"NO_COLOR": "1"})
        assert kwargs["no_color"] is True


@pytest.mark.unit
class TestConfigureStdio:
    """configure_stdio must make typer.echo safe on cp1252 streams (issue #111)."""

    def test_raw_cp1252_stream_cannot_encode_arrow(self):
        """Document the pre-fix failure: cp1252 cannot encode the arrow glyph."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with pytest.raises(UnicodeEncodeError):
            stream.write("→")
            stream.flush()

    def test_configure_stdio_makes_cp1252_stdout_utf8_safe(self):
        """After configure_stdio, typer.echo of non-ASCII succeeds via UTF-8."""
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252", line_buffering=True)
        original = sys.stdout
        sys.stdout = stream
        try:
            configure_stdio()
            assert sys.stdout.encoding.lower().replace("-", "") in ("utf8", "utf_8")
            # The exact surface from the bug: a plan action containing "->".
            typer.echo("- [ ] `P01.S01` - migrate → done; `src/a.py`.")
            sys.stdout.flush()
        finally:
            sys.stdout = original
        assert "→".encode() in buffer.getvalue()

    def test_configure_stdio_leaves_utf8_stream_untouched(self):
        """A stream already UTF-8 is not reconfigured or replaced."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        original = sys.stdout
        sys.stdout = stream
        try:
            configure_stdio()
            assert sys.stdout is stream
            assert sys.stdout.encoding.lower().replace("-", "") in ("utf8", "utf_8")
        finally:
            sys.stdout = original
