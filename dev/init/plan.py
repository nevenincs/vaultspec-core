"""What initializing THIS repository means.

The only file in :mod:`dev.init` that differs between repositories. Everything
here is data: the host tools the workstation must already provide, the steps
each phase runs, and - the part that is easy to get wrong - the inputs whose
change makes a phase stale and the artifacts whose absence does the same.

``vaultspec-core`` is a single-language repository. Its initialization is a
locked `uv` sync, then the framework enrollment that a fresh worktree
specifically needs: `.vaultspec/` is tracked but its install manifest,
`.vaultspec/providers.json`, is not, and the diagnosis engine reads
"config without manifest" as CORRUPTED. ``vaultspec-core install --skip core``
rebuilds the manifest and renders every provider's configuration from the
tracked `.vaultspec/` without seeding it. ``--force`` would also copy the
package's bundled builtins over the tracked ones, so a fresh worktree would
start with modified files whenever the two differ; bringing `.vaultspec/` up
to date is a change to commit, not a side effect of initializing.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import sys
from typing import Final

from dev.init.contract import Phase, Step
from dev.init.probe import Requirement

#: The ephemeral interpreter `init` is running on. Steps that are themselves
#: Python reuse it rather than assuming a `python` on PATH, because the whole
#: premise of this package is that the environment does not exist yet.
PY: Final = sys.executable

#: What the workstation must provide before `init` can do anything. `just` is
#: absent from this list on purpose: if `just` were missing, the recipe that
#: reached this code could not have run.
REQUIREMENTS: Final[tuple[Requirement, ...]] = (
    Requirement(
        command="uv",
        purpose="It resolves the locked Python environment.",
        install_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
)

#: Steps that run before any phase, on every entry point. Materializing `.env`
#: belongs here rather than in `init-tools` because a worktree without one is
#: under-configured for tools that read it, including `just` itself in the
#: repositories that set `dotenv-load`. The rule is uniform across the fleet.
#: A linked worktree also carries the values already set in the main
#: worktree's `.env`, so a fresh worktree has the operator's hosted-search key
#: instead of a blank placeholder.
PREFLIGHT: Final[tuple[Step, ...]] = (
    Step(
        name="dotenv",
        argv=(
            PY,
            "-m",
            "dev.init.dotenv",
            ".env.example",
            ".env",
            "--from-main-worktree",
        ),
        summary=(
            "Provision .env from .env.example when it is absent, carrying the "
            "values set in the main worktree's .env."
        ),
    ),
)

PYTHON = Phase(
    name="python",
    summary="Resolve the locked Python development toolchain into .venv.",
    steps=(
        Step(
            name="uv-sync",
            argv=("uv", "sync", "--locked", "--group", "dev"),
            summary="Install the locked dev dependency group.",
        ),
    ),
    inputs=("uv.lock", "pyproject.toml", ".python-version"),
    artifacts=(".venv",),
)

NODE = Phase(
    name="node",
    summary="Restore the pinned Node dependency graph.",
    skip_reason="this repository has no Node dependency graph",
)

# Deliberately no git-hook step. The hook runner stashes a worktree's unstaged
# changes for the length of every commit and restores them afterwards, and in a
# worktree several writers share, an edit landing inside that window is lost on
# restore. The gates run in CI and on demand instead.
TOOLS = Phase(
    name="tools",
    summary="Enroll the Vaultspec framework and provision actionlint.",
    steps=(
        Step(
            name="framework-install",
            argv=(
                "uv",
                "run",
                "--no-sync",
                "vaultspec-core",
                "install",
                "--skip",
                "core",
            ),
            summary=(
                "Rebuild .vaultspec/providers.json and render the providers "
                "from the tracked .vaultspec/."
            ),
        ),
        Step(
            name="actionlint-install",
            argv=(
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "dev.actionlint",
                "--install",
            ),
            summary="Provision the pinned actionlint the workflow check uses.",
        ),
    ),
    # The sources the provider render reads, so pulling a changed rule or skill
    # re-renders the providers instead of leaving them stale until `uv.lock`
    # next moves.
    inputs=(
        "uv.lock",
        ".vaultspec/agents",
        ".vaultspec/hooks",
        ".vaultspec/mcps",
        ".vaultspec/rules",
        ".vaultspec/skills",
        ".vaultspec/system",
        ".vaultspec/triggers",
        ".vaultspec/workspace.json",
    ),
    artifacts=(".vaultspec/providers.json",),
)

#: The phases, keyed by name. The runner reads this and nothing else.
PHASE_PLAN: Final[dict[str, Phase]] = {
    "python": PYTHON,
    "node": NODE,
    "tools": TOOLS,
}
