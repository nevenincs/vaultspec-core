"""Check and optionally fix resource name/filename integrity.

Validates that rules, skills, and agents have matching filenames and
frontmatter 'name' keys.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write, build_file
from ...core.resources import resource_rename
from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["check_rename_integrity"]


def get_clean_resource_name(file_name: str) -> str:
    """Strip extensions/suffixes to compute clean resource name."""
    stem = file_name
    if stem.endswith(".md"):
        stem = stem[:-3]
    if stem.endswith(".builtin"):
        stem = stem[:-8]
    return stem


def _build_scan_groups(root_dir: Path) -> list[tuple[str, bool, Path]]:
    """Gather (label, is_dir, base_dir) scan groups for rules/skills/agents."""
    from ...config import resolve_workspace
    from ...core.manifest import installed_tool_configs

    scan_groups: list[tuple[str, bool, Path]] = []

    try:
        layout = resolve_workspace(target_override=root_dir)
    except Exception:
        return scan_groups

    from ...core.types import init_paths

    vaultspec_dir = layout.vaultspec_dir
    rules_src_dir = vaultspec_dir / "rules"
    skills_src_dir = vaultspec_dir / "skills"
    agents_src_dir = vaultspec_dir / "agents"

    if rules_src_dir.exists():
        scan_groups.append(("Rule", False, rules_src_dir))
    if skills_src_dir.exists():
        scan_groups.append(("Skill", True, skills_src_dir))
    if agents_src_dir.exists():
        scan_groups.append(("Agent", False, agents_src_dir))

    try:
        init_paths(layout)
        active_configs = installed_tool_configs()
    except Exception as e:
        logger.warning("Could not gather installed tool configs: %s", e)
        return scan_groups

    for tool_type, cfg in active_configs.items():
        if getattr(cfg, "rules_dir", None) and cfg.rules_dir.exists():
            scan_groups.append((f"Rule ({tool_type.value})", False, cfg.rules_dir))
        if getattr(cfg, "skills_dir", None) and cfg.skills_dir.exists():
            scan_groups.append((f"Skill ({tool_type.value})", True, cfg.skills_dir))
        if getattr(cfg, "agents_dir", None) and cfg.agents_dir.exists():
            scan_groups.append((f"Agent ({tool_type.value})", False, cfg.agents_dir))

    return scan_groups


def _scan_skill_group(
    *,
    base_dir: Path,
    label: str,
    root_dir: Path,
    fix: bool,
    fix_frontmatter_wins: bool,
    confirm_fn: Callable[[str], bool] | None,
    result: CheckResult,
) -> None:
    """Scan a directory of skill subdirectories, each holding a SKILL.md."""
    for skill_dir in sorted(base_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.startswith(".") or skill_dir.name == "__pycache__":
            continue
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            continue

        _check_resource_file(
            file_path=skill_md_path,
            base_dir=base_dir,
            rel_resource_path=skill_dir.name,
            expected_name=get_clean_resource_name(skill_dir.name),
            label=label,
            is_dir=True,
            root_dir=root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn,
            result=result,
        )


def _scan_flat_group(
    *,
    base_dir: Path,
    label: str,
    root_dir: Path,
    fix: bool,
    fix_frontmatter_wins: bool,
    confirm_fn: Callable[[str], bool] | None,
    result: CheckResult,
) -> None:
    """Scan a directory of flat resource files (rules, agents)."""
    for f in sorted(base_dir.rglob("*.md")):
        if not f.is_file():
            continue
        rel_resource_path = f.relative_to(base_dir).as_posix()
        expected_name = get_clean_resource_name(f.name)

        _check_resource_file(
            file_path=f,
            base_dir=base_dir,
            rel_resource_path=rel_resource_path,
            expected_name=expected_name,
            label=label,
            is_dir=False,
            root_dir=root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn,
            result=result,
        )


def _scan_group(
    *,
    label: str,
    is_dir: bool,
    base_dir: Path,
    root_dir: Path,
    fix: bool,
    fix_frontmatter_wins: bool,
    confirm_fn: Callable[[str], bool] | None,
    result: CheckResult,
) -> None:
    """Dispatch a single scan group to the directory- or file-shaped scanner."""
    if is_dir:
        _scan_skill_group(
            base_dir=base_dir,
            label=label,
            root_dir=root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn,
            result=result,
        )
    else:
        _scan_flat_group(
            base_dir=base_dir,
            label=label,
            root_dir=root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn,
            result=result,
        )


def check_rename_integrity(
    root_dir: Path,
    *,
    fix: bool = False,
    fix_frontmatter_wins: bool = False,
    confirm_fn: Callable[[str], bool] | None = None,
) -> CheckResult:
    """Scan Rules, Skills, and Agents for name/filename mismatch and fix them.

    Args:
        root_dir: Project root directory.
        fix: Filename-wins mode. Updates frontmatter `name:` to match filename.
        fix_frontmatter_wins: Frontmatter-wins mode. Renames file to match
            frontmatter `name:`.
        confirm_fn: Interactive confirmation callback for frontmatter-wins mode.
    """
    result = CheckResult(check_name="rename-integrity", supports_fix=True)

    for label, is_dir, base_dir in _build_scan_groups(root_dir):
        _scan_group(
            label=label,
            is_dir=is_dir,
            base_dir=base_dir,
            root_dir=root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn,
            result=result,
        )

    return result


def _read_resource_metadata(
    file_path: Path,
    root_dir: Path,
    result: CheckResult,
) -> tuple[dict, str] | None:
    """Read and parse a resource file's frontmatter, recording errors on failure."""
    from ..parser import parse_frontmatter

    try:
        content = file_path.read_text(encoding="utf-8")
        return parse_frontmatter(content)
    except Exception as e:
        result.diagnostics.append(
            CheckDiagnostic(
                path=file_path.relative_to(root_dir)
                if file_path.is_absolute()
                else file_path,
                message=f"Failed to read/parse resource file: {e}",
                severity=Severity.ERROR,
            )
        )
        return None


