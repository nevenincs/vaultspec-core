"""Tests for the ``body_hash_seed`` migration (0.1.55).

Exercises
:func:`vaultspec_core.migrations.m_0_1_55_body_hash_seed.migrate` against
real on-disk fixtures. The migration attests each document's current body
with a ``body_hash:`` fingerprint so the modified-stamp checker's
reconciliation begins working corpus-wide, and it must do so without
rewriting a single ``modified:`` value - the amnesty the
modified-stamp-provenance decision grants to historical stamps.

Covers seeding, amnesty, idempotence (a second run mutates nothing),
encoding fidelity, the skip path, and the end-to-end property the whole
change exists for: a corpus that the mtime checker flagged wholesale
reports clean after the seed, with no stamp touched. All fixtures are
real files; no mocks, patches, or skips.
"""

from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.graph import VaultGraph
from vaultspec_core.migrations.m_0_1_55_body_hash_seed import migrate
from vaultspec_core.vaultcore import parse_vault_metadata
from vaultspec_core.vaultcore.body_hash import document_body_digest, is_canonical_digest
from vaultspec_core.vaultcore.checks._base import Severity
from vaultspec_core.vaultcore.checks.modified_stamp import check_modified_stamp

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _skeleton(root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


def _write_doc(
    root: Path,
    stem: str,
    *,
    modified: str = "2026-06-28",
    date: str = "2026-02-08",
    body: str = "# Heading\n\nProse.\n",
    newline: str = "\n",
    sub: str = "adr",
) -> Path:
    text = (
        f"---\ntags:\n  - '#adr'\n  - '#feat'\n"
        f"date: '{date}'\nmodified: '{modified}'\n---\n\n{body}"
    )
    doc = root / ".vault" / sub / f"{stem}.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return doc


class TestSeeding:
    def test_seeds_the_digest_of_the_current_body(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr")

        result = migrate(tmp_path)

        assert result.counts == {"seeded": 1, "already": 0, "skipped": 0}
        metadata, _body = parse_vault_metadata(doc.read_text(encoding="utf-8"))
        assert metadata.body_hash == document_body_digest("# Heading\n\nProse.\n")

    def test_leaves_every_modified_stamp_untouched(self, tmp_path: Path):
        _skeleton(tmp_path)
        stamps = {
            _write_doc(
                tmp_path, f"2026-02-08-doc-{i}-adr", modified=f"2026-06-{i:02d}"
            ): f"2026-06-{i:02d}"
            for i in range(1, 13)
        }

        migrate(tmp_path)

        for doc, stamp in stamps.items():
            metadata, _body = parse_vault_metadata(doc.read_text(encoding="utf-8"))
            assert metadata.modified == stamp

    def test_body_bytes_are_untouched(self, tmp_path: Path):
        _skeleton(tmp_path)
        body = "# Heading\n\nProse with  spacing\tand a tab.\n"
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr", body=body)

        migrate(tmp_path)

        assert doc.read_text(encoding="utf-8").endswith(body)

    def test_preserves_crlf_documents(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr", newline="\r\n")

        migrate(tmp_path)

        raw = doc.read_bytes()
        assert b"body_hash: 'sha256:" in raw
        assert raw.replace(b"\r\n", b"").count(b"\n") == 0

    def test_no_vault_directory_is_a_clean_no_op(self, tmp_path: Path):
        result = migrate(tmp_path)

        assert result.counts == {"seeded": 0, "already": 0, "skipped": 0}
        assert "nothing to seed" in result.summary

    def test_document_without_an_anchor_is_skipped(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = tmp_path / ".vault" / "adr" / "2026-02-08-anchorless-adr.md"
        doc.write_text(
            "---\ntags:\n  - '#adr'\n  - '#feat'\n---\n\n# Heading\n", encoding="utf-8"
        )
        before = doc.read_bytes()

        result = migrate(tmp_path)

        assert result.counts["skipped"] == 1
        assert result.counts["seeded"] == 0
        assert doc.read_bytes() == before


class TestIdempotence:
    def test_second_run_mutates_nothing(self, tmp_path: Path):
        _skeleton(tmp_path)
        docs = [_write_doc(tmp_path, f"2026-02-08-doc-{i}-adr") for i in range(5)]

        first = migrate(tmp_path)
        after_first = {doc: doc.read_bytes() for doc in docs}

        second = migrate(tmp_path)

        assert first.counts["seeded"] == 5
        assert second.counts == {"seeded": 0, "already": 5, "skipped": 0}
        assert {doc: doc.read_bytes() for doc in docs} == after_first

    def test_an_already_attested_document_is_left_alone(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr")
        migrate(tmp_path)
        seeded = doc.read_bytes()

        # A later hand edit leaves the attestation genuinely out of date;
        # the migration must not quietly re-attest it, because that would
        # erase the very evidence the checker exists to report.
        doc.write_bytes(seeded + b"\nAn unstamped sentence.\n")
        edited = doc.read_bytes()

        result = migrate(tmp_path)

        assert result.counts["already"] == 1
        assert doc.read_bytes() == edited

    def test_a_non_canonical_value_is_replaced(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr")
        text = doc.read_text(encoding="utf-8")
        doc.write_text(
            text.replace(
                "modified: '2026-06-28'",
                "modified: '2026-06-28'\nbody_hash: 'not-a-digest'",
            ),
            encoding="utf-8",
        )

        result = migrate(tmp_path)

        assert result.counts["seeded"] == 1
        metadata, _body = parse_vault_metadata(doc.read_text(encoding="utf-8"))
        assert is_canonical_digest(metadata.body_hash)


class TestSeedDissolvesMtimeFindings:
    """The acceptance property, in miniature.

    A corpus of documents whose stamps are old and whose files were all
    touched today is exactly the shape that produced the corpus-wide
    staleness flood. After the seed the checker reports clean, and no
    stamp was rewritten to get there.
    """

    def test_touched_corpus_reports_clean_after_the_seed(self, tmp_path: Path):
        _skeleton(tmp_path)
        docs = [
            _write_doc(tmp_path, f"2026-02-08-doc-{i}-adr", modified="2026-06-28")
            for i in range(15)
        ]
        now = datetime.datetime.now().timestamp()
        for doc in docs:
            os.utime(doc, (now, now))

        migrate(tmp_path)

        graph = VaultGraph(tmp_path)
        result = check_modified_stamp(tmp_path, snapshot=graph.to_snapshot())

        actionable = [
            d
            for d in result.diagnostics
            if d.severity in (Severity.WARNING, Severity.ERROR)
        ]
        assert actionable == []
        for doc in docs:
            assert "modified: '2026-06-28'" in doc.read_text(encoding="utf-8")
