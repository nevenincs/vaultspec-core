"""Manage canonical trigger definitions and lifecycle CRUD commands.

Triggers are stored as YAML definitions under ``.vaultspec/triggers/``.
This module provides first-class CRUD, sync, and status compliance
verification for triggers.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from . import types as _t
from .exceptions import ResourceExistsError, ResourceNotFoundError

__all__ = [
    "resolve_trigger_path",
]

logger = logging.getLogger(__name__)


def resolve_trigger_path(name: str) -> Path:
    """Resolve a trigger name to its YAML file path."""
    ctx = _t.get_context()
    if name.endswith((".yaml", ".yml")):
        return ctx.triggers_dir / name
    p_yaml = ctx.triggers_dir / f"{name}.yaml"
    p_yml = ctx.triggers_dir / f"{name}.yml"
    if p_yml.exists() and not p_yaml.exists():
        return p_yml
    return p_yaml


def triggers_add(
    name: str,
    event: str = "config.synced",
    command: str = "",
    force: bool = False,
    *,
    body: str | None = None,
    dry_run: bool = False,
    interactive: bool | None = None,
) -> Path:
    """Scaffold a new trigger YAML definition.

    Args:
        name: Trigger name.
        event: Lifecycle event to trigger on.
        command: Command to run.
        force: Whether to overwrite existing.
        body: Optional direct body content to override scaffold.
        dry_run: If ``True``, return the target path without writing.
        interactive: Override TTY detection.  ``None`` means auto-detect.

    Returns:
        Path to the created (or would-be-created) trigger YAML file.

    Raises:
        ResourceExistsError: If the trigger exists and *force* is ``False``.
    """
    from .helpers import atomic_write, ensure_dir, launch_editor

    ctx = _t.get_context()
    ensure_dir(ctx.triggers_dir)

    file_path = resolve_trigger_path(name)

    if file_path.exists() and not force:
        raise ResourceExistsError(
            f"Trigger '{file_path.name}' exists.",
            hint="Use --force to overwrite, or --dry-run to preview",
        )

    if dry_run:
        return file_path

    body_content = body
    is_interactive = interactive if interactive is not None else sys.stdin.isatty()

    if body_content is None:
        if is_interactive and not command:
            import yaml

            scaffold_dict = {
                "event": event,
                "enabled": True,
                "actions": [
                    {
                        "type": "shell",
                        "command": command
                        or 'echo "Trigger triggered with {event} and {path}"',
                    }
                ],
            }
            body_content = yaml.safe_dump(scaffold_dict, sort_keys=False)
            atomic_write(file_path, body_content)
            from ..config import get_config

            editor = get_config().editor
            logger.info("Opening editor (%s) for %s...", editor, file_path)
            try:
                launch_editor(editor, str(file_path))
                logger.info("Trigger saved to %s", file_path)
            except Exception as e:
                logger.error("Error opening editor: %s", e)
            return file_path
        else:
            if not sys.stdin.isatty():
                body_content = sys.stdin.read()
            if not body_content:
                import yaml

                scaffold_dict = {
                    "event": event,
                    "enabled": True,
                    "actions": [
                        {
                            "type": "shell",
                            "command": command or 'echo "Trigger triggered"',
                        }
                    ],
                }
                body_content = yaml.safe_dump(scaffold_dict, sort_keys=False)

    from .helpers import atomic_write

    atomic_write(file_path, body_content)
    logger.info("Created trigger: %s", file_path)
    return file_path


def triggers_show(name: str) -> str:
    """Read and return the contents of a trigger file.

    Returns:
        The trigger YAML content as a string.

    Raises:
        ResourceNotFoundError: If the trigger does not exist.
    """
    file_path = resolve_trigger_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Trigger '{name}' not found.")
    return file_path.read_text(encoding="utf-8")


def triggers_edit(name: str, editor: str | None = None) -> Path:
    """Open a trigger file in the configured text editor.

    Returns:
        The path to the trigger file that was opened.

    Raises:
        ResourceNotFoundError: If the trigger does not exist.
    """
    from .editor import assert_interactive_editing_allowed
    from .exceptions import (
        EditorCancellationError,
        EditorSubprocessError,
    )
    from .local_config import resolve_editor

    # Before resolution, not after: an invocation with no terminal cannot open
    # an editor whatever the ladder would have produced.
    assert_interactive_editing_allowed()

    file_path = resolve_trigger_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Trigger '{name}' not found.")

    target_dir = _t.get_context().target_dir
    resolved_editor = resolve_editor(editor, target_dir)

    import subprocess

    from .editor import spawn_editor

    try:
        returncode = spawn_editor(resolved_editor, file_path)

        if returncode != 0:
            if returncode == 130:
                raise EditorCancellationError("Editor edit cancelled by user.")
            raise EditorSubprocessError(
                f"Editor exited with non-zero exit code {returncode}."
            )
    except KeyboardInterrupt as e:
        raise EditorCancellationError("Editor edit cancelled by user (Ctrl+C).") from e
    except (OSError, subprocess.SubprocessError) as e:
        raise EditorSubprocessError(
            f"Failed to launch or run editor {resolved_editor!r}: {e}",
            hint=(
                "Ensure the editor command is valid and "
                "the executable is present on your PATH."
            ),
        ) from e

    return file_path


def triggers_remove(
    name: str,
    force: bool = False,
    confirm_fn: Callable[[str], bool] | None = None,
) -> bool:
    """Delete a trigger file from disk, with optional confirmation.

    Returns:
        ``True`` if removed, ``False`` if skipped.

    Raises:
        ResourceNotFoundError: If the trigger does not exist.
    """
    file_path = resolve_trigger_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Trigger '{name}' not found.")

    if not force:
        if confirm_fn is None:
            return False
        confirmed = confirm_fn(f"Are you sure you want to remove trigger '{name}'?")
        if not confirmed:
            return False

    file_path.unlink()
    logger.info("Removed Trigger: %s", name)
    return True


def triggers_rename(old_name: str, new_name: str) -> Path:
    """Rename a trigger file atomically through the shared rename engine.

    The move is driven through a :class:`RenameTransaction` bound to the triggers
    directory and serialized on the shared ``.vaultspec`` resource lock, so the
    endpoints are containment-checked, the rename is case-safe, and a failed
    rename rolls the triggers file back byte-for-byte.  The observable contract is
    unchanged: the same new path is returned and the same error types are raised.

    Returns:
        The new path after renaming.

    Raises:
        ResourceNotFoundError: If the source does not exist.
        ResourceExistsError: If the destination already exists.
        VaultSpecError: If an endpoint escapes the triggers directory or the
            on-disk rename fails.
    """
    from ..vaultcore.rename_engine import (
        RenameTransaction,
        assert_within,
        resource_lock_target,
    )

    triggers_dir = _t.get_context().triggers_dir

    old_path = resolve_trigger_path(old_name)
    ext = old_path.suffix
    new_file = new_name if new_name.endswith((".yaml", ".yml")) else f"{new_name}{ext}"
    new_path = triggers_dir / new_file

    assert_within(triggers_dir, old_path)
    assert_within(triggers_dir, new_path)

    if not old_path.exists():
        raise ResourceNotFoundError(f"Trigger '{old_name}' not found.")

    if new_path.exists():
        raise ResourceExistsError(f"Destination '{new_name}' already exists.")

    lock_target = resource_lock_target(triggers_dir.parent.parent)
    with RenameTransaction(triggers_dir, lock_target=lock_target) as tx:
        tx.snapshot([old_path])
        if not tx.rename(old_path, new_path):
            raise ResourceExistsError(f"Destination '{new_name}' already exists.")

    logger.info("Renamed Trigger '%s' to '%s'.", old_name, new_name)
    return new_path


def _action_warnings(name: str, actions: object) -> list[str]:
    """Return compliance warnings for one trigger definition's ``actions`` list."""
    if not isinstance(actions, list) or not actions:
        return [f"Trigger '{name}' has no defined actions."]

    action_list = cast("list[object]", actions)
    warnings: list[str] = []
    for idx, act in enumerate(action_list):
        if not isinstance(act, dict):
            warnings.append(
                f"Trigger '{name}': action at index {idx} is not a dictionary."
            )
            continue
        act_dict = cast("dict[str, Any]", act)
        if act_dict.get("type") != "shell":
            warnings.append(
                f"Trigger '{name}': action at index {idx} "
                f"has unknown type '{act_dict.get('type')}'."
            )
        elif not act_dict.get("command"):
            warnings.append(
                f"Trigger '{name}': shell action at index {idx} "
                "is missing 'command' field."
            )
    return warnings


