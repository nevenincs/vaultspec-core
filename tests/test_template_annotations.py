"""Template annotation source-shape tests."""

from __future__ import annotations

import pytest

from tests.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit]


def test_templates_do_not_use_frontmatter_comment_directives() -> None:
    templates_dir = PROJECT_ROOT / ".vaultspec" / "rules" / "templates"
    offenders: list[str] = []

    for template in sorted(templates_dir.glob("*.md")):
        lines = template.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            continue
        for line in lines[1:]:
            if line == "---":
                break
            if line.lstrip().startswith("#"):
                offenders.append(f"{template.relative_to(PROJECT_ROOT)}: {line}")

    assert offenders == []
