"""Tests for the ``body_hash`` content fingerprint definition and writer.

Pins the canonical body definition from
:mod:`vaultspec_core.vaultcore.body_hash` - what the fingerprint covers,
what it deliberately ignores, and where the field lands in frontmatter.
The definition is the load-bearing part of the modified-stamp-provenance
decision: a fingerprint that moved with encoding, line endings, or
formatting churn would recreate the corpus-wide false-staleness failure
that disqualified file mtime.

All assertions work on real text and independently-computed SHA-256
digests. No mocks, patches, or skips.
"""

from __future__ import annotations

import hashlib

import pytest

from vaultspec_core.vaultcore.body_hash import (
    BODY_HASH_PREFIX,
    body_digest,
    canonical_body,
    document_body_digest,
    is_canonical_digest,
    set_body_hash,
)

pytestmark = [pytest.mark.unit]

_LF_DOC = (
    "---\ntags:\n  - '#adr'\ndate: '2026-02-08'\nmodified: '2026-02-08'\n"
    "---\n\n# Heading\n\nProse.\n"
)


def _sha256(text: str) -> str:
    return BODY_HASH_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestCanonicalBody:
    def test_normalizes_newlines(self):
        assert canonical_body("a\r\nb\rc\n") == "a\nb\nc"

    def test_strips_outer_whitespace(self):
        assert canonical_body("\n\n  # H\n\nProse.\n\n\n") == "# H\n\nProse."

    def test_drops_a_leading_bom(self):
        assert canonical_body("﻿# H\n") == "# H"

    def test_preserves_interior_content_exactly(self):
        body = "# H\n\n    indented\ttab\n\nline  with  spaces\n"
        assert canonical_body(body) == body.strip()

    def test_does_not_eat_a_leading_thematic_break(self):
        # A body whose own first line is '---' must be hashed whole; only
        # ``strip_frontmatter`` removes a fence, and it is not applied here.
        body = "---\n\n# H\n"
        assert canonical_body(body) == "---\n\n# H"


class TestDocumentBodyDigest:
    def test_excludes_frontmatter(self):
        assert document_body_digest(_LF_DOC) == _sha256("# Heading\n\nProse.")

    def test_frontmatter_change_does_not_move_the_digest(self):
        other = _LF_DOC.replace("modified: '2026-02-08'", "modified: '2026-07-31'")
        assert document_body_digest(other) == document_body_digest(_LF_DOC)

    def test_body_change_moves_the_digest(self):
        other = _LF_DOC.replace("Prose.", "Different prose.")
        assert document_body_digest(other) != document_body_digest(_LF_DOC)

    def test_crlf_document_matches_its_lf_twin(self):
        crlf = _LF_DOC.replace("\n", "\r\n")
        assert document_body_digest(crlf) == document_body_digest(_LF_DOC)

    def test_cr_only_document_matches_its_lf_twin(self):
        cr = _LF_DOC.replace("\n", "\r")
        assert document_body_digest(cr) == document_body_digest(_LF_DOC)

    def test_bom_document_matches_its_bomless_twin(self):
        assert document_body_digest("﻿" + _LF_DOC) == document_body_digest(_LF_DOC)

    def test_trailing_newline_churn_does_not_move_the_digest(self):
        assert document_body_digest(_LF_DOC + "\n\n") == document_body_digest(_LF_DOC)

    def test_documents_without_frontmatter_hash_their_whole_text(self):
        assert document_body_digest("# Loose\n") == body_digest("# Loose\n")

    def test_surrogate_escaped_legacy_bytes_hash_without_raising(self):
        """A body carrying an undecodable legacy byte must still fingerprint.

        The edit pipeline decodes with ``surrogateescape`` so bytes like a
        bare ``0x90`` survive a round trip as lone surrogates. Strict
        encoding raises on those, which would turn a deliberately preserved
        byte into a crash on every stamping write.
        """
        legacy = _LF_DOC.replace("Prose.", "Legacy byte: \udc90")
        digest = document_body_digest(legacy)
        assert is_canonical_digest(digest)
        assert (
            digest
            == BODY_HASH_PREFIX
            + hashlib.sha256(b"# Heading\n\nLegacy byte: \x90").hexdigest()
        )


