"""Tests for the canonical frontmatter renderer.

The ADR supersession, rule promotion, and frontmatter repair paths once each
carried a renderer of their own. Their output is pinned here against those
renderers, kept below as the reference, over every markdown file in the
repository and a set of synthetic frontmatters: a rebuild must not move one
byte for any document the old code handled. The round-trip tests show a
frontmatter already in canonical form renders back to itself.

No mocks, patches, or skips.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from vaultspec_core.core.adr import _rewrite_adr_frontmatter
from vaultspec_core.vaultcore.checks.frontmatter import (
    _existing_tag_lines,
    _normalized_date,
    _normalized_tags,
    _repair_frontmatter,
)
from vaultspec_core.vaultcore.models import DocType, DocumentMetadata
from vaultspec_core.vaultcore.parser import (
    parse_vault_metadata,
    rerender_frontmatter,
    split_frontmatter,
)

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[4]

_SKIPPED_DIRS = frozenset({".venv", ".git", "node_modules"})

_BOM = chr(0xFEFF)

_REFERENCE_KNOWN = frozenset(
    {
        "tags",
        "date",
        "related",
        "feature",
        "supersedes",
        "superseded_by",
        "derived_from",
        "promoted_to",
        "archived",
    }
)


def _reference_unknown_lines(yaml_block: str, known: frozenset[str]) -> list[str]:
    preserved: list[str] = []
    in_unknown_key = False
    for line in yaml_block.split("\n"):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip()
            in_unknown_key = key not in known
            if in_unknown_key:
                preserved.append(line)
            continue
        if stripped.startswith("-"):
            if in_unknown_key:
                preserved.append(line)
            continue
        if in_unknown_key and stripped:
            preserved.append(line)
        in_unknown_key = False
    return preserved


def _reference_adr_render(normalized: str, meta: DocumentMetadata) -> str:
    """The ADR supersession and rule promotion renderer, as first written."""
    split = split_frontmatter(normalized)
    assert split.yaml_block is not None
    fm_lines = ["---"]
    if meta.tags:
        fm_lines.append("tags:")
        fm_lines.extend(f'  - "{tag}"' for tag in meta.tags)
    if meta.date:
        fm_lines.append(f"date: '{meta.date}'")
    if meta.related:
        fm_lines.append("related:")
        fm_lines.extend(f'  - "{link}"' for link in meta.related)
    if meta.supersedes:
        fm_lines.append("supersedes:")
        fm_lines.extend(f"  - '{stem}'" for stem in meta.supersedes)
    if meta.superseded_by:
        fm_lines.append(f"superseded_by: '{meta.superseded_by}'")
    if meta.derived_from:
        fm_lines.append("derived_from:")
        fm_lines.extend(f"  - '{stem}'" for stem in meta.derived_from)
    if meta.promoted_to:
        fm_lines.append("promoted_to:")
        fm_lines.extend(f"  - '{rule}'" for rule in meta.promoted_to)
    if meta.archived:
        fm_lines.append(f"archived: '{meta.archived}'")
    fm_lines.extend(_reference_unknown_lines(split.yaml_block, _REFERENCE_KNOWN))
    fm_lines.append("---")
    if split.body:
        fm_lines.append(split.body)
    return normalized[: split.frontmatter_start] + "\n".join(fm_lines)


def _reference_fixer_lines(
    metadata: DocumentMetadata,
    new_tags: list[str],
    date_val: str | None,
    yaml_block: str,
    *,
    tags_changed: bool,
) -> list[str]:
    """The frontmatter repair renderer, as first written."""
    lines = ["---"]
    if new_tags:
        lines.append("tags:")
        lines.extend(f'  - "{tag}"' for tag in new_tags)
    elif not tags_changed:
        lines.extend(_existing_tag_lines(yaml_block))
    if date_val:
        lines.append(f"date: {date_val}")
    elif metadata.date:
        lines.append(f"date: {metadata.date}")
    if metadata.modified:
        lines.append(f"modified: '{metadata.modified}'")
    if metadata.body_schema:
        lines.append(f"body_schema: '{metadata.body_schema}'")
    if metadata.body_hash:
        lines.append(f"body_hash: '{metadata.body_hash}'")
    if metadata.related:
        lines.append("related:")
        lines.extend(f'  - "{link}"' for link in metadata.related)
    if metadata.supersedes:
        lines.append("supersedes:")
        lines.extend(f"  - '{stem}'" for stem in metadata.supersedes)
    if metadata.superseded_by:
        lines.append(f"superseded_by: '{metadata.superseded_by}'")
    if metadata.derived_from:
        lines.append("derived_from:")
        lines.extend(f"  - '{stem}'" for stem in metadata.derived_from)
    if metadata.promoted_to:
        lines.append("promoted_to:")
        lines.extend(f"  - '{rule}'" for rule in metadata.promoted_to)
    if metadata.archived:
        lines.append(f"archived: '{metadata.archived}'")
    known = _REFERENCE_KNOWN | {"modified", "body_schema", "body_hash"}
    lines.extend(_reference_unknown_lines(yaml_block, known))
    lines.append("---")
    return lines


def _reference_repair(
    content: str, doc_type: DocType | None
) -> tuple[str, list[str]] | None:
    split = split_frontmatter(content)
    if split.yaml_block is None:
        return None
    metadata, _ = parse_vault_metadata(content)
    fixes: list[str] = []
    new_tags, tags_changed, tag_fix = _normalized_tags(
        metadata, split.yaml_block, doc_type
    )
    if tag_fix:
        fixes.append(tag_fix)
    date_val, date_fixed = _normalized_date(metadata.date)
    if date_fixed:
        fixes.append("normalized date format")
    if not fixes:
        return None
    lines = _reference_fixer_lines(
        metadata, new_tags, date_val, split.yaml_block, tags_changed=tags_changed
    )
    if split.body:
        lines.append(split.body)
    return content[: split.frontmatter_start] + "\n".join(lines), fixes


def _promoted(content: str) -> DocumentMetadata:
    """Parse *content* and mutate it the way supersession and promotion do."""
    meta, _ = parse_vault_metadata(content)
    meta.promoted_to.append("rule:promoted")
    meta.superseded_by = meta.superseded_by or "2026-01-02-successor-adr"
    return meta


def _assert_matches_reference(content: str) -> None:
    if split_frontmatter(content).yaml_block is None:
        return
    assert _rewrite_adr_frontmatter(
        content, _promoted(content), Path("doc.md")
    ) == _reference_adr_render(content, _promoted(content))
    for doc_type in (DocType.ADR, None):
        assert _repair_frontmatter(content, doc_type) == _reference_repair(
            content, doc_type
        )


_SYNTHETIC = [
    "---\ntags: ['adr', '#demo']\ndate: 2026-01-01T10:00:00\n---\n\n# Body\n",
    "---\nfeature: demo\ndate: '2026-01-01'\n---\nBody\n",
    "---\ntags: []\ndate: 2026-01-01T00:00\ncustom:\n  - a\n  - b\n\nnote: x\n"
    "  continued\n---\nBody",
    "---\ntags:\n  - '#adr'\n  - 'demo'\ndate: '2026-01-01'\nmodified: '2026-01-02'\n"
    "body_schema: 'body-v2'\nbody_hash: 'sha256:00'\nstep_id: 'S01'\n"
    "related:\n  - '[[a]]'\nsupersedes:\n  - 'old'\narchived: '2026-02-01'\n---\n",
    _BOM + "\n---\ntags:\n  - 'adr'\n---\n\n\nBody after blank lines\n",
]


class TestRendererMatchesReference:
    def test_every_repository_markdown_file(self) -> None:
        paths = [
            path
            for path in _REPO_ROOT.rglob("*.md")
            if not _SKIPPED_DIRS.intersection(path.relative_to(_REPO_ROOT).parts)
        ]
        assert len(paths) > 100
        for path in paths:
            text = path.read_bytes().decode("utf-8", "surrogateescape")
            _assert_matches_reference(text.replace("\r\n", "\n"))

    @pytest.mark.parametrize("content", _SYNTHETIC)
    def test_synthetic_frontmatter(self, content: str) -> None:
        _assert_matches_reference(content)


class TestRoundTrip:
    def test_canonical_adr_form_renders_back_to_itself(self) -> None:
        content = (
            _BOM + "\n---\ntags:\n"
            '  - "#adr"\n  - "#demo"\n'
            "date: '2026-01-01'\n"
            'related:\n  - "[[a]]"\n'
            "promoted_to:\n  - 'rule:x'\n"
            "modified: '2026-01-02'\n"
            "custom:  keep  this  \n"
            "---\n# Body\n\n  indented prose\n"
        )
        meta, _ = parse_vault_metadata(content)

        rendered = rerender_frontmatter(
            content, meta, render_stamps=False, quote_date=True
        )

        assert rendered == content

    def test_canonical_repair_form_renders_back_to_itself(self) -> None:
        content = (
            "---\ntags:\n"
            '  - "#adr"\n  - "#demo"\n'
            "date: 2026-01-01\n"
            "modified: '2026-01-02'\n"
            "body_hash: 'sha256:00'\n"
            'related:\n  - "[[a]]"\n'
            "custom: x\n"
            "---\n# Body\n"
        )
        meta, _ = parse_vault_metadata(content)

        rendered = rerender_frontmatter(
            content, meta, render_stamps=True, quote_date=False
        )

        assert rendered == content

    def test_mutation_changes_only_its_own_lines(self) -> None:
        content = "---\ntags:\n" + '  - "#adr"\n' + "date: '2026-01-01'\n---\nBody\n"
        meta, _ = parse_vault_metadata(content)

        rendered = rerender_frontmatter(
            content,
            dataclasses.replace(meta, superseded_by="next-adr"),
            render_stamps=False,
            quote_date=True,
        )

        assert rendered == content.replace(
            "---\nBody", "superseded_by: 'next-adr'\n---\nBody"
        )

    def test_text_without_frontmatter_is_not_rendered(self) -> None:
        assert (
            rerender_frontmatter(
                "# Body\n", DocumentMetadata(), render_stamps=True, quote_date=True
            )
            is None
        )
