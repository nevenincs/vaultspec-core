"""The next action ``vault add plan`` suggests is a command that runs.

A new plan has no structure yet, and the container it needs first depends on
its tier. Each test scaffolds a plan at one tier, fills the hint's
placeholders the way a reader would, runs the command it names through the
real CLI, and requires it to succeed.
"""

from __future__ import annotations

import json
import shlex
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

pytestmark = [pytest.mark.integration]

#: What a reader substitutes for each placeholder a plan hint may carry.
_FILLS = {
    "<action>": "Add the search index",
    "<path>": "src/search.py",
    "<title>": "Foundation",
    "<intent>": "Lay the groundwork the later Steps build on.",
}


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_the_hint_after_a_new_plan_runs(
    runner: CliRunner, synthetic_project: Path, tier: str
) -> None:
    target = ["--target", str(synthetic_project)]
    add_plan = ["vault", "add", "plan", "--feature", "hint-check", "--tier", tier]
    created = runner.invoke(app, [*target, *add_plan, "--json"])
    assert created.exit_code == 0, created.output

    command = json.loads(created.stdout)["hints"]["command"]
    for placeholder, value in _FILLS.items():
        command = command.replace(placeholder, value)
    program, *args = shlex.split(command)
    assert program == "vaultspec-core", command

    followed = runner.invoke(app, [*target, *args])
    assert followed.exit_code == 0, f"{command}\n{followed.output}"
