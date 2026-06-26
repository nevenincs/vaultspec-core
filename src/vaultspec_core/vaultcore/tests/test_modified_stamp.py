"""Tests for the CLI-maintained ``modified:`` frontmatter stamp.

Covers the lenient date helpers (``parse_lenient_date`` /
``normalize_date``), the ``DocumentMetadata.modified`` validation
policy (canonical ok, parseable-noncanonical ok, unparseable is a
violation), typed parsing of the field, and scaffold-time stamping
through ``create_vault_doc`` against the real shipped templates.
Implements the vault-orientation ADR decisions D3 and D3b.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import vaultspec_core
from vaultspec_core.config import reset_config
from vaultspec_core.vaultcore import (
    DocType,
    DocumentMetadata,
    normalize_date,
    parse_lenient_date,
    parse_vault_metadata,
)
from vaultspec_core.vaultcore.hydration import create_vault_doc, hydrate_template
from vaultspec_core.vaultcore.models import refresh_modified_stamp

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = [pytest.mark.unit]


class TestRefreshModifiedStamp:
    """``refresh_modified_stamp`` rewrites/adds the stamp preserving every other
    byte, across LF, CRLF, and classic-Mac CR line endings."""

    TODAY = datetime.date(2026, 6, 26)

    def test_lf_rewrites_existing_in_place(self):
        text = (
            "---\ntags:\n  - '#x'\ndate: '2026-01-01'\n"
            "modified: '2026-01-01'\n---\n\nBody.\n"
        )
        out = refresh_modified_stamp(text, self.TODAY)
        assert out == text.replace("modified: '2026-01-01'", "modified: '2026-06-26'")

    def test_crlf_rewrites_existing_preserving_crlf(self):
        text = (
            "---\r\ntags:\r\n  - '#x'\r\ndate: '2026-01-01'\r\n"
            "modified: '2026-01-01'\r\n---\r\n\r\nBody.\r\n"
        )
        out = refresh_modified_stamp(text, self.TODAY)
        assert out == text.replace("modified: '2026-01-01'", "modified: '2026-06-26'")
        assert "\r\n" in out and "\n" not in out.replace("\r\n", "")

    def test_cr_only_rewrites_existing_preserving_cr(self):
        # Classic-Mac CR-only document: the stamp must still be refreshed and the
        # bare-CR endings preserved (no LF introduced).
        text = (
            "---\rtags:\r  - '#x'\rdate: '2026-01-01'\r"
            "modified: '2026-01-01'\r---\rBody.\r"
        )
        out = refresh_modified_stamp(text, self.TODAY)
        assert out == text.replace("modified: '2026-01-01'", "modified: '2026-06-26'")
        assert "\n" not in out

    def test_cr_only_inserts_after_date_when_absent(self):
        # No modified: field -> insert after date:, preserving CR endings.
        text = "---\rtags:\r  - '#x'\rdate: '2026-01-01'\r---\rBody.\r"
        out = refresh_modified_stamp(text, self.TODAY)
        assert "modified: '2026-06-26'\r" in out
        assert out == (
            "---\rtags:\r  - '#x'\rdate: '2026-01-01'\r"
            "modified: '2026-06-26'\r---\rBody.\r"
        )
        assert "\n" not in out

    def test_lf_inserts_after_date_when_absent(self):
        text = "---\ntags:\n  - '#x'\ndate: '2026-01-01'\n---\n\nBody.\n"
        out = refresh_modified_stamp(text, self.TODAY)
        assert out == (
            "---\ntags:\n  - '#x'\ndate: '2026-01-01'\n"
            "modified: '2026-06-26'\n---\n\nBody.\n"
        )

    def test_no_frontmatter_unchanged(self):
        text = "# Just a body\n\nNo frontmatter here.\n"
        assert refresh_modified_stamp(text, self.TODAY) == text

    def test_bom_crlf_preserved(self):
        text = "﻿---\r\ndate: '2026-01-01'\r\nmodified: '2026-01-01'\r\n---\r\nBody.\r\n"
        out = refresh_modified_stamp(text, self.TODAY)
        assert out.startswith("﻿")
        assert out == text.replace("modified: '2026-01-01'", "modified: '2026-06-26'")


_BUILTIN_TEMPLATES = Path(vaultspec_core.__file__).parent / "builtins" / "templates"


@pytest.fixture(autouse=True)
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


class TestParseLenientDate:
    """Lenient parsing accepts common formats and rejects ambiguity."""

    def test_canonical_string(self):
        assert parse_lenient_date("2026-06-12") == datetime.date(2026, 6, 12)

    def test_quoted_and_padded_strings(self):
        assert parse_lenient_date("'2026-06-12'") == datetime.date(2026, 6, 12)
        assert parse_lenient_date('  "2026-06-12"  ') == datetime.date(2026, 6, 12)

    def test_date_object_passthrough(self):
        # YAML parses unquoted yyyy-mm-dd scalars into date objects.
        assert parse_lenient_date(datetime.date(2026, 6, 12)) == datetime.date(
            2026, 6, 12
        )

    def test_datetime_object_truncates_to_date(self):
        value = datetime.datetime(2026, 6, 12, 14, 30, 5)
        assert parse_lenient_date(value) == datetime.date(2026, 6, 12)

    def test_iso_timestamp(self):
        assert parse_lenient_date("2026-06-12T14:30:05") == datetime.date(2026, 6, 12)

    def test_iso_timestamp_with_zone(self):
        assert parse_lenient_date("2026-06-12T14:30:05+02:00") == datetime.date(
            2026, 6, 12
        )
        assert parse_lenient_date("2026-06-12T14:30:05Z") == datetime.date(2026, 6, 12)

    def test_iso_timestamp_space_separator(self):
        assert parse_lenient_date("2026-06-12 14:30:05") == datetime.date(2026, 6, 12)

    def test_year_first_slashes(self):
        assert parse_lenient_date("2026/06/12") == datetime.date(2026, 6, 12)
        assert parse_lenient_date("2026/6/2") == datetime.date(2026, 6, 2)

    def test_day_first_unambiguous(self):
        # First component 25 cannot be a month, so day-first is certain.
        assert parse_lenient_date("25-06-2026") == datetime.date(2026, 6, 25)
        assert parse_lenient_date("25/06/2026") == datetime.date(2026, 6, 25)

    def test_month_first_unambiguous(self):
        # Second component 25 cannot be a month, so month-first is certain.
        assert parse_lenient_date("06/25/2026") == datetime.date(2026, 6, 25)
        assert parse_lenient_date("06-25-2026") == datetime.date(2026, 6, 25)

    def test_ambiguous_year_last_rejected(self):
        # Both components could be a month: reject rather than guess.
        assert parse_lenient_date("03-04-2026") is None
        assert parse_lenient_date("03/04/2026") is None

    def test_impossible_dates_rejected(self):
        assert parse_lenient_date("2026-13-01") is None
        assert parse_lenient_date("2026-02-30") is None
        assert parse_lenient_date("2026/13/01") is None
        # Both components above 12 cannot form a valid month either way.
        assert parse_lenient_date("13-13-2026") is None

    def test_garbage_rejected(self):
        assert parse_lenient_date("not-a-date") is None
        assert parse_lenient_date("yesterday") is None
        assert parse_lenient_date("") is None
        assert parse_lenient_date("''") is None
        assert parse_lenient_date(None) is None
        assert parse_lenient_date(20260612) is None


class TestNormalizeDate:
    """Normalization returns the canonical quoted-form payload string."""

    def test_canonical_is_identity(self):
        assert normalize_date("2026-06-12") == "2026-06-12"

    def test_noncanonical_forms_normalize(self):
        assert normalize_date("2026/06/12") == "2026-06-12"
        assert normalize_date("2026-06-12T14:30:05+02:00") == "2026-06-12"
        assert normalize_date("25-06-2026") == "2026-06-25"
        assert normalize_date(datetime.date(2026, 6, 12)) == "2026-06-12"

    def test_unparseable_returns_none(self):
        assert normalize_date("03-04-2026") is None
        assert normalize_date("garbage") is None
        assert normalize_date(None) is None


class TestModifiedValidation:
    """validate(): canonical ok, parseable-noncanonical ok, unparseable fails."""

    @staticmethod
    def _metadata(modified: str | None) -> DocumentMetadata:
        return DocumentMetadata(
            tags=["#adr", "#vault-orientation"],
            date="2026-06-12",
            modified=modified,
        )

    def test_absent_modified_is_valid(self):
        assert self._metadata(None).validate() == []

    def test_canonical_modified_is_valid(self):
        assert self._metadata("2026-06-12").validate() == []

    def test_parseable_noncanonical_does_not_hard_fail(self):
        # The check/fix path normalizes these later (ADR D3b); validation
        # must not reject a permitted hand edit it can parse.
        assert self._metadata("2026/06/12").validate() == []
        assert self._metadata("2026-06-12T14:30:05").validate() == []
        assert self._metadata("25-06-2026").validate() == []

    def test_unparseable_modified_is_a_violation(self):
        errors = self._metadata("not-a-date").validate()
        assert len(errors) == 1
        assert "modified" in errors[0]
        assert "not-a-date" in errors[0]

    def test_ambiguous_modified_is_a_violation(self):
        errors = self._metadata("03-04-2026").validate()
        assert len(errors) == 1
        assert "modified" in errors[0]


class TestParseModifiedField:
    """Typed metadata parsing surfaces the modified field."""

    def test_quoted_scalar(self):
        content = (
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#vault-orientation'\n"
            "date: '2026-06-12'\n"
            "modified: '2026-06-13'\n"
            "related: []\n"
            "---\n"
            "# body\n"
        )
        metadata, body = parse_vault_metadata(content)
        assert metadata.date == "2026-06-12"
        assert metadata.modified == "2026-06-13"
        assert "# body" in body

    def test_unquoted_scalar(self):
        content = (
            "---\ntags: ['#adr', '#feat']\ndate: 2026-06-12\n"
            "modified: 2026-06-13\n---\nbody\n"
        )
        metadata, _ = parse_vault_metadata(content)
        assert metadata.modified == "2026-06-13"

    def test_absent_field_is_none(self):
        content = "---\ntags: ['#adr', '#feat']\ndate: '2026-06-12'\n---\nbody\n"
        metadata, _ = parse_vault_metadata(content)
        assert metadata.modified is None

    def test_empty_value_is_none(self):
        content = (
            "---\ntags: ['#adr', '#feat']\ndate: '2026-06-12'\nmodified:\n---\nbody\n"
        )
        metadata, _ = parse_vault_metadata(content)
        assert metadata.modified is None


class TestScaffoldStamp:
    """Scaffolded documents carry modified equal to date (ADR D3)."""

    @staticmethod
    def _content_root(tmp_path: Path) -> Path:
        """Mirror the real shipped templates into a workspace content root."""
        content_root = tmp_path / ".vaultspec"
        templates_dir = content_root / "rules" / "templates"
        templates_dir.mkdir(parents=True)
        for template in _BUILTIN_TEMPLATES.glob("*.md"):
            shutil.copy(template, templates_dir / template.name)
        return content_root

    @pytest.mark.parametrize(
        "doc_type",
        [DocType.ADR, DocType.AUDIT, DocType.PLAN, DocType.RESEARCH, DocType.REFERENCE],
    )
    def test_scaffold_stamps_modified_equal_to_date(self, tmp_path, doc_type):
        content_root = self._content_root(tmp_path)
        path = create_vault_doc(
            tmp_path,
            doc_type,
            "stamp-feat",
            "2026-06-12",
            title="stamp probe",
            content_root=content_root,
            tier="L1" if doc_type is DocType.PLAN else None,
        )
        metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
        assert metadata.date == "2026-06-12"
        assert metadata.modified == "2026-06-12"
        assert metadata.validate() == []

    def test_scaffold_exec_step_record_stamps_modified(self, tmp_path):
        content_root = self._content_root(tmp_path)
        path = create_vault_doc(
            tmp_path,
            DocType.EXEC,
            "stamp-feat",
            "2026-06-12",
            content_root=content_root,
            step_id="S01",
            step_display_path="W01.P01.S01",
            plan_stem="2026-06-12-stamp-feat-plan",
        )
        metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
        assert metadata.modified == "2026-06-12"
        assert metadata.validate() == []

    def test_stamp_lands_in_frontmatter_after_date(self, tmp_path):
        content_root = self._content_root(tmp_path)
        path = create_vault_doc(
            tmp_path,
            DocType.RESEARCH,
            "stamp-feat",
            "2026-06-12",
            title="placement probe",
            content_root=content_root,
        )
        content = path.read_text(encoding="utf-8")
        frontmatter_block = content.split("---")[1]
        lines = [line.strip() for line in frontmatter_block.strip().splitlines()]
        date_index = lines.index("date: '2026-06-12'")
        assert lines[date_index + 1] == "modified: '2026-06-12'"

    def test_template_with_existing_modified_field_is_not_double_stamped(self):
        template = (
            "---\n"
            "tags:\n"
            "  - '#research'\n"
            "  - '#{feature}'\n"
            "date: '{yyyy-mm-dd}'\n"
            "modified: '{yyyy-mm-dd}'\n"
            "related: []\n"
            "---\n"
            "# {feature} research: {topic}\n"
        )
        hydrated = hydrate_template(template, "stamp-feat", "2026-06-12", "probe")
        assert hydrated.count("modified:") == 1
        metadata, _ = parse_vault_metadata(hydrated)
        assert metadata.modified == "2026-06-12"

    def test_content_without_frontmatter_is_unchanged(self):
        hydrated = hydrate_template("# bare {feature}\n", "stamp-feat", "2026-06-12")
        assert "modified:" not in hydrated
