"""Manage canonical hook definitions and lifecycle CRUD commands.

Hooks are stored as YAML definitions under ``.vaultspec/hooks/``.
This module provides first-class CRUD, sync, and status compliance
verification for hooks.
"""

from __future__ import annotations

import logging
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import types as _t
from .exceptions import ResourceExistsError, ResourceNotFoundError
from .types import SyncResult

logger = logging.getLogger(__name__)


def _resolve_hook_path(name: str) -> Path:
    """Resolve a hook name to its YAML file path."""
    ctx = _t.get_context()
    if name.endswith((".yaml", ".yml")):
        return ctx.hooks_dir / name
    p_yaml = ctx.hooks_dir / f"{name}.yaml"
    p_yml = ctx.hooks_dir / f"{name}.yml"
    if p_yml.exists() and not p_yaml.exists():
        return p_yml
    return p_yaml


def hooks_add(
    name: str,
    event: str = "vault.document.created",
    command: str = "",
    force: bool = False,
    *,
    body: str | None = None,
    dry_run: bool = False,
    interactive: bool | None = None,
) -> Path:
    """Scaffold a new hook YAML definition.

    Args:
        name: Hook name.
        event: Lifecycle event to trigger on.
        command: Command to run.
        force: Whether to overwrite existing.
        body: Optional direct body content to override scaffold.
        dry_run: If ``True``, return the target path without writing.
        interactive: Override TTY detection.  ``None`` means auto-detect.

    Returns:
        Path to the created (or would-be-created) hook YAML file.

    Raises:
        ResourceExistsError: If the hook exists and *force* is ``False``.
    """
    from .helpers import _launch_editor, atomic_write, ensure_dir

    ctx = _t.get_context()
    ensure_dir(ctx.hooks_dir)

    file_path = _resolve_hook_path(name)

    if file_path.exists() and not force:
        raise ResourceExistsError(
            f"Hook '{file_path.name}' exists.",
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
                        or 'echo "Hook triggered with {event} and {path}"',
                    }
                ],
            }
            body_content = yaml.safe_dump(scaffold_dict, sort_keys=False)
            atomic_write(file_path, body_content)
            from ..config import get_config

            editor = get_config().editor
            logger.info("Opening editor (%s) for %s...", editor, file_path)
            try:
                _launch_editor(editor, str(file_path))
                logger.info("Hook saved to %s", file_path)
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
                            "command": command or 'echo "Hook triggered"',
                        }
                    ],
                }
                body_content = yaml.safe_dump(scaffold_dict, sort_keys=False)

    from .helpers import atomic_write

    atomic_write(file_path, body_content)
    logger.info("Created hook: %s", file_path)
    return file_path


def hooks_show(name: str) -> str:
    """Read and return the contents of a hook file.

    Returns:
        The hook YAML content as a string.

    Raises:
        ResourceNotFoundError: If the hook does not exist.
    """
    file_path = _resolve_hook_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Hook '{name}' not found.")
    return file_path.read_text(encoding="utf-8")


