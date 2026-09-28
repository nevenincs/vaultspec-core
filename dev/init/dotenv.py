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

With ``--from-main-worktree``, a linked worktree's new `.env` also takes the
values the operator already set in the main worktree's copy, so it starts with
the same local credentials rather than blank placeholders. Each carried value
replaces the line that declares its variable, commented out or not, and every
other byte of the example is kept. A variable the example does not declare is
left behind: the example is the list of what the repository reads, and a stale
entry should not spread to every new worktree. Carrying is best effort -
outside git, in a bare repository, in the main worktree itself, or when the
main worktree has no `.env`, the example is copied as it is.

Invoked as a subprocess so it is an ordinary declared step in
:mod:`dev.init.plan`, visible in the report like any other, rather than a
special case hidden inside the runner.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

#: An active ``NAME=value`` line, with the ``export`` prefix dotenv readers
#: accept. A commented line never matches, because a name cannot start with #.
_ASSIGNMENT: Final = re.compile(
    r"(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)"
)

#: Decoding that round-trips every byte, so an example that is not UTF-8 is
#: still copied exactly rather than refused.
_ENCODING: Final = "utf-8"
_ERRORS: Final = "surrogateescape"

#: Upper bound on one git query. This runs on every entry point, so a git that
#: hangs must cost the carry, not the whole of `init`.
_GIT_TIMEOUT_SECONDS: Final = 30


def _git(cwd: Path, *args: str) -> str | None:
    """Run a read-only git query.

    Args:
        cwd: The directory to run it in.
        *args: The git arguments.

    Returns:
        Its standard output, or ``None`` when git is absent, fails, or hangs.
    """
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _main_worktree_counterpart(target: Path) -> Path | None:
    """Locate the file at ``target``'s place in the repository's main worktree.

    Args:
        target: The file about to be created. Its directory must exist.

    Returns:
        The same repository-relative path under the main worktree, or ``None``
        when ``target`` is not inside a linked worktree of a non-bare
        repository.
    """
    location = _git(target.parent, "rev-parse", "--show-toplevel", "--show-prefix")
    listing = _git(target.parent, "worktree", "list", "--porcelain")
    if location is None or listing is None:
        return None
    toplevel, _, prefix = location.partition("\n")
    # The main worktree is always listed first; a bare repository lists itself
    # there instead, and has no working files to carry from.
    first = listing.split("\n\n", maxsplit=1)[0].splitlines()
    if not first or not first[0].startswith("worktree ") or "bare" in first:
        return None
    main = Path(first[0].removeprefix("worktree "))
    try:
        if os.path.samefile(main, toplevel):
            return None
    except OSError:
        return None
    return main / prefix.strip() / target.name


def _read_assignments(path: Path) -> dict[str, str]:
    """Read the variables a dotenv file sets.

    Args:
        path: The dotenv file.

    Returns:
        Each variable's right-hand side exactly as written, quotes included, so
        the copy means to its reader what the source meant. The last assignment
        of a name wins, and a name whose value is blank is omitted, as the
        readers of these files treat a blank as unset.
    """
    values: dict[str, str] = {}
    with path.open(encoding=_ENCODING, errors=_ERRORS) as source:
        for line in source:
            match = _ASSIGNMENT.fullmatch(line.strip())
            if match is not None:
                values[match["name"]] = match["value"].strip()
    return {name: value for name, value in values.items() if value.strip("'\" \t")}


def _fill(template: str, values: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """Write ``values`` into the lines of ``template`` that declare them.

    Args:
        template: The example's text, line endings intact.
        values: The values to carry, by variable name.

    Returns:
        The filled text, the names carried, and the names left behind because
        no line of the template declares them.
    """
    lines = template.splitlines(keepends=True)
    carried: list[str] = []
    undeclared: list[str] = []
    for name, value in values.items():
        declaration = re.compile(
            rf"[ \t]*(?:#[ \t]*)?(?:export[ \t]+)?{re.escape(name)}[ \t]*=.*"
        )
        for index, line in enumerate(lines):
            body = line.rstrip("\r\n")
            if declaration.fullmatch(body):
                lines[index] = f"{name}={value}{line[len(body) :]}"
                carried.append(name)
                break
        else:
            undeclared.append(name)
    return "".join(lines), carried, undeclared


def _create(target: Path, text: str) -> bool:
    """Create ``target`` holding ``text``, refusing to replace an existing file.

    Exclusive creation keeps the never-overwrite contract even against a
    concurrent run, and a failed write removes the partial file, so the next run
    provisions again instead of mistaking a truncated file for the operator's.

    Args:
        target: The file to create.
        text: Its contents.

    Returns:
        ``True`` when the file was created, ``False`` when it already existed.
    """
    try:
        out = target.open("x", encoding=_ENCODING, errors=_ERRORS, newline="")
    except FileExistsError:
        return False
    try:
        with out:
            out.write(text)
    except OSError:
        target.unlink(missing_ok=True)
        raise
    return True


def provision(example: Path, target: Path, *, from_main_worktree: bool = False) -> int:
    """Create ``target`` from ``example`` when ``target`` is absent.

    Args:
        example: The committed example file.
        target: The operator's local file.
        from_main_worktree: Whether to carry the values set in the main
            worktree's copy of ``target``.

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
    with example.open(encoding=_ENCODING, errors=_ERRORS, newline="") as source:
        text = source.read()
    target.parent.mkdir(parents=True, exist_ok=True)

    carried: list[str] = []
    undeclared: list[str] = []
    origin = _main_worktree_counterpart(target) if from_main_worktree else None
    if origin is not None and origin.is_file():
        try:
            values = _read_assignments(origin)
        except OSError as error:
            print(
                f"Cannot read {origin} ({error.__class__.__name__}) - "
                "carrying nothing from it.",
                file=sys.stderr,
                flush=True,
            )
            values = {}
        text, carried, undeclared = _fill(text, values)

    if not _create(target, text):
        print(f"{target.name} already exists - leaving it untouched.", flush=True)
        return 0
    print(f"Created {target.name} from {example.name}.", flush=True)
    if carried:
        print(f"Carried {', '.join(carried)} from {origin}.", flush=True)
    if undeclared:
        print(
            f"Not carried, not declared in {example.name}: {', '.join(undeclared)}.",
            flush=True,
        )
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
        description="Create a missing environment file from its committed example.",
    )
    parser.add_argument("example", type=Path, help="the committed example file")
    parser.add_argument("target", type=Path, help="the local file to create")
    parser.add_argument(
        "--from-main-worktree",
        action="store_true",
        help=(
            "in a linked worktree, carry the values set in the main worktree's "
            "copy of the target for the variables the example declares"
        ),
    )
    args = parser.parse_args(argv)
    return provision(
        args.example,
        args.target,
        from_main_worktree=args.from_main_worktree,
    )


if __name__ == "__main__":
    sys.exit(main())
