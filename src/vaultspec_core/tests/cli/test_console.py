"""Tests for console singleton."""

from __future__ import annotations

import io

import pytest

from vaultspec_core.console import _console_kwargs, get_console, reset_console


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

    def test_no_color_env_var(self):
        """no_color must be True when NO_COLOR env var is set."""
        kwargs = _console_kwargs(environ={"NO_COLOR": "1"})
        assert kwargs["no_color"] is True
