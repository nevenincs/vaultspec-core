"""The help of each executable names the command a user typed.

These run the real launch shapes in a subprocess rather than calling the Typer
apps directly, because the defect they cover lives entirely in ``sys.argv[0]``
and a direct call does not have one. PyApp starts the release binaries the same
two ways: the CLI as ``python -m vaultspec_core`` and the MCP server as
``python -c``. Both used to render that launcher as the program name - the CLI
announced ``Usage: python -m vaultspec_core`` and the MCP server ``Usage: -c``
- so the shipped binaries told users to type something that does not exist.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from vaultspec_core.cli._app import CLI_PROG_NAME, MCP_PROG_NAME

pytestmark = [pytest.mark.integration]

#: The ``python -c`` form PyApp uses for a console-script entry point.
MCP_LAUNCH = "from vaultspec_core.mcp_server.app import run; run()"


def _usage(*argv: str) -> str:
    """Return the first line of ``--help`` from a real subprocess launch."""
    completed = subprocess.run(
        [sys.executable, *argv, "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()[0]


def test_module_launch_names_the_installed_cli_command() -> None:
    assert _usage("-m", "vaultspec_core") == (
        f"Usage: {CLI_PROG_NAME} [OPTIONS] COMMAND [ARGS]..."
    )


def test_console_script_launch_names_the_installed_mcp_command() -> None:
    assert _usage("-c", MCP_LAUNCH) == (
        f"Usage: {MCP_PROG_NAME} [OPTIONS] COMMAND [ARGS]..."
    )


@pytest.mark.parametrize(
    ("argv", "shipped"),
    [
        (("-m", "vaultspec_core"), "Usage: python -m vaultspec_core [OPTIONS]"),
        (("-c", MCP_LAUNCH), "Usage: -c [OPTIONS]"),
    ],
)
def test_no_help_renders_the_usage_line_that_shipped(
    argv: tuple[str, ...], shipped: str
) -> None:
    """The two usage lines these launches actually produced, pinned.

    Asserting the correct name above cannot distinguish a fix from Click
    happening to derive something that matches; these are the strings a user
    of v0.2.4 saw, so a regression to either is named rather than described.
    Matched as whole lines: ``-c`` is a substring of ``vaultspec-core-mcp``,
    and a containment check here passes the bug it is looking for.
    """
    assert not _usage(*argv).startswith(shipped)
