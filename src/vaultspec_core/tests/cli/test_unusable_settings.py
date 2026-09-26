"""An unusable setting stops a run before it writes, not after.

A value the product cannot use used to be discovered wherever it happened to
be read. For a field that is at load time, which is early enough; for a switch
consulted while printing a report it is after every file has already been
written, so the operator gets a failure exit over a workspace that was
nonetheless changed. Both entry points check the whole environment first, and
these tests drive the real executables as subprocesses with an explicit
environment to prove it.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

#: A field read when the configuration loads, and a switch read only when a
#: command prints its report. Both must refuse in the same place.
_UNUSABLE = [
    ("VAULTSPEC_IO_BUFFER_SIZE", "plenty"),
    ("VAULTSPEC_NO_HINTS", "maybe"),
]


def _fingerprint(root: Path) -> dict[str, str]:
    """Return a content fingerprint of every file under *root*."""
    prints: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            prints[str(path.relative_to(root))] = digest
    return prints


def _environment(**overrides: str) -> dict[str, str]:
    """The process environment plus *overrides*, with our own names cleared."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("VAULTSPEC_")
    }
    return {**env, **overrides}


@pytest.mark.parametrize(("name", "value"), _UNUSABLE)
def test_the_cli_refuses_before_it_writes(
    factory: WorkspaceFactory, name: str, value: str
) -> None:
    root = factory.install().path
    before = _fingerprint(root)

    result = subprocess.run(
        [sys.executable, "-m", "vaultspec_core", "sync"],
        cwd=root,
        env=_environment(**{name: value}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 1, result.stderr
    reports = [line for line in result.stderr.splitlines() if line.startswith("Error:")]
    assert len(reports) == 1, result.stderr
    assert name in reports[0]
    assert _fingerprint(root) == before


@pytest.mark.parametrize(("name", "value"), _UNUSABLE)
def test_the_mcp_server_refuses_before_it_serves(
    factory: WorkspaceFactory, name: str, value: str
) -> None:
    root = factory.install().path
    before = _fingerprint(root)

    result = subprocess.run(
        [sys.executable, "-c", "from vaultspec_core.mcp_server.app import run; run()"],
        stdin=subprocess.DEVNULL,
        env=_environment(VAULTSPEC_TARGET_DIR=str(root), **{name: value}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    reports = [line for line in result.stderr.splitlines() if line.startswith("Error:")]
    assert len(reports) == 1, result.stderr
    assert name in reports[0]
    assert result.stdout == ""
    assert _fingerprint(root) == before
