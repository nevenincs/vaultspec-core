"""Filesystem boundary for untrusted plan addresses."""

from pathlib import Path


def validate_plan_identifier(target: str) -> None:
    """Accept stems and feature handles, without platform-specific path syntax."""
    if not target or target in (".", "..") or any(c in target for c in "/\\:\0"):
        raise ValueError(
            "MCP plan targets must be a stem or feature handle, not a path"
        )


def workspace_plan_directory(root_dir: Path) -> Path:
    """Pin the plan boundary before following any vault directory links."""
    directory = root_dir.resolve() / ".vault" / "plan"
    try:
        contained = directory.resolve().is_relative_to(directory)
    except (OSError, ValueError) as exc:
        raise ValueError("could not resolve the workspace plan directory") from exc
    if not contained:
        raise ValueError("plan directory must stay within the workspace's .vault/plan")
    return directory


def workspace_plan_file(root_dir: Path, path: Path) -> Path:
    """Return a canonical regular file inside the workspace's plan boundary."""
    directory = workspace_plan_directory(root_dir)
    try:
        resolved = path.resolve(strict=True)
        contained = resolved.is_relative_to(directory) and resolved.is_file()
    except (OSError, ValueError) as exc:
        raise ValueError(
            "plan target must resolve to a regular file in .vault/plan"
        ) from exc
    if not contained:
        raise ValueError("plan target must resolve to a regular file in .vault/plan")
    return resolved
