"""Tests for the ``body-sections`` vault health checker.

Exercises template-derived required-section validation against real on-disk
documents and controlled templates in ``.vaultspec/templates/``: present
sections pass, absent sections are flagged, comment-only and placeholder-only
sections read as empty, every document type is covered, plans require their
sections across tiers, execution records select the step vs summary template,
and a missing template degrades to a skip. No mocks, patches, or skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from .._base import Severity
from ..body_sections import check_body_sections

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

# Directory tag and template filename per document type under test.
_TYPE_META = {
    "adr": ("#adr", "adr.md"),
    "plan": ("#plan", "plan.md"),
    "research": ("#research", "research.md"),
    "reference": ("#reference", "reference.md"),
    "audit": ("#audit", "audit.md"),
    "exec": ("#exec", "exec-step.md"),
}


@pytest.fixture(autouse=True)
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _write_template(root: Path, name: str, sections: tuple[str, ...]) -> None:
    tdir = root / ".vaultspec" / "templates"
    tdir.mkdir(parents=True, exist_ok=True)
    heads = "\n\n".join(f"## {s}\n\n<!-- hint -->" for s in sections)
    (tdir / name).write_text(f"# `{{feature}}` doc\n\n{heads}\n", encoding="utf-8")


def _write_doc(
    root: Path,
    doc_type: str,
    stem: str,
    section_bodies: dict[str, str],
    *,
    feature: str = "feat",
    folder: str | None = None,
) -> Path:
    tag, _template = _TYPE_META[doc_type]
    body_parts = [
        f"## {title}\n\n{content}".rstrip() for title, content in section_bodies.items()
    ]
    text = (
        f"---\ntags:\n  - '{tag}'\n  - '#{feature}'\n"
        f"date: '2026-02-04'\nmodified: '2026-02-04'\nrelated: []\n---\n\n"
        f"# {stem}\n\n" + "\n\n".join(body_parts) + "\n"
    )
    if doc_type == "exec":
        sub = root / ".vault" / "exec" / (folder or "2026-02-04-feat")
    else:
        sub = root / ".vault" / doc_type
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"{stem}.md"
    path.write_text(text, encoding="utf-8")
    return path


def _skeleton(root: Path) -> None:
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    (root / ".vault").mkdir(parents=True, exist_ok=True)


def _run(root: Path, *, feature: str | None = None):
    snapshot = VaultGraph(root).to_snapshot()
    return check_body_sections(root, snapshot=snapshot, feature=feature)


class TestBodySections:
    def test_check_shape(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "adr.md", ("Problem", "Consequences"))
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            {"Problem": "real prose", "Consequences": "real prose"},
        )
        result = _run(tmp_path)
        assert result.check_name == "body-sections"
        assert result.supports_fix is False
        assert result.diagnostics == []

    def test_absent_required_section_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "adr.md", ("Problem", "Consequences"))
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            {"Problem": "real prose"},  # Consequences missing
        )
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Consequences" in warnings[0].message
        assert "Missing required section" in warnings[0].message

    def test_empty_required_section_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "adr.md", ("Problem", "Consequences"))
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            {"Problem": "real prose", "Consequences": "   "},
        )
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Consequences" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_extra_author_section_tolerated(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "adr.md", ("Problem",))
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            {"Problem": "real prose", "Appendix": "bonus content"},
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    @pytest.mark.parametrize("doc_type", list(_TYPE_META))
    def test_each_doc_type_present_is_clean(
        self, tmp_path: Path, doc_type: str
    ) -> None:
        _skeleton(tmp_path)
        _, template = _TYPE_META[doc_type]
        _write_template(tmp_path, template, ("Alpha", "Beta"))
        _write_doc(
            tmp_path,
            doc_type,
            f"2026-02-04-feat-{doc_type}",
            {"Alpha": "content", "Beta": "content"},
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    @pytest.mark.parametrize("doc_type", list(_TYPE_META))
    def test_each_doc_type_absent_is_flagged(
        self, tmp_path: Path, doc_type: str
    ) -> None:
        _skeleton(tmp_path)
        _, template = _TYPE_META[doc_type]
        _write_template(tmp_path, template, ("Alpha", "Beta"))
        _write_doc(
            tmp_path,
            doc_type,
            f"2026-02-04-feat-{doc_type}",
            {"Alpha": "content"},  # Beta missing
        )
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Beta" in d.message]
        assert len(warnings) == 1

    def test_comment_only_section_is_empty(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "research.md", ("Findings",))
        _write_doc(
            tmp_path,
            "research",
            "2026-02-04-feat-research",
            {"Findings": "<!-- One subsection per line of inquiry. -->"},
        )
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Findings" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_placeholder_only_section_is_empty(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "research.md", ("Findings",))
        _write_doc(
            tmp_path,
            "research",
            "2026-02-04-feat-research",
            {"Findings": "{topic}"},
        )
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Findings" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_plan_sections_required_across_tiers(self, tmp_path: Path) -> None:
        # The plan template mandates the same sections regardless of a plan's
        # tier; a plan missing one is flagged whether it is L1 or L2.
        _skeleton(tmp_path)
        _write_template(
            tmp_path,
            "plan.md",
            ("Description", "Steps", "Parallelization", "Verification"),
        )
        for tier, stem in (("L1", "2026-02-04-l1-plan"), ("L2", "2026-02-04-l2-plan")):
            path = tmp_path / ".vault" / "plan" / f"{stem}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"---\ntags:\n  - '#plan'\n  - '#feat'\n"
                f"date: '2026-02-04'\nmodified: '2026-02-04'\ntier: {tier}\n"
                "related: []\n---\n\n"
                f"# `feat` plan\n\n## Description\n\np\n\n## Steps\n\np\n\n"
                "## Parallelization\n\np\n",  # Verification missing
                encoding="utf-8",
            )
        result = _run(tmp_path)
        missing = [d for d in result.diagnostics if "Verification" in d.message]
        assert len(missing) == 2  # both tiers flagged identically

    def test_exec_summary_uses_summary_template(self, tmp_path: Path) -> None:
        # A -summary exec is validated against exec-summary.md, not exec-step.md.
        _skeleton(tmp_path)
        _write_template(tmp_path, "exec-step.md", ("Description", "Outcome", "Notes"))
        _write_template(tmp_path, "exec-summary.md", ("Description",))
        # Summary doc has only Description: clean against exec-summary, but would
        # fail against exec-step (which also requires Outcome and Notes).
        _write_doc(
            tmp_path,
            "exec",
            "2026-02-04-feat-P01-summary",
            {"Description": "phase summary prose"},
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    def test_exec_step_requires_all_step_sections(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "exec-step.md", ("Description", "Outcome", "Notes"))
        _write_doc(
            tmp_path,
            "exec",
            "2026-02-04-feat-P01-S01",
            {"Description": "did it"},  # Outcome, Notes missing
        )
        result = _run(tmp_path)
        titles = {
            t
            for d in result.diagnostics
            for t in ("Outcome", "Notes")
            if t in d.message
        }
        assert titles == {"Outcome", "Notes"}

    def test_missing_template_degrades_to_skip(self, tmp_path: Path) -> None:
        # No template written for adr: the checker skips rather than flagging.
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            {"Anything": "content"},
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    def test_generated_index_is_skipped(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_template(tmp_path, "index.md", ("Documents",))
        idx = tmp_path / ".vault" / "index" / "feat.index.md"
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(
            "---\ntags:\n  - '#index'\n  - '#feat'\n"
            "date: '2026-02-04'\nmodified: '2026-02-04'\nrelated: []\n---\n\n"
            "# `feat` feature index\n",  # no Documents section
            encoding="utf-8",
        )
        result = _run(tmp_path)
        assert result.diagnostics == []
