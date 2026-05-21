"""Shared error handling for CLI commands.

Provides :func:`handle_error` which converts domain exceptions into
CLI error exits with optional hint messages.
"""

import typer


def handle_error(exc: Exception, *, json_output: bool = False) -> None:
    """Convert a domain or OS exception to a CLI error exit.

    Args:
        exc: The caught exception. :class:`VaultSpecError` and
            :class:`OSError` exit with code 1; anything else re-raises.
        json_output: When ``True``, emit the canonical
            ``{"schema": "vaultspec.error.v1", "status": "failed",
            "data": {...}}`` envelope to stdout instead of a plain-text
            ``Error:`` line on stderr, so a ``--json`` consumer can parse
            failures, not just exit codes.
    """
    from vaultspec_core.core.exceptions import VaultSpecError

    if isinstance(exc, (VaultSpecError, OSError)):
        hint = getattr(exc, "hint", None)
        if json_output:
            import json

            from vaultspec_core.cli.rendering import json_envelope

            data: dict[str, str] = {"message": str(exc)}
            if hint:
                data["hint"] = hint
            print(json.dumps(json_envelope("error", "failed", data), indent=2))
        else:
            typer.echo(f"Error: {exc}", err=True)
            if hint:
                typer.echo(f"  Hint: {hint}", err=True)
        raise typer.Exit(code=1) from exc
    raise exc