def _describe_fix(
    fix: bool,
    fix_frontmatter_wins: bool,
    actual_name: str,
    expected_name: str,
) -> tuple[bool, str]:
    """Compute (fixable, fix_description) for the active fix mode."""
    if fix:
        return True, f"Update frontmatter name to '{expected_name}'"
    if fix_frontmatter_wins:
        if actual_name:
            return True, f"Physically rename to '{actual_name}'"
        return False, "Cannot physically rename (frontmatter name is empty/missing)"
    if actual_name:
        return True, (
            f"Update frontmatter name to '{expected_name}' (filename-wins) "
            f"or rename to '{actual_name}' (frontmatter-wins)"
        )
    return True, f"Update frontmatter name to '{expected_name}' (filename-wins)"


def _apply_filename_wins_fix(
    file_path: Path,
    meta: dict,
    body: str,
    expected_name: str,
    label: str,
    diag_path: Path,
    fix_description: str,
    result: CheckResult,
) -> None:
    """Rewrite the frontmatter `name:` key to match the expected (filename) name."""
    try:
        meta["name"] = expected_name
        new_content = build_file(meta, body)
        atomic_write(file_path, new_content)
        result.fixed_count += 1
        result.diagnostics.append(
            CheckDiagnostic(
                path=diag_path,
                message=f"Fixed: {fix_description}",
                severity=Severity.INFO,
            )
        )
        logger.info("Fixed %s frontmatter name in %s.", label.lower(), diag_path)
    except Exception as e:
        logger.error("Failed to fix frontmatter name in %s: %s", diag_path, e)
        result.diagnostics.append(
            CheckDiagnostic(
                path=diag_path,
                message=f"Failed to write frontmatter fix: {e}",
                severity=Severity.ERROR,
            )
        )


