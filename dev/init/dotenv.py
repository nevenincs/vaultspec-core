"""Materialize a repository's `.env` from its committed example.

Idempotent by contract, and asymmetrically so: an existing `.env` is NEVER
overwritten, because it carries the operator's own local credentials and
overwriting it is unrecoverable. The only thing this does is turn absence into
presence.

It is a preflight rather than a step of ``init-tools`` for a specific reason.
``vaultspec-a2a``'s justfile sets ``dotenv-load``, which means `just` itself
reads `.env` before it runs anything - so a worktree without one is
under-configured for the very command that would have created it. Running this
first, on every entry point, closes that trap for good.

Invoked as a subprocess so it is an ordinary declared step in
:mod:`dev.init.plan`, visible in the report like any other, rather than a
special case hidden inside the runner.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def provision(example: Path, target: Path) -> int:
    """Copy ``example`` to ``target`` when ``target`` is absent.

    Args:
        example: The committed example file.
        target: The operator's local file.

    Returns:
        0 when the target exists or was created, 1 when the example is missing
        and so the target cannot be provisioned at all.
    """
    if target.exists():
        print(f"{target.name} already exists - leaving it untouched.", flush=True)
        return 0
    if not example.is_file():
        print(
            f"{example} not found - cannot provision {target}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, target)
    print(f"Created {target.name} from {example.name}.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Provision one environment file.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The exit code of the provisioning.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.init.dotenv",
        description="Copy a committed example environment file into place when absent.",
    )
    parser.add_argument("example", type=Path, help="the committed example file")
    parser.add_argument("target", type=Path, help="the local file to create")
    args = parser.parse_args(argv)
    return provision(args.example, args.target)


if __name__ == "__main__":
    sys.exit(main())
