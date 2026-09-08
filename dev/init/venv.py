"""Create the virtual environment only when it is genuinely absent.

``uv venv --allow-existing`` is not the idempotent operation its name suggests.
It tolerates an existing directory and still rewrites the interpreter links
inside it - which, on a shared Windows worktree where an editor, an MCP server
or another agent's session is running out of that environment, fails with
``Access is denied`` against a ``python.exe`` that is perfectly fine. The
observed failure is indistinguishable from a broken environment and is in fact
a healthy one in use.

So the existence check happens here, before `uv` is invoked at all, and an
environment that already has an interpreter is left strictly alone.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def interpreter(venv: Path) -> Path:
    """Return a virtual environment's interpreter path on this platform.

    Args:
        venv: The environment root.

    Returns:
        The interpreter path. The two platforms differ only in the layout
        directory's name, which is the whole of what the paired
        ``[windows]``/``[unix]`` recipe bodies this replaced disagreed about.
    """
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def ensure(venv: Path) -> int:
    """Create ``venv`` when it has no interpreter, and report either way.

    Args:
        venv: The environment root.

    Returns:
        0 when the environment exists or was created, otherwise ``uv venv``'s
        exit code.
    """
    if interpreter(venv).is_file():
        print(f"{venv.name} already exists - leaving it in place.", flush=True)
        return 0
    argv = ["uv", "venv", str(venv)]
    print(f"$ {' '.join(argv)}", flush=True)
    return subprocess.run(argv, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    """Ensure this repository's virtual environment exists.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The exit code of the provisioning.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.init.venv",
        description="Create the virtual environment only when it is absent.",
    )
    parser.add_argument(
        "venv",
        type=Path,
        default=Path(".venv"),
        nargs="?",
        help="the environment root, relative to the repository",
    )
    args = parser.parse_args(argv)
    return ensure(args.venv)


if __name__ == "__main__":
    sys.exit(main())
