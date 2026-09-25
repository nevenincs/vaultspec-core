"""Validate explicit environment imports and merge them after installation."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..core.exceptions import VaultSpecError
from .config import CONFIG_REGISTRY, reset_config
from .local_env import (
    LOCAL_ENV,
    protect_store,
    read_environment_file,
    read_local_environment,
    reject_tracked_store,
    write_local_environment,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


@dataclass(frozen=True)
class EnvironmentImport:
    """A validated import, never rendered with its values."""

    values: dict[str, str] = field(default_factory=dict, repr=False)


def validate_values(values: Mapping[str, str]) -> None:
    """Reject unsupported variables and invalid values without echoing input."""
    allowed = {var.env_name: var for var in CONFIG_REGISTRY if var.persistable}
    for name, value in values.items():
        var = allowed.get(name)
        if var is None:
            raise VaultSpecError(
                "Environment import contains an unsupported variable.",
                hint="Supported names: " + ", ".join(sorted(allowed)),
            )
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise VaultSpecError(
                f"{name} requires a single-line value without controls."
            )
        if var.var_type in (int, float):
            try:
                number = var.var_type(value)
                valid = math.isfinite(number)
                valid &= var.min_value is None or number >= var.min_value
                valid &= var.max_value is None or number <= var.max_value
            except (ValueError, OverflowError):
                valid = False
            if not valid:
                raise VaultSpecError(
                    f"{name} requires a number within its allowed range."
                )


def prepare_environment(
    root: Path,
    entries: Sequence[str] = (),
    env_file: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> EnvironmentImport:
    """Validate before preflight; explicit entries override file imports."""
    reject_tracked_store(root)
    values = read_environment_file(env_file) if env_file is not None else {}
    validate_values(values)
    registry = {var.env_name: var for var in CONFIG_REGISTRY if var.persistable}
    environment = os.environ if environ is None else environ
    for entry in entries:
        name, separator, value = entry.partition("=")
        var = registry.get(name)
        if var is None:
            raise VaultSpecError(
                "--env requires a supported environment variable name."
            )
        if separator and var.secret:
            raise VaultSpecError(
                f"{name} cannot be supplied as a command-line value.",
                hint=f"Use --env {name} to import it, or --env-file PATH.",
            )
        if not separator:
            if name not in environment:
                raise VaultSpecError(
                    f"{name} is not present in the process environment."
                )
            value = environment[name]
        values[name] = value
    validate_values(values)
    # Validate existing content before install can change anything around it.
    if values:
        reject_tracked_store(root, provisioning=True)
        read_local_environment(root)
    return EnvironmentImport(values)


def apply_environment(
    root: Path, request: EnvironmentImport, *, dry_run: bool = False
) -> dict[str, str]:
    """Merge named keys, returning only names and canonical outcomes."""
    from ..core.helpers import advisory_lock

    validate_values(request.values)
    if not request.values:
        return {}
    if dry_run:
        return _outcomes(read_local_environment(root), request.values)
    protect_store(root)
    with advisory_lock(root / LOCAL_ENV):
        existing = read_local_environment(root)
        outcomes = _outcomes(existing, request.values)
        if any(value != "unchanged" for value in outcomes.values()):
            existing.update(request.values)
            write_local_environment(root, existing)
    reset_config()
    return outcomes


def _outcomes(existing: dict[str, str], supplied: dict[str, str]) -> dict[str, str]:
    return {
        name: (
            "created"
            if name not in existing
            else "unchanged"
            if existing[name] == value
            else "updated"
        )
        for name, value in supplied.items()
    }