def _confirm_rename(
    confirm_fn: Callable[[str], bool] | None,
    prompt: str,
) -> bool:
    """Resolve interactive confirmation, defaulting to False on absence/error."""
    if confirm_fn is None:
        return False
    try:
        return confirm_fn(prompt)
    except Exception as e:
        logger.error("Error calling confirm_fn: %s", e)
        return False


def _apply_frontmatter_wins_fix(
    *,
    actual_name: str,
    expected_name: str,
    label: str,
    rel_resource_path: str,
    base_dir: Path,
    is_dir: bool,
    confirm_fn: Callable[[str], bool] | None,
    diag_path: Path,
    fix_description: str,
    diagnostic: CheckDiagnostic,
    result: CheckResult,
) -> None:
    """Physically rename the resource file to match its frontmatter `name:`."""
    if not actual_name:
        result.diagnostics.append(diagnostic)
        return

    prompt = f"Physically rename {label.lower()} '{expected_name}' to '{actual_name}'?"
    if not _confirm_rename(confirm_fn, prompt):
        result.diagnostics.append(diagnostic)
        return

    try:
        resource_rename(
            old_name=rel_resource_path,
            new_name=actual_name,
            base_dir=base_dir,
            label=label,
            is_dir=is_dir,
        )
        result.fixed_count += 1
        result.diagnostics.append(
            CheckDiagnostic(
                path=diag_path,
                message=f"Fixed: {fix_description}",
                severity=Severity.INFO,
            )
        )
        logger.info(
            "Physically renamed %s to match frontmatter name '%s'.",
            diag_path,
            actual_name,
        )
    except Exception as e:
        logger.error("Failed to rename %s to %s: %s", diag_path, actual_name, e)
        result.diagnostics.append(
            CheckDiagnostic(
                path=diag_path,
                message=f"Failed to rename resource: {e}",
                severity=Severity.ERROR,
            )
        )


def _check_resource_file(
    file_path: Path,
    base_dir: Path,
    rel_resource_path: str,
    expected_name: str,
    label: str,
    is_dir: bool,
    root_dir: Path,
    fix: bool,
    fix_frontmatter_wins: bool,
    confirm_fn: Callable[[str], bool] | None,
    result: CheckResult,
) -> None:
    parsed = _read_resource_metadata(file_path, root_dir, result)
    if parsed is None:
        return
    meta, body = parsed

    # Skip builtins (e.g. .builtin.md or containing .builtin)
    if file_path.name.endswith(".builtin.md") or ".builtin" in file_path.name:
        return

    actual_name = meta.get("name")

    # If the frontmatter lacks a name key, it is derived from the filename
    # (defensible for builtins/defaults)
    if actual_name is None or actual_name == expected_name:
        return

    diag_path = (
        file_path.relative_to(root_dir) if file_path.is_absolute() else file_path
    )
    msg = (
        f"{label} '{rel_resource_path}' frontmatter name '{actual_name}' "
        f"does not match expected name '{expected_name}'."
    )
    fixable, fix_description = _describe_fix(
        fix, fix_frontmatter_wins, actual_name, expected_name
    )
    diagnostic = CheckDiagnostic(
        path=diag_path,
        message=msg,
        severity=Severity.ERROR,
        fixable=fixable,
        fix_description=fix_description,
    )

    if fix:
        _apply_filename_wins_fix(
            file_path,
            meta,
            body,
            expected_name,
            label,
            diag_path,
            fix_description,
            result,
        )
        return

    if fix_frontmatter_wins:
        _apply_frontmatter_wins_fix(
            actual_name=actual_name,
            expected_name=expected_name,
            label=label,
            rel_resource_path=rel_resource_path,
            base_dir=base_dir,
            is_dir=is_dir,
            confirm_fn=confirm_fn,
            diag_path=diag_path,
            fix_description=fix_description,
            diagnostic=diagnostic,
            result=result,
        )
        return

    # Just report
    result.diagnostics.append(diagnostic)
