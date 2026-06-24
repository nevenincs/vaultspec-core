"""CLI command definitions for vaultspec-core config."""

from __future__ import annotations

import json as _json
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target_install
from vaultspec_core.core import (
    KNOWN_KEYS,
    get_config_value,
    get_local_config_path,
    read_local_config,
    set_config_value,
    unset_config_value,
)

config_app = make_app(
    help=(
        "Manage local project configuration settings.\n\n"
        "Configuration is stored in .vaultspec/config.toml at the workspace "
        "root, ensuring settings are shared by default with teammates."
    ),
    no_args_is_help=True,
    add_completion=False,
)


@config_app.command("get")
def cmd_config_get(
    key: Annotated[str, typer.Argument(help="Configuration key to read")],
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Read a local configuration value.

    Reads from the project's .vaultspec/config.toml.
    """
    effective_target = apply_target_install(target)
    try:
        value = get_config_value(key, effective_target)
        if json_output:
            from vaultspec_core.cli.rendering import json_envelope

            print(
                _json.dumps(
                    json_envelope(
                        "config.get", "unchanged", {"key": key, "value": value}
                    ),
                    indent=2,
                )
            )
        else:
            if value is not None:
                typer.echo(value)
            else:
                typer.echo(f"Key '{key}' is not set.")
                raise typer.Exit(code=1)
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@config_app.command("set")
def cmd_config_set(
    key: Annotated[str, typer.Argument(help="Configuration key to set")],
    value: Annotated[str, typer.Argument(help="Value to write")],
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Write a local configuration value.

    Writes to the project's .vaultspec/config.toml.
    """
    effective_target = apply_target_install(target)
    try:
        set_config_value(key, value, effective_target)
        if json_output:
            from vaultspec_core.cli.rendering import json_envelope

            print(
                _json.dumps(
                    json_envelope(
                        "config.set", "updated", {"key": key, "value": value}
                    ),
                    indent=2,
                )
            )
        else:
            typer.echo(
                f"Set '{key}' to '{value}' in {get_local_config_path(effective_target)}"
            )
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@config_app.command("unset")
def cmd_config_unset(
    key: Annotated[str, typer.Argument(help="Configuration key to clear")],
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Clear a local configuration entry.

    Removes the entry from the project's .vaultspec/config.toml.
    """
    effective_target = apply_target_install(target)
    try:
        unset_config_value(key, effective_target)
        if json_output:
            from vaultspec_core.cli.rendering import json_envelope

            print(
                _json.dumps(
                    json_envelope("config.unset", "removed", {"key": key}), indent=2
                )
            )
        else:
            typer.echo(f"Unset '{key}' in {get_local_config_path(effective_target)}")
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@config_app.command("list")
def cmd_config_list(
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Enumerate all known configuration entries and current values.

    Displays keys and values from the project's .vaultspec/config.toml.
    """
    effective_target = apply_target_install(target)
    try:
        config_data = read_local_config(effective_target)
        entries = {}
        for key in sorted(KNOWN_KEYS):
            entries[key] = config_data.get(key)

        if json_output:
            from vaultspec_core.cli.rendering import json_envelope

            print(
                _json.dumps(
                    json_envelope("config.list", "unchanged", {"entries": entries}),
                    indent=2,
                )
            )
        else:
            from vaultspec_core.cli.rendering import (
                Cell,
                Column,
                render_listing,
                summary_line,
            )

            rows = []
            for key, val in entries.items():
                if val is not None:
                    rows.append({"key": key, "value": str(val), "status": "set"})
                else:
                    rows.append(
                        {
                            "key": key,
                            "value": Cell("<unset>", style="dim"),
                            "status": Cell("default", style="dim"),
                        }
                    )
            render_listing(
                rows,
                [Column("key"), Column("value"), Column("status")],
                title="config",
                summary=summary_line(len(rows), "config keys"),
                empty="no config keys defined",
            )
    except Exception as exc:
        _handle_error(exc, json_output=json_output)
