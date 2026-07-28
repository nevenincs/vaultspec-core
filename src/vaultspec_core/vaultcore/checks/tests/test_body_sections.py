"""Tests for the body-sections vault health checker.

Exercises immutable, attested body-schema validation against real on-disk
documents. A current schema stamp selects the registry contract, a declared
or ledger-contradicted claim is reported while an undeclared document with no
ledger entry is silent, mutable deployed templates cannot alter a document's
requirements, and execution records select their step or summary contract.
No mocks, patches, or skips.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from ...body_schema import body_schema_baseline_path
from ...parser import parse_vault_metadata
from .._base import Severity
from ..body_sections import check_body_sections

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_CURRENT_SCHEMA = "body-v1"

# These are the reviewed body-v1 contracts. The checker resolves them from
# production code; naming them here keeps each fixture readable and lets each
# case isolate the exact required section it exercises.
_REQUIRED_SECTIONS = {
    "adr": (
        "Problem Statement",
        "Considerations",
        "Considered options",
        "Constraints",
        "Implementation",
        "Rationale",
        "Consequences",
    ),
    "audit": ("Scope", "Findings", "Recommendations"),
    "plan": ("Description", "Steps", "Parallelization", "Verification"),
    "research": ("Findings", "Sources"),
    "reference": ("Summary",),
    "exec": ("Description", "Outcome", "Notes"),
}

_TYPE_META = {
    "adr": "#adr",
    "plan": "#plan",
    "research": "#research",
    "reference": "#reference",
    "audit": "#audit",
    "exec": "#exec",
}


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _write_doc(
    root: Path,
    doc_type: str,
    stem: str,
    section_bodies: dict[str, str],
    *,
    feature: str = "feat",
    folder: str | None = None,
    body_schema: str | None = _CURRENT_SCHEMA,
) -> Path:
    body_parts = [
        f"## {title}\n\n{content}".rstrip() for title, content in section_bodies.items()
    ]
    schema_line = f"body_schema: '{body_schema}'\n" if body_schema is not None else ""
    text = (
        f"---\ntags:\n  - '{_TYPE_META[doc_type]}'\n  - '#{feature}'\n"
        f"date: '2026-02-04'\nmodified: '2026-02-04'\n{schema_line}"
        "related: []\n---\n\n"
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


def _contents(doc_type: str) -> dict[str, str]:
    return {
        section: f"Authored {section} prose."
        for section in _REQUIRED_SECTIONS[doc_type]
    }


def _skeleton(root: Path) -> None:
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    (root / ".vault").mkdir(parents=True, exist_ok=True)


def _run(root: Path, *, feature: str | None = None):
    snapshot = VaultGraph(root).to_snapshot()
    return check_body_sections(root, snapshot=snapshot, feature=feature)


class TestBodySections:
    def test_check_shape(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(tmp_path, "adr", "2026-02-04-feat-adr", _contents("adr"))
        result = _run(tmp_path)
        assert result.check_name == "body-sections"
        assert result.supports_fix is False
        assert result.diagnostics == []

    def test_absent_required_section_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        sections = _contents("adr")
        del sections["Consequences"]
        _write_doc(tmp_path, "adr", "2026-02-04-feat-adr", sections)
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Consequences" in warnings[0].message
        assert "Missing required section" in warnings[0].message
        assert "body-v1" in warnings[0].message

    def test_empty_required_section_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        sections = _contents("adr")
        sections["Consequences"] = "   "
        _write_doc(tmp_path, "adr", "2026-02-04-feat-adr", sections)
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Consequences" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_extra_author_section_tolerated(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        sections = _contents("reference")
        sections["Appendix"] = "Bonus content."
        _write_doc(tmp_path, "reference", "2026-02-04-feat-reference", sections)
        result = _run(tmp_path)
        assert result.diagnostics == []

    @pytest.mark.parametrize("doc_type", list(_TYPE_META))
    def test_each_doc_type_present_is_clean(
        self, tmp_path: Path, doc_type: str
    ) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            doc_type,
            f"2026-02-04-feat-{doc_type}",
            _contents(doc_type),
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    @pytest.mark.parametrize("doc_type", list(_TYPE_META))
    def test_each_doc_type_absent_is_flagged(
        self, tmp_path: Path, doc_type: str
    ) -> None:
        _skeleton(tmp_path)
        sections = _contents(doc_type)
        missing = _REQUIRED_SECTIONS[doc_type][-1]
        del sections[missing]
        _write_doc(tmp_path, doc_type, f"2026-02-04-feat-{doc_type}", sections)
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if missing in d.message]
        assert len(warnings) == 1
        assert "Missing required section" in warnings[0].message

    def test_comment_only_section_is_empty(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        sections = _contents("research")
        sections["Findings"] = "<!-- One subsection per line of inquiry. -->"
        _write_doc(tmp_path, "research", "2026-02-04-feat-research", sections)
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Findings" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_placeholder_only_section_is_empty(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        sections = _contents("research")
        sections["Findings"] = "{topic}"
        _write_doc(tmp_path, "research", "2026-02-04-feat-research", sections)
        result = _run(tmp_path)
        warnings = [d for d in result.diagnostics if "Findings" in d.message]
        assert len(warnings) == 1
        assert "empty" in warnings[0].message

    def test_plan_sections_required_across_tiers(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        for tier, stem in (("L1", "2026-02-04-l1-plan"), ("L2", "2026-02-04-l2-plan")):
            sections = _contents("plan")
            del sections["Verification"]
            path = _write_doc(tmp_path, "plan", stem, sections)
            contents = path.read_text(encoding="utf-8")
            path.write_text(
                contents.replace("related: []", f"tier: {tier}\nrelated: []"),
                encoding="utf-8",
            )
        result = _run(tmp_path)
        missing = [d for d in result.diagnostics if "Verification" in d.message]
        assert len(missing) == 2

    def test_exec_summary_uses_summary_contract(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "exec",
            "2026-02-04-feat-P01-summary",
            {"Description": "Phase summary prose."},
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    def test_exec_step_requires_all_step_sections(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "exec",
            "2026-02-04-feat-P01-S01",
            {"Description": "Did it."},
        )
        result = _run(tmp_path)
        titles = {
            title
            for diagnostic in result.diagnostics
            for title in ("Outcome", "Notes")
            if title in diagnostic.message
        }
        assert titles == {"Outcome", "Notes"}

    def test_current_stamp_ignores_deployed_template(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        templates = tmp_path / ".vaultspec" / "templates"
        templates.mkdir()
        (templates / "adr.md").write_text(
            "# mutable template\n\n## Invented future requirement\n",
            encoding="utf-8",
        )
        _write_doc(tmp_path, "adr", "2026-02-04-feat-adr", _contents("adr"))
        result = _run(tmp_path)
        assert result.diagnostics == []

    def test_missing_schema_provenance_is_silent(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            _contents("adr"),
            body_schema=None,
        )
        result = _run(tmp_path)
        assert result.diagnostics == []

    def test_declared_legacy_schema_absent_from_ledger_is_flagged(
        self, tmp_path: Path
    ) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            _contents("adr"),
            body_schema="legacy-adr-v1",
        )
        result = _run(tmp_path)
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.severity is Severity.WARNING
        assert "provenance is not attested" in diagnostic.message
        assert "legacy-adr-v1" in diagnostic.message

    def test_hash_attested_legacy_body_is_validated_by_its_contract(
        self, tmp_path: Path
    ) -> None:
        _skeleton(tmp_path)
        document = _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            _contents("adr"),
            body_schema=None,
        )
        _metadata, body = parse_vault_metadata(document.read_text(encoding="utf-8"))
        ledger = body_schema_baseline_path(tmp_path)
        ledger.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "path": ".vault/adr/2026-02-04-feat-adr.md",
                            "body_sha256": hashlib.sha256(
                                body.encode("utf-8")
                            ).hexdigest(),
                            "body_schema": "legacy-adr-v3",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_ledger_hash_mismatch_is_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            _contents("adr"),
            body_schema=None,
        )
        ledger = body_schema_baseline_path(tmp_path)
        ledger.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "path": ".vault/adr/2026-02-04-feat-adr.md",
                            "body_sha256": "0" * 64,
                            "body_schema": "legacy-adr-v3",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = _run(tmp_path)

        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.severity is Severity.WARNING
        assert "provenance is not attested" in diagnostic.message
        assert "SHA-256" in diagnostic.message

    def test_unknown_schema_provenance_is_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "adr",
            "2026-02-04-feat-adr",
            _contents("adr"),
            body_schema="body-v999",
        )
        result = _run(tmp_path)
        assert len(result.diagnostics) == 1
        diagnostic = result.diagnostics[0]
        assert diagnostic.severity is Severity.WARNING
        assert "provenance is not attested" in diagnostic.message
        assert "body-v999" in diagnostic.message

    def test_generated_index_is_skipped(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        idx = tmp_path / ".vault" / "index" / "feat.index.md"
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(
            "---\ntags:\n  - '#index'\n  - '#feat'\n"
            "date: '2026-02-04'\nmodified: '2026-02-04'\nrelated: []\n---\n\n"
            "# feat feature index\n",
            encoding="utf-8",
        )
        result = _run(tmp_path)
        assert result.diagnostics == []