def hooks_edit(name: str, editor: str | None = None) -> Path:
    """Open a hook file in the configured text editor.

    Returns:
        The path to the hook file that was opened.

    Raises:
        ResourceNotFoundError: If the hook does not exist.
    """
    from .exceptions import (
        EditorCancellationError,
        EditorResolutionError,
        EditorSubprocessError,
    )
    from .local_config import resolve_editor

    file_path = _resolve_hook_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Hook '{name}' not found.")

    target_dir = _t.get_context().target_dir
    resolved_editor = resolve_editor(editor, target_dir)

    import shlex
    import subprocess

    parts = shlex.split(resolved_editor)
    if not parts:
        raise EditorResolutionError(
            f"Empty editor command resolved from {resolved_editor!r}"
        )

    exe = shutil.which(parts[0]) or parts[0]
    cmd = [exe, *parts[1:], str(file_path)]

    try:
        if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
            result = subprocess.run(["cmd.exe", "/c", *cmd], shell=False)
        else:
            result = subprocess.run(cmd, shell=False)

        if result.returncode != 0:
            if result.returncode == 130:
                raise EditorCancellationError("Editor edit cancelled by user.")
            raise EditorSubprocessError(
                f"Editor exited with non-zero exit code {result.returncode}."
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


def hooks_remove(
    name: str,
    force: bool = False,
    confirm_fn: Callable[[str], bool] | None = None,
) -> bool:
    """Delete a hook file from disk, with optional confirmation.

    Returns:
        ``True`` if removed, ``False`` if skipped.

    Raises:
        ResourceNotFoundError: If the hook does not exist.
    """
    file_path = _resolve_hook_path(name)
    if not file_path.exists():
        raise ResourceNotFoundError(f"Hook '{name}' not found.")

    if not force:
        if confirm_fn is None:
            return False
        confirmed = confirm_fn(f"Are you sure you want to remove hook '{name}'?")
        if not confirmed:
            return False

    file_path.unlink()
    logger.info("Removed Hook: %s", name)
    return True


def hooks_rename(old_name: str, new_name: str) -> Path:
    """Rename a hook file atomically.

    Returns:
        The new path after renaming.

    Raises:
        ResourceNotFoundError: If the source does not exist.
        ResourceExistsError: If the destination already exists.
    """
    old_path = _resolve_hook_path(old_name)
    if not old_path.exists():
        raise ResourceNotFoundError(f"Hook '{old_name}' not found.")

    ext = old_path.suffix
    new_file = new_name if new_name.endswith((".yaml", ".yml")) else f"{new_name}{ext}"
    new_path = _t.get_context().hooks_dir / new_file

    if new_path.exists():
        raise ResourceExistsError(f"Destination '{new_name}' already exists.")

    shutil.move(str(old_path), str(new_path))
    logger.info("Renamed Hook '%s' to '%s'.", old_name, new_name)
    return new_path


def hooks_sync(dry_run: bool = False, prune: bool = False) -> SyncResult:
    """Perform validation sync of declarative hooks.

    Since hooks are defined declarative-only and do not output generated
    provider artifacts, this sync performs load validation.

    Args:
        dry_run: Unused.
        prune: Unused.

    Returns:
        A successful ``SyncResult`` if loaded successfully, otherwise contains errors.
    """
    _ = dry_run
    _ = prune
    from vaultspec_core.hooks import load_hooks

    result = SyncResult()
    try:
        hooks = load_hooks(_t.get_context().hooks_dir)
        result.skipped = len(hooks)
    except Exception as e:
        logger.warning("Failed to validate hooks during sync: %s", e)
        result.errors.append(str(e))
    return result


def hooks_status() -> dict[str, Any]:
    """Perform deep compliancy verification of YAML hook definitions."""
    from vaultspec_core.hooks import SUPPORTED_EVENTS
    from vaultspec_core.hooks.engine import _is_provider_hook_event, _parse_yaml

    hooks_dir = _t.get_context().hooks_dir

    status = "ok"
    definitions: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if not hooks_dir.exists():
        return {
            "status": "ok",
            "hooks_dir": str(hooks_dir),
            "definitions": [],
            "warnings": ["Hooks directory does not exist."],
            "errors": [],
        }

    for ext in ("*.yaml", "*.yml"):
        for path in sorted(hooks_dir.glob(ext)):
            try:
                raw_text = path.read_text(encoding="utf-8")
                data = _parse_yaml(raw_text)

                event = data.get("event", "")
                if _is_provider_hook_event(event):
                    # Provider (agent-runtime) hook; rendered by
                    # provider_hooks, not a CLI-lifecycle hook. Not our concern.
                    continue
                definitions.append(path.name)
                if not event:
                    warnings.append(f"Hook '{path.name}' is missing the 'event' field.")
                elif event not in SUPPORTED_EVENTS:
                    warnings.append(
                        f"Hook '{path.name}' has unsupported event '{event}'."
                    )

                actions = data.get("actions", [])
                if not isinstance(actions, list) or not actions:
                    warnings.append(f"Hook '{path.name}' has no defined actions.")
                else:
                    for idx, act in enumerate(actions):
                        if not isinstance(act, dict):
                            warnings.append(
                                f"Hook '{path.name}': action at index {idx} "
                                "is not a dictionary."
                            )
                        else:
                            from typing import cast

                            act_dict = cast("dict[str, Any]", act)
                            if act_dict.get("type") != "shell":
                                warnings.append(
                                    f"Hook '{path.name}': action at index {idx} "
                                    f"has unknown type '{act_dict.get('type')}'."
                                )
                            elif not act_dict.get("command"):
                                warnings.append(
                                    f"Hook '{path.name}': shell action at index "
                                    f"{idx} is missing 'command' field."
                                )

            except Exception as e:
                # A hook that fails to parse cannot be classified; list it and
                # report the parse error.
                definitions.append(path.name)
                errors.append(f"Failed to parse hook '{path.name}': {e}")

    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "hooks_dir": str(hooks_dir),
        "definitions": definitions,
        "warnings": warnings,
        "errors": errors,
    }
