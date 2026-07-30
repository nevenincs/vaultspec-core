"""Template annotation source-shape tests.

The subject is this checkout's installed ``.vaultspec/templates/``, so the
repository root arrives through the ``repo_root`` fixture in
``dev/conftest.py`` rather than being re-derived here by counting directory
hops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.repo]


def _template_paths(repo_root: Path) -> list[Path]:
    templates_dir = repo_root / ".vaultspec" / "templates"
    return sorted(templates_dir.glob("*.md"))


def test_templates_do_not_use_frontmatter_comment_directives(repo_root: Path) -> None:
    offenders: list[str] = []

    for template in _template_paths(repo_root):
        lines = template.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            continue
        for line in lines[1:]:
            if line == "---":
                break
            if line.lstrip().startswith("#"):
                offenders.append(f"{template.relative_to(repo_root)}: {line}")

    assert offenders == []


def test_templates_do_not_use_malformed_html_comment_directives(
    repo_root: Path,
) -> None:
    offenders: list[str] = []

    for template in _template_paths(repo_root):
        for line_no, line in enumerate(
            template.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "<--" in line and "<!--" not in line:
                offenders.append(f"{template.relative_to(repo_root)}:{line_no}: {line}")

    assert offenders == []


def test_template_frontmatter_contains_only_data_fields(repo_root: Path) -> None:
    allowed_keys = {
        "body_schema",
        "date",
        "generated",
        "modified",
        "related",
        "step_id",
        "tags",
        "tier",
    }
    offenders: list[str] = []

    for template in _template_paths(repo_root):
        lines = template.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            offenders.append(f"{template.relative_to(repo_root)}: missing ---")
            continue

        active_sequence_key: str | None = None
        for line_no, line in enumerate(lines[1:], start=2):
            if line == "---":
                break
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("<!--", "#", "<--")):
                offenders.append(f"{template.relative_to(repo_root)}:{line_no}: {line}")
                continue
            if stripped.startswith("- "):
                if active_sequence_key not in {"related", "tags"}:
                    offenders.append(
                        f"{template.relative_to(repo_root)}:{line_no}: {line}"
                    )
                continue
            if ":" not in stripped:
                offenders.append(f"{template.relative_to(repo_root)}:{line_no}: {line}")
                continue
            key = stripped.split(":", 1)[0]
            active_sequence_key = key
            if key not in allowed_keys:
                offenders.append(f"{template.relative_to(repo_root)}:{line_no}: {line}")

    assert offenders == []
