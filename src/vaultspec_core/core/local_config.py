"""Local project configuration manager for `.vaultspec/config.toml`."""

from __future__ import annotations

import os
import shlex
import shutil
import tomllib
from pathlib import Path
from typing import Any

from .exceptions import EditorResolutionError, VaultSpecError
from .helpers import atomic_write, ensure_dir

KNOWN_KEYS = {"editor"}


def _command_first_token_on_path(command: str) -> bool:
    """Return whether *command*'s leading token resolves on ``PATH``.

    Tokenizes *command* with platform-aware quoting rules, disabling POSIX
    mode on Windows exactly as :mod:`vaultspec_core.hooks.engine` does, so a
    Windows editor path containing backslashes (for example
    ``C:\\tools\\ed.exe``) is not mangled by POSIX escape handling before the
    :func:`shutil.which` lookup.

    Args:
        command: Editor command string, optionally including flags such as
            ``"code --wait"``.

    Returns:
        ``True`` when the command has a first token that :func:`shutil.which`
        can locate on the current ``PATH``, ``False`` otherwise.
    """
    parts = shlex.split(command, posix=(os.name != "nt"))
    return bool(parts) and shutil.which(parts[0]) is not None


def get_local_config_path(target_dir: Path | None = None) -> Path:
    """Get the path to `.vaultspec/config.toml`."""
    if target_dir is None:
        try:
            from .types import get_context

            target_dir = get_context().target_dir
        except Exception:
            target_dir = Path.cwd()
    return target_dir / ".vaultspec" / "config.toml"


def read_local_config(target_dir: Path | None = None) -> dict[str, Any]:
    """Read the local configuration file."""
    path = get_local_config_path(target_dir)
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        return tomllib.loads(content)
    except Exception as e:
        raise VaultSpecError(f"Failed to parse config file at '{path}': {e}") from e


def write_local_config(data: dict[str, Any], target_dir: Path | None = None) -> None:
    """Write the local configuration file atomically."""
    path = get_local_config_path(target_dir)
    ensure_dir(path.parent)

    # Check that all keys in data are known
    for k in data:
        if k not in KNOWN_KEYS:
            keys_str = ", ".join(sorted(KNOWN_KEYS))
            raise VaultSpecError(
                f"Unknown configuration key '{k}'. Valid keys: {keys_str}"
            )

    # Serialize to simple TOML format
    lines = []
    for k, v in sorted(data.items()):
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')
        elif isinstance(v, bool):
            lines.append(f"{k} = {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        else:
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')

    content = "\n".join(lines)
    if content:
        content += "\n"

    try:
        atomic_write(path, content)
    except Exception as e:
        raise VaultSpecError(f"Failed to write config file at '{path}': {e}") from e


def get_config_value(key: str, target_dir: Path | None = None) -> Any:
    """Get a configuration value, returning None if not set."""
    if key not in KNOWN_KEYS:
        keys_str = ", ".join(sorted(KNOWN_KEYS))
        raise VaultSpecError(
            f"Unknown configuration key '{key}'. Valid keys: {keys_str}"
        )
    data = read_local_config(target_dir)
    return data.get(key)


def set_config_value(key: str, value: Any, target_dir: Path | None = None) -> None:
    """Set a configuration value."""
    if key not in KNOWN_KEYS:
        keys_str = ", ".join(sorted(KNOWN_KEYS))
        raise VaultSpecError(
            f"Unknown configuration key '{key}'. Valid keys: {keys_str}"
        )
    data = read_local_config(target_dir)
    data[key] = value
    write_local_config(data, target_dir)


def unset_config_value(key: str, target_dir: Path | None = None) -> None:
    """Unset a configuration value. If not present, this is a no-op."""
    if key not in KNOWN_KEYS:
        keys_str = ", ".join(sorted(KNOWN_KEYS))
        raise VaultSpecError(
            f"Unknown configuration key '{key}'. Valid keys: {keys_str}"
        )
    data = read_local_config(target_dir)
    if key in data:
        del data[key]
        write_local_config(data, target_dir)


def resolve_editor(
    editor_override: str | None = None, target_dir: Path | None = None
) -> str:
    """Resolve the editor command to use based on the precedence rules.

    Order:
      1. editor_override (e.g. from --editor flag)
      2. local config `editor` value
      3. VISUAL env var
      4. EDITOR env var
      5. "vi" fallback
    """
    sources_tried = []

    if editor_override:
        sources_tried.append(f"--editor flag ({editor_override!r})")
        if _command_first_token_on_path(editor_override):
            return editor_override

    local_editor = get_config_value("editor", target_dir)
    if local_editor:
        sources_tried.append(f"local config 'editor' ({local_editor!r})")
        if _command_first_token_on_path(local_editor):
            return local_editor

    vaultspec_editor = os.environ.get("VAULTSPEC_EDITOR")
    if vaultspec_editor:
        sources_tried.append(f"$VAULTSPEC_EDITOR env var ({vaultspec_editor!r})")
        if _command_first_token_on_path(vaultspec_editor):
            return vaultspec_editor

    visual_env = os.environ.get("VISUAL")
    if visual_env:
        sources_tried.append(f"$VISUAL env var ({visual_env!r})")
        if _command_first_token_on_path(visual_env):
            return visual_env

    editor_env = os.environ.get("EDITOR")
    if editor_env:
        sources_tried.append(f"$EDITOR env var ({editor_env!r})")
        if _command_first_token_on_path(editor_env):
            return editor_env

    sources_tried.append("fallback 'vi'")
    if shutil.which("vi"):
        return "vi"

    raise EditorResolutionError(
        "Could not resolve a working text editor from any of the configured sources.\n"
        "Sources tried:\n" + "\n".join(f"  - {src}" for src in sources_tried),
        hint=(
            "Configure a valid editor using the `--editor` flag, project-local config "
            "(`vaultspec-core config set editor <value>`), or the VISUAL/EDITOR "
            "environment variables."
        ),
    )
