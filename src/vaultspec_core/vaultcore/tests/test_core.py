"""Tests for low-level frontmatter parsing.

Targets :func:`~vaultspec_core.vaultcore.parser.parse_frontmatter`.

Covers fallback semantics (PyYAML → simple parser), value normalization,
colon-in-value handling, quoted strings, whitespace trimming, and body
preservation.
"""

from __future__ import annotations

import pytest

from ...protocol.providers import GeminiModels
from .. import parse_frontmatter, parse_vault_metadata

pytestmark = [pytest.mark.unit]

# A UTF-8 byte-order mark (U+FEFF). A file authored with a BOM reads via
# ``read_text(encoding="utf-8")`` as this character followed by its content.
_BOM = "\ufeff"


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = (
            f"---\ntier: LOW\nmodel: {GeminiModels.LOW}\n"
            "---\n\n# Persona\nBody text here."
        )
        meta, body = parse_frontmatter(content)
        assert meta["tier"] == "LOW"
        assert meta["model"] == GeminiModels.LOW
        assert "# Persona" in body

    def test_no_frontmatter(self):
        content = "Just plain body text without frontmatter."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_empty_frontmatter(self):
        content = "---\n\n---\nBody after empty frontmatter."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert "Body after empty frontmatter." in body

    def test_colon_in_value(self):
        content = "---\ndescription: A test: with colons: everywhere\n---\nBody."
        meta, _body = parse_frontmatter(content)
        assert meta["description"] == "A test: with colons: everywhere"

    def test_quoted_description(self):
        content = (
            "---\n"
            'description: "A quoted description with special chars"\n'
            "tier: HIGH\n"
            "---\n"
            "Body."
        )
        meta, _body = parse_frontmatter(content)
        # PyYAML strips quotes (correct YAML behavior); simple parser preserves them.
        assert meta["description"] in (
            "A quoted description with special chars",
            '"A quoted description with special chars"',
        )
        assert meta["tier"] == "HIGH"

    def test_whitespace_handling(self):
        content = "---\n  key  :  value with spaces  \n---\nBody."
        meta, _body = parse_frontmatter(content)
        assert meta["key"] == "value with spaces"

    def test_body_preserved(self):
        content = "---\ntier: LOW\n---\nLine 1\nLine 2\nLine 3"
        _meta, body = parse_frontmatter(content)
        assert body == "Line 1\nLine 2\nLine 3"


class TestParseFrontmatterBOM:
    """A leading UTF-8 BOM must not hide the frontmatter fence.

    ``str.lstrip`` does not strip U+FEFF, so without the explicit BOM strip in
    the parser a BOM-prefixed document parses as having no frontmatter and is
    silently invisible to every feature scan and check.
    """

    def test_bom_frontmatter_parsed_identically_to_plain(self):
        plain = (
            "---\ntags:\n  - '#research'\n  - '#bom-feature'\n"
            "date: '2026-06-26'\n---\n\n# Body\nProse.\n"
        )
        meta_plain, body_plain = parse_frontmatter(plain)
        meta_bom, body_bom = parse_frontmatter(_BOM + plain)

        assert meta_bom == meta_plain
        assert meta_bom["tags"] == ["#research", "#bom-feature"]
        assert body_bom == body_plain

    def test_bom_followed_by_leading_whitespace(self):
        # The BOM is stripped first, then the existing lstrip handles any
        # additional leading whitespace before the fence.
        content = _BOM + "\n  ---\ntier: LOW\n---\nBody."
        meta, body = parse_frontmatter(content)
        assert meta["tier"] == "LOW"
        assert "Body." in body


class TestParseVaultMetadataBOM:
    """The rigid vault-metadata scanner must also see through a leading BOM."""

    def test_bom_metadata_parsed_identically_to_plain(self):
        plain = (
            "---\ntags:\n  - '#research'\n  - '#bom-feature'\n"
            "date: '2026-06-26'\nmodified: '2026-06-26'\n"
            "related:\n  - '[[other-doc]]'\n---\n\n# Body\nProse.\n"
        )
        meta_plain, body_plain = parse_vault_metadata(plain)
        meta_bom, body_bom = parse_vault_metadata(_BOM + plain)

        assert meta_bom.tags == meta_plain.tags == ["#research", "#bom-feature"]
        assert meta_bom.date == meta_plain.date == "2026-06-26"
        assert meta_bom.related == meta_plain.related == ["[[other-doc]]"]
        assert body_bom == body_plain
