"""Guard against drift between the CLI surface and the bundled reference.

The bundled machine-facing reference at
`src/vaultspec_core/builtins/reference/cli.md` is hand-authored. This module
walks the live Typer command tree, invokes ``--help`` on every visible leaf
command, and asserts that every command name and every non-global option name
appears in the bundled reference. It mirrors `test_cli_handbook_drift` for the
bundled reference so a new command, subcommand, or flag cannot land without a
corresponding reference update.

The bundled reference is a terse agent-facing catalog that consolidates whole
command families into running prose, so the per-command section contract the
handbook carries does not apply here; coverage is the contract this surface
owes.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vaultspec_core.builtins import builtins_root
from vaultspec_core.cli import app
from vaultspec_core.tests.cli.reference_contract import (
    GLOBAL_FLAGS,
    collect_group_paths,
    collect_leaf_command_paths,
    extract_options,
    help_output,
)

pytestmark = [pytest.mark.integration]


# The bundled reference ships inside the distributed package alongside the
# other builtins, so it is addressed through the package's own accessor rather
# than by walking out to a repository root that exists only in a checkout.
_BUILTINS_ROOT = builtins_root()
_REFERENCE = _BUILTINS_ROOT / "reference" / "cli.md"


def test_reference_exists() -> None:
    assert _REFERENCE.is_file(), f"Missing bundled CLI reference at {_REFERENCE}"


def test_every_cli_command_is_in_reference() -> None:
    reference_text = _REFERENCE.read_text(encoding="utf-8")
    leaf_paths = collect_leaf_command_paths(app)
    group_paths = collect_group_paths(app)
    assert leaf_paths, "CLI tree is empty; Typer app failed to register commands"

    missing: list[str] = []
    for path in leaf_paths + group_paths:
        leaf = path[-1]
        full = " ".join(path)
        if leaf in reference_text or full in reference_text:
            continue
        missing.append(full)

    assert not missing, (
        "The following CLI commands are registered in code but not mentioned "
        f"in {_REFERENCE.relative_to(_BUILTINS_ROOT)}:\n  - "
        + "\n  - ".join(sorted(missing))
    )


def test_every_cli_option_is_in_reference() -> None:
    reference_text = _REFERENCE.read_text(encoding="utf-8")
    cli = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})

    missing: list[str] = []
    for path in collect_leaf_command_paths(app):
        help_text = help_output(cli, app, path)
        for option in sorted(extract_options(help_text)):
            if option in GLOBAL_FLAGS:
                continue
            if option in reference_text:
                continue
            missing.append(f"{' '.join(path)}  {option}")

    assert not missing, (
        "The following CLI options appear in `--help` but are not mentioned "
        f"anywhere in {_REFERENCE.relative_to(_BUILTINS_ROOT)}:\n  - "
        + "\n  - ".join(sorted(missing))
    )