def triggers_status() -> dict[str, Any]:
    """Perform deep compliancy verification of YAML trigger definitions."""
    from vaultspec_core.triggers import SUPPORTED_EVENTS
    from vaultspec_core.triggers.engine import parse_yaml

    triggers_dir = _t.get_context().triggers_dir

    status = "ok"
    definitions: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if not triggers_dir.exists():
        return {
            "status": "ok",
            "triggers_dir": str(triggers_dir),
            "definitions": [],
            "warnings": ["Triggers directory does not exist."],
            "errors": [],
        }

    for ext in ("*.yaml", "*.yml"):
        for path in sorted(triggers_dir.glob(ext)):
            try:
                raw_text = path.read_text(encoding="utf-8")
                data = parse_yaml(raw_text)

                event = data.get("event", "")
                definitions.append(path.name)
                if not event:
                    warnings.append(
                        f"Trigger '{path.name}' is missing the 'event' field."
                    )
                elif event not in SUPPORTED_EVENTS:
                    warnings.append(
                        f"Trigger '{path.name}' has unsupported event '{event}'."
                    )

                warnings.extend(_action_warnings(path.name, data.get("actions", [])))

            except Exception as e:
                # A trigger that fails to parse cannot be classified; list it and
                # report the parse error.
                definitions.append(path.name)
                errors.append(f"Failed to parse trigger '{path.name}': {e}")

    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "triggers_dir": str(triggers_dir),
        "definitions": definitions,
        "warnings": warnings,
        "errors": errors,
    }
