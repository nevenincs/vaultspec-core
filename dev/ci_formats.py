"""Machine-readable gate output, opt-in through one environment variable.

Every gate here reports as human-readable console text: ruff's rendered
diagnostics, ty's and basedpyright's annotated source excerpts. That is right
at a terminal and wrong in CI, where a job gets an exit code and a wall of
scrollback nobody parses - a failing lint annotates nothing on the pull request
that caused it, even though every one of these tools can emit exactly that.

Two switches, deliberately separate:

* ``GITHUB_ACTIONS`` turns on GitHub workflow annotations, which go to stdout
  and are meaningful only inside a workflow run.
* ``VAULTSPEC_CI_REPORTS`` names a directory for report artifacts.

UNSET - every local run, and any CI job that has not opted in - every command
runs exactly as it does today. The switch is additive on purpose: adopting it
must not change what a developer sees at their own terminal.

This module decides only what a tool PRINTS and where its artifact lands. It
never alters a command's exit status, and ``augment`` is a pure function, so
the mapping is tested without running any of the tools.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Names a directory for report artifacts, and enables machine-readable output.
REPORTS_ENV = "VAULTSPEC_CI_REPORTS"

#: Set by the Actions runner. Annotations are only meaningful under it.
ANNOTATIONS_ENV = "GITHUB_ACTIONS"


def annotating(env: Mapping[str, str]) -> bool:
    """Whether findings should be emitted as GitHub workflow annotations."""
    return env.get(ANNOTATIONS_ENV, "").strip().lower() == "true"


def augment(argv: Sequence[str], env: Mapping[str, str] | None = None) -> list[str]:
    """Return ``argv`` with this run's machine-readable output flags added.

    Args:
        argv: The command about to run.
        env: The environment it will run under; defaults to the process's own.

    Returns:
        The command to run - unchanged whenever annotations are not enabled, or
        the caller already chose an output format.
    """
    environment = os.environ if env is None else env
    if not argv or not annotating(environment):
        return list(argv)

    flags = " ".join(argv)
    if "--output-format" in flags or "--outputjson" in flags:
        return list(argv)

    # `ruff format --check` reports drift as a file list, not diagnostics, and
    # has no annotation format; only `ruff check` does.
    if "ruff" in argv and "check" in argv:
        return [*argv, "--output-format=github"]
    if "ty" in argv and "check" in argv:
        return [*argv, "--output-format=github"]
    if "basedpyright" in argv:
        # basedpyright has no GitHub format; its JSON is what a downstream step
        # turns into annotations.
        return [*argv, "--outputjson"]
    return list(argv)
