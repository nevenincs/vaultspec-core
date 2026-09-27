"""The canonical positional metavar grammar reaches only this CLI's command tree.

Typer resolves its argument class through a module global when a command tree
is built, which happens lazily. A grammar installed by rebinding that global
would rewrite the help of every other Typer application in the process, so
these tests build a foreign application after core's own tree and require it to
keep Typer's own argument class.
"""

from __future__ import annotations

from typing import Annotated

import pytest
import typer
import typer.main
from typer.core import TyperArgument, TyperGroup
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._metavar import CanonicalTyperArgument

pytestmark = [pytest.mark.unit]

_RUNNER = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def _usage_line(target: typer.Typer, *argv: str) -> str:
    result = _RUNNER.invoke(target, [*argv, "--help"])
    assert result.exit_code == 0, result.output
    return next(
        line for line in result.output.splitlines() if line.startswith("Usage:")
    )


def test_building_core_leaves_typers_argument_global_alone() -> None:
    typer.main.get_command(app)
    assert vars(typer.main)["TyperArgument"] is TyperArgument


def test_foreign_app_built_after_core_keeps_typers_argument_class() -> None:
    typer.main.get_command(app)
    foreign = typer.Typer()

    @foreign.callback()
    def main(workspace: str) -> None:
        del workspace

    @foreign.command()
    def run(project: str) -> None:
        del project

    group = typer.main.get_command(foreign)
    assert isinstance(group, TyperGroup)
    command = group.commands["run"]
    arguments = [
        param
        for param in (*group.params, *command.params)
        if param.param_type_name == "argument"
    ]
    assert [type(param) for param in arguments] == [TyperArgument, TyperArgument]


def test_core_commands_render_the_canonical_grammar() -> None:
    assert _usage_line(app, "vault", "add") == (
        "Usage: root vault add [OPTIONS] DOC_TYPE"
    )
    assert _usage_line(app, "install") == "Usage: root install [OPTIONS] [PROVIDER]"


def test_make_app_single_command_renders_the_canonical_grammar() -> None:
    single = make_app()

    @single.command()
    def run(project: Annotated[str | None, typer.Argument()] = None) -> None:
        del project

    command = typer.main.get_command(single)
    assert [type(param) for param in command.params] == [CanonicalTyperArgument]
    assert _usage_line(single) == "Usage: run [OPTIONS] [PROJECT]"


def test_make_app_group_callback_renders_the_canonical_grammar() -> None:
    grouped = make_app()

    @grouped.callback()
    def main(workspace: str) -> None:
        del workspace

    @grouped.command()
    def run() -> None:
        pass

    group = typer.main.get_command(grouped)
    assert [type(param) for param in group.params] == [CanonicalTyperArgument]
    assert _usage_line(grouped).startswith("Usage: root [OPTIONS] WORKSPACE")
