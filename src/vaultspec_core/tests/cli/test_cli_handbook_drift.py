"""Guard against drift between the CLI command surface and `docs/CLI.md`.

Three contracts, in tightening order. Mention: every command name and every
non-global flag appears somewhere in the handbook. Section: every command in the
generated Command Index also has a hand-written ``### `` prose section a reader
can land on, either its own or a group section that names it. Locality: every
one of a command's flags is explained inside that section, not merely somewhere
in a two-thousand-line file.

The section contract is the one that catches the drift the mention contract
cannot see. The Command Index is generated from the live command tree, so a new
command appears there the moment it is registered - and a reader following the
index into the body finds nothing. Without this guard that gap is invisible to
CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.reference_contract import (
    GLOBAL_FLAGS,
    collect_group_paths,
    collect_leaf_command_paths,
    command_options,
    covering_section,
    extract_options,
    help_output,
    parse_command_sections,
)

pytestmark = [pytest.mark.integration]


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HANDBOOK = _REPO_ROOT / "docs" / "CLI.md"

_REGENERATE_HINT = (
    "Add a `### ` section for it in docs/CLI.md, in the shape of its "
    "neighbours: a usage fence, a short narrative, then `#### Arguments`, "
    "`#### Options`, and `#### Examples` grounded in the command's `--help`."
)


def _runner() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def test_handbook_exists() -> None:
    assert _HANDBOOK.is_file(), f"Missing handbook at {_HANDBOOK}"


def test_every_cli_command_is_documented() -> None:
    handbook_text = _HANDBOOK.read_text(encoding="utf-8")
    leaf_paths = collect_leaf_command_paths(app)
    group_paths = collect_group_paths(app)
    assert leaf_paths, "CLI tree is empty; Typer app failed to register commands"

    missing: list[str] = []
    for path in leaf_paths + group_paths:
        leaf = path[-1]
        full = " ".join(path)
        if leaf in handbook_text or full in handbook_text:
            continue
        missing.append(full)

    assert not missing, (
        "The following CLI commands are registered in code but not mentioned in "
        f"{_HANDBOOK.relative_to(_REPO_ROOT)}:\n  - " + "\n  - ".join(sorted(missing))
    )


def test_every_cli_option_is_documented() -> None:
    handbook_text = _HANDBOOK.read_text(encoding="utf-8")
    cli = _runner()

    missing: list[str] = []
    for path in collect_leaf_command_paths(app):
        help_text = help_output(cli, app, path)
        for option in sorted(extract_options(help_text)):
            if option in GLOBAL_FLAGS:
                continue
            if option in handbook_text:
                continue
            missing.append(f"{' '.join(path)}  {option}")

    assert not missing, (
        "The following CLI options appear in `--help` but are not mentioned "
        f"anywhere in {_HANDBOOK.relative_to(_REPO_ROOT)}:\n  - "
        + "\n  - ".join(sorted(missing))
    )


def test_every_indexed_command_has_a_prose_section() -> None:
    """Every command in the Command Index has a prose section behind it.

    The Command Index is rendered from the live command tree, so every
    registered command is listed there whether or not anyone wrote about it.
    This asserts the other half: that following an index entry into the body
    lands the reader on a `### ` section, either the command's own or a group
    section whose prose names the command.
    """
    handbook_text = _HANDBOOK.read_text(encoding="utf-8")
    sections = parse_command_sections(handbook_text, app)
    assert sections, "No `### ` command sections parsed out of the handbook"

    leaf_paths = collect_leaf_command_paths(app)
    assert leaf_paths, "CLI tree is empty; Typer app failed to register commands"

    missing = [
        " ".join(path)
        for path in leaf_paths
        if covering_section(sections, path) is None
    ]

    assert not missing, (
        "The following commands have a Command Index entry in "
        f"{_HANDBOOK.relative_to(_REPO_ROOT)} but no `### ` prose section:\n  - "
        + "\n  - ".join(sorted(missing))
        + f"\n\n{_REGENERATE_HINT}"
    )


def test_every_option_is_documented_in_its_own_section() -> None:
    """A command's flags are explained where the command is explained.

    The whole-file mention contract passes as soon as a flag name occurs
    anywhere, including in an unrelated command's section. This asserts the
    locality a reader actually depends on: the section documenting a command
    spells out that command's own flags.
    """
    handbook_text = _HANDBOOK.read_text(encoding="utf-8")
    sections = parse_command_sections(handbook_text, app)
    cli = _runner()

    missing: list[str] = []
    for path in collect_leaf_command_paths(app):
        section = covering_section(sections, path)
        if section is None:
            # Reported by the section contract above; not double-counted here.
            continue
        for option in sorted(command_options(cli, app, path)):
            if option not in section.text:
                missing.append(
                    f"{' '.join(path)}  {option}  (section: {section.heading})"
                )

    assert not missing, (
        "The following options are missing from the handbook section that "
        "documents their command:\n  - " + "\n  - ".join(sorted(missing))
    )
