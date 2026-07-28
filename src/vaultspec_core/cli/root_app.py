"""The shared root Typer app instance and global callback.

Defines :data:`app`, the top-level Typer application for the
``vaultspec-core`` executable, plus the ``--version``/``--target``/``--debug``
global callback (:func:`main`). Split out from :mod:`vaultspec_core.cli.root`
so the top-level command modules (:mod:`.root_install`, :mod:`.root_sync`,
:mod:`.root_doctor`) can import and mount onto it without a circular import
back through :mod:`vaultspec_core.cli.root`, which re-exports this module's
:data:`app` as the public surface.
"""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003 - Typer evaluates the root --target annotation.
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app

# Main app definition must precede sub-app imports to enable them to
# reference it if needed (and to satisfy Typer's module-level discovery).
app = make_app(
    help=(
        "vaultspec-core: Workspace runtime for vaultspec-managed projects. "
        "All commands default to the current directory; use --target / -t to "
        "operate on a different directory. Run 'vaultspec-core install' to set "
        "up a project, then 'vaultspec-core vault add research --feature <tag>' "
        "to start the first feature. See 'vaultspec-core spec reference' for "
        "worked command examples."
    ),
    no_args_is_help=True,
    add_completion=False,
)

# ---- Global callback --------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        from vaultspec_core.cli_common import get_version

        typer.echo(get_version())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: Annotated[
        Path | None,
        typer.Option(
            "--target",
            "-t",
            help="Target directory (defaults to current working directory)",
            dir_okay=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = None,
    debug: Annotated[
        bool, typer.Option("--debug", "-d", help="Enable debug logging")
    ] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Initialize workspace and logging."""
    from vaultspec_core.cli._target import reset, set_root_target
    from vaultspec_core.logging_config import configure_logging

    log_level = logging.DEBUG if debug else logging.WARNING
    configure_logging(level=log_level, debug=debug)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    # Store root-level target for subcommands; no workspace init here.
    # Each subcommand calls apply_target() / apply_target_install() which
    # merges root-level and subcommand-level --target with clear precedence.
    reset()
    set_root_target(target)
    ctx.obj = {}
