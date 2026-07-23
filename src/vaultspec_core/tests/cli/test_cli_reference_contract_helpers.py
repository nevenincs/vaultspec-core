"""Cover the machinery the CLI-reference drift guards are built on.

The drift guards are only as strong as their two primitives: the option
extractor that reads a command's flags out of ``--help``, and the section parser
that reads a reference document's prose structure. A primitive that silently
returns nothing turns every guard built on it into a test that cannot fail, so
each is asserted here against the real CLI and real reference documents.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.reference_contract import (
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


def _runner() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def test_extractor_reads_flags_from_real_help_output() -> None:
    """The extractor returns a command's actual flags, not an empty set.

    A parser that matches nothing makes the option-coverage guards vacuous:
    every flag is trivially "documented" because none is ever collected. This
    pins the extractor against a command whose flag set is known from its own
    surface, so a help-rendering change that the parser stops understanding
    fails here instead of quietly disarming the guards.
    """
    cli = _runner()
    options = extract_options(help_output(cli, app, ("vault", "add")))

    assert {"--feature", "-f", "--tier", "--step", "--all-steps"} <= options
    assert "--help" in options


def test_extractor_reads_every_option_bearing_command() -> None:
    """No command with flags parses as flagless.

    Sweeps the whole live tree rather than one sample: for every leaf command
    whose help renders an Options block, the extractor must return at least one
    token from it.
    """
    cli = _runner()

    silent: list[str] = []
    for path in collect_leaf_command_paths(app):
        help_text = help_output(cli, app, path)
        if "Options" not in help_text:
            continue
        if not extract_options(help_text):
            silent.append(" ".join(path))

    assert not silent, (
        "The option extractor found no flags for these commands, whose `--help` "
        "renders an Options block:\n  - " + "\n  - ".join(sorted(silent))
    )


def test_extractor_ignores_flags_named_in_help_descriptions() -> None:
    """Only the option column counts, not flags quoted in a description.

    Several commands describe one flag in another's help text. Treating those
    mentions as accepted options would credit a command with flags it rejects
    and weaken the per-section contract into noise.
    """
    help_text = (
        "Usage: root demo [OPTIONS]\n"
        "\n"
        "Options:\n"
        "  --real <str>              Ignored unless --imaginary is also passed\n"
        "  --help                    Show this message and exit.\n"
    )
    assert extract_options(help_text) == {"--real", "--help"}


def test_section_parser_finds_the_handbook_command_sections() -> None:
    """Sections parse out of the real handbook and resolve to real commands."""
    sections = parse_command_sections(_HANDBOOK.read_text(encoding="utf-8"), app)
    assert sections, "No `### ` sections parsed out of the handbook"

    headings = {section.heading for section in sections}
    assert "vaultspec-core vault add" in headings
    assert "install" in headings

    # The bare workspace heading and the fully qualified heading both resolve.
    by_heading = {section.heading: section for section in sections}
    assert by_heading["install"].commands == (("install",),)
    assert by_heading["vaultspec-core vault add"].commands == (("vault", "add"),)


def test_section_parser_excludes_the_generated_command_index() -> None:
    """Index headings never count as prose sections.

    The generated Command Index carries its own `### ` group headings. Counting
    those as documentation would make the section contract self-satisfying: the
    index is rendered from the same command tree the contract checks against.
    """
    sections = parse_command_sections(_HANDBOOK.read_text(encoding="utf-8"), app)
    headings = {section.heading for section in sections}
    assert "Vault" not in headings
    assert "Top-level commands" not in headings


def test_group_section_only_covers_commands_its_prose_names() -> None:
    """A group heading alone does not vouch for a leaf it never mentions."""
    sections = parse_command_sections(_HANDBOOK.read_text(encoding="utf-8"), app)
    check_section = covering_section(sections, ("vault", "check", "orphans"))
    assert check_section is not None
    assert check_section.heading == "vaultspec-core vault check"

    # A leaf the group section does not name is not covered by it.
    invented = ("vault", "check", "no-such-subcommand-anywhere")
    assert covering_section(sections, invented) is None


@pytest.mark.parametrize(
    "path",
    [("vault", "edit"), ("vault", "link", "add"), ("doctor",)],
)
def test_command_options_are_scoped_to_the_command(path: tuple[str, ...]) -> None:
    """`command_options` drops global flags and keeps command-specific ones."""
    cli = _runner()
    options = command_options(cli, app, path)
    assert "--help" not in options
    assert "--target" not in options
    assert options, f"{' '.join(path)} reported no command-specific options"