class TestIsCanonicalDigest:
    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "sha256:",
            "deadbeef",
            "sha256:" + "0" * 63,
            "sha256:" + "0" * 65,
            "sha256:" + "G" * 64,
            "SHA256:" + "a" * 64,
            "sha256:" + "A" * 64,
            "sha1:" + "a" * 40,
        ],
    )
    def test_rejects_non_canonical_values(self, value: str | None):
        assert is_canonical_digest(value) is False

    def test_accepts_what_the_module_writes(self):
        assert is_canonical_digest(document_body_digest(_LF_DOC)) is True


class TestSetBodyHash:
    def test_inserts_after_body_schema_when_present(self):
        text = (
            "---\ndate: '2026-02-08'\nmodified: '2026-02-08'\n"
            "body_schema: 'body-v1'\nrelated: []\n---\n\nBody.\n"
        )
        out = set_body_hash(text)
        lines = out.split("\n")
        assert lines[lines.index("body_schema: 'body-v1'") + 1].startswith("body_hash:")

    def test_inserts_after_modified_when_no_schema(self):
        text = "---\ndate: '2026-02-08'\nmodified: '2026-02-08'\n---\n\nBody.\n"
        out = set_body_hash(text)
        lines = out.split("\n")
        assert lines[lines.index("modified: '2026-02-08'") + 1].startswith("body_hash:")

    def test_inserts_after_date_when_no_modified(self):
        text = "---\ndate: '2026-02-08'\n---\n\nBody.\n"
        out = set_body_hash(text)
        lines = out.split("\n")
        assert lines[lines.index("date: '2026-02-08'") + 1].startswith("body_hash:")

    def test_rewrites_an_existing_field_in_place(self):
        text = (
            "---\ndate: '2026-02-08'\nmodified: '2026-02-08'\n"
            f"body_hash: '{_sha256('stale')}'\n---\n\nBody.\n"
        )
        out = set_body_hash(text)
        assert out.count("body_hash:") == 1
        assert _sha256("Body.") in out

    def test_preserves_indentation_of_an_existing_field(self):
        text = "---\ndate: '2026-02-08'\n  body_hash: 'sha256:0'\n---\n\nBody.\n"
        assert "\n  body_hash: '" in set_body_hash(text)

    def test_preserves_crlf(self):
        text = "---\r\ndate: '2026-02-08'\r\n---\r\n\r\nBody.\r\n"
        out = set_body_hash(text)
        assert "body_hash:" in out
        assert "\n" not in out.replace("\r\n", "")

    def test_preserves_cr_only_endings(self):
        text = "---\rdate: '2026-02-08'\r---\rBody.\r"
        out = set_body_hash(text)
        assert "body_hash:" in out
        assert "\n" not in out

    def test_no_frontmatter_is_left_untouched(self):
        text = "# Just a body\n\nNo frontmatter.\n"
        assert set_body_hash(text) == text

    def test_no_anchor_is_left_untouched(self):
        text = "---\ntags:\n  - '#adr'\n---\n\nBody.\n"
        assert set_body_hash(text) == text

    def test_is_idempotent(self):
        once = set_body_hash(_LF_DOC)
        assert set_body_hash(once) == once

    def test_writes_the_digest_of_its_own_body(self):
        out = set_body_hash(_LF_DOC)
        assert f"body_hash: '{_sha256('# Heading\n\nProse.')}'" in out

    def test_explicit_digest_is_written_verbatim(self):
        explicit = _sha256("something else")
        assert f"body_hash: '{explicit}'" in set_body_hash(_LF_DOC, explicit)
