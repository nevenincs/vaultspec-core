"""Install the committed git hooks, or say precisely why they were not.

A repository that commits a `.pre-commit-config.yaml` and installs nothing has
a gate that exists on paper. Every checkout is one `git commit` away from
skipping every hook in it, and nothing announces that.

The honest options are not "install it" and "stay quiet". They are:

* a hook runner is reachable, so install the hook and say so;
* no hook runner is declared by this repository's dependencies, so say THAT,
  by name, every time `init` runs.

The second case is deliberately not fixed by installing a runner from the
network. Adding a dependency is a change to the lockfile and belongs in a
commit somebody reviewed, not in a bootstrap that quietly reaches for PyPI. So
this step is advisory: it reports the gap, `init` still succeeds, and the gap
is visible in every run's report until a lockfile change closes it.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

#: The hook runners this fleet uses, most preferred first. `prek` is the
#: reimplementation the repositories that DO declare a runner have settled on;
#: `pre-commit` is accepted because a workstation may still carry it.
RUNNERS = ("prek", "pre-commit")


def _venv_bin(repo_root: Path) -> Path:
    """Return the virtual environment's executable directory.

    Args:
        repo_root: The worktree root.

    Returns:
        ``.venv/Scripts`` on Windows, ``.venv/bin`` elsewhere.
    """
    return repo_root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")


def _find(repo_root: Path) -> tuple[str, list[str]] | None:
    """Locate a hook runner.

    The environment is searched before ``PATH`` on purpose: a runner pinned by
    this repository's lockfile is the one whose version the hooks were written
    against, and a globally installed one is a coincidence.

    Args:
        repo_root: The worktree root.

    Returns:
        The runner's name and the argv prefix that invokes it, or ``None``.
    """
    binaries = _venv_bin(repo_root)
    for runner in RUNNERS:
        for name in (runner, f"{runner}.exe"):
            candidate = binaries / name
            if candidate.is_file():
                return runner, [str(candidate)]
    for runner in RUNNERS:
        if shutil.which(runner) is not None:
            return runner, [runner]
    return None


def install(repo_root: Path, config: Path) -> int:
    """Install the committed git hooks when a runner is available.

    Args:
        repo_root: The worktree root.
        config: The hook configuration, relative to ``repo_root``.

    Returns:
        0 when the hooks were installed or there is no configuration to
        install, 1 when a configuration exists and no runner does. The caller
        declares this step advisory, so the 1 is a report rather than a gate.
    """
    if not (repo_root / config).is_file():
        print(f"No {config} in this repository; no git hooks to install.", flush=True)
        return 0

    found = _find(repo_root)
    if found is None:
        print(
            f"{config} is committed but no hook runner ({' or '.join(RUNNERS)}) is "
            "available, so the committed hooks are NOT installed and every commit "
            "in this worktree bypasses them.\n"
            "  Remedy: declare a hook runner in pyproject.toml's dev dependency "
            "group, refresh uv.lock, and re-run `just init-tools`.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    runner, prefix = found
    argv = [*prefix, "install"]
    print(f"$ {' '.join(argv)}", flush=True)
    completed = subprocess.run(argv, cwd=repo_root, check=False)
    if completed.returncode == 0:
        print(f"Git hooks installed with {runner}.", flush=True)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    """Install this repository's git hooks.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The exit code of the installation.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.init.hooks",
        description="Install the committed git hooks, or report why they were not.",
    )
    parser.add_argument(
        "config",
        type=Path,
        default=Path(".pre-commit-config.yaml"),
        nargs="?",
        help="the hook configuration, relative to the repository root",
    )
    args = parser.parse_args(argv)
    return install(Path(__file__).resolve().parents[2], args.config)


if __name__ == "__main__":
    sys.exit(main())
