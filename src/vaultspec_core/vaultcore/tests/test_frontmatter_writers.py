"""Byte-preservation tests for every in-place frontmatter writer.

Each writer edits only the frontmatter lines it owns. The fixture documents
carry the bytes a careless rewrite would disturb: a byte-order mark, fence
lines with trailing whitespace, irregular spacing inside values, CRLF or CR
line endings, a final line with no terminator, and a body code sample that
itself looks like frontmatter (``---`` lines, ``tags:``, ``related:``). The
expected output of every writer is the input with only the named lines
changed, so any other byte that moves fails the comparison.

No mocks, patches, or skips.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.vaultcore.body_hash import document_body_digest, set_body_hash
from vaultspec_core.vaultcore.checks._base import CheckResult
from vaultspec_core.vaultcore.checks.structure import ensure_index_directory_tag
from vaultspec_core.vaultcore.edit_engine import _compose_new_text
from vaultspec_core.vaultcore.exec_recovery import _replace_step_id
from vaultspec_core.vaultcore.hydration import _inject_body_schema, _inject_modified
from vaultspec_core.vaultcore.models import refresh_modified_stamp
from vaultspec_core.vaultcore.query_rename import rewrite_feature_tag_block
from vaultspec_core.vaultcore.related_surgery import (
    append_related_entry,
    remove_related_entries,
)
from vaultspec_core.vaultcore.rename_ops import rewrite_incoming_refs

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_BOM = "\ufeff"

#: Frontmatter with no ``date:``/``modified:`` anchor, so writers that also
#: refresh the stamp leave every line they do not own untouched.
_FRONTMATTER = (
    "---  \r\n"
    "tags:\r\n"
    "  - '#adr'\r\n"
    "  - '#demo'\r\n"
    "step_id: 'S01'\r\n"
    "related:\r\n"
    "  - '[[old-stem]]'\r\n"
    "custom:   keep   spacing   \r\n"
    "---\t\r\n"
)

#: A body whose code sample mimics frontmatter.
_BODY = (
    "\r\n# Body\r\n\r\n```yaml\r\n---\r\ntags:\r\n  - '#demo'\r\nrelated:\r\n"
    "  - '[[old-stem]]'\r\n---\r\n```\r\ntail without newline"
)

_DOC = _BOM + _FRONTMATTER + _BODY


@pytest.fixture(autouse=True)
def _fresh_config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _vault_doc(root: Path, text: str) -> Path:
    path = root / ".vault" / "adr" / "2026-01-01-demo-adr.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def test_rename_rewrites_only_the_frontmatter_link(tmp_path: Path) -> None:
    path = _vault_doc(tmp_path, _DOC)
    result = CheckResult(check_name="structure", supports_fix=True)

    rewrite_incoming_refs(tmp_path, [("old-stem", "new-stem")], result)

    expected = _BOM + _FRONTMATTER.replace("old-stem", "new-stem") + _BODY
    assert path.read_bytes() == expected.encode("utf-8")
    assert result.fixed_count == 1


def test_feature_tag_rename_rewrites_only_the_frontmatter_tag() -> None:
    out, changed = rewrite_feature_tag_block(_DOC, "demo", "renamed")

    assert changed is True
    assert out == _BOM + _FRONTMATTER.replace("'#demo'", "'#renamed'") + _BODY


def test_related_removal_keeps_every_other_byte(tmp_path: Path) -> None:
    path = _vault_doc(tmp_path, _DOC)

    assert remove_related_entries(path, ["old-stem"]) == 1

    frontmatter = _FRONTMATTER.replace(
        "related:\r\n  - '[[old-stem]]'\r\n", "related: []\r\n"
    )
    assert path.read_bytes() == (_BOM + frontmatter + _BODY).encode("utf-8")


def test_related_append_keeps_every_other_byte(tmp_path: Path) -> None:
    path = _vault_doc(tmp_path, _DOC)

    assert append_related_entry(path, "[[extra]]") is True

    frontmatter = _FRONTMATTER.replace(
        "  - '[[old-stem]]'\r\n", "  - '[[old-stem]]'\r\n  - '[[extra]]'\r\n"
    )
    assert path.read_bytes() == (_BOM + frontmatter + _BODY).encode("utf-8")


def test_related_key_is_added_to_the_frontmatter_not_the_body_sample(
    tmp_path: Path,
) -> None:
    frontmatter = "---\r\ntags:\r\n  - '#adr'\r\n---\r\n"
    path = _vault_doc(tmp_path, frontmatter + _BODY)

    assert append_related_entry(path, "[[extra]]") is True

    expected = (
        "---\r\ntags:\r\n  - '#adr'\r\nrelated:\r\n  - '[[extra]]'\r\n---\r\n" + _BODY
    )
    assert path.read_bytes() == expected.encode("utf-8")


def test_index_tag_is_planted_in_the_frontmatter_tags() -> None:
    out, changed = ensure_index_directory_tag(_DOC)

    assert changed is True
    assert (
        out
        == _BOM
        + _FRONTMATTER.replace("  - '#demo'\r\n", "  - '#demo'\r\n  - '#index'\r\n")
        + _BODY
    )


def test_index_tag_leaves_a_body_sample_alone_without_frontmatter() -> None:
    content = "# Doc\n\n```yaml\n---\ntags:\n  - '#plan'\n---\n```\n"

    assert ensure_index_directory_tag(content) == (content, False)


def test_step_id_replacement_keeps_every_other_byte(tmp_path: Path) -> None:
    path = _vault_doc(tmp_path, _DOC)

    _replace_step_id(path, "S02")

    expected = _BOM + _FRONTMATTER.replace("'S01'", "'S02'") + _BODY
    assert path.read_bytes() == expected.encode("utf-8")


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_modified_stamp_and_fingerprint_keep_every_other_byte(ending: str) -> None:
    doc = _BOM + ending.join(
        [
            "---",
            "date: '2026-01-01'   ",
            "modified: '2026-01-01'",
            "custom:  x",
            "---",
            "",
            "---",
            "not frontmatter",
            "---",
            "tail",
        ]
    )
    digest = document_body_digest(doc)

    out = refresh_modified_stamp(doc, datetime.date(2026, 9, 23))

    expected = doc.replace(
        f"modified: '2026-01-01'{ending}",
        f"modified: '2026-09-23'{ending}body_hash: '{digest}'{ending}",
    )
    assert out == expected
    assert set_body_hash(out, digest) == out


def test_scaffold_injectors_edit_only_the_frontmatter() -> None:
    body = "\n```yaml\n---\ndate: 'sample'\nmodified: 'sample'\n---\n```\n"
    content = "---\ntags:\n  - '#adr'\ndate: '2026-01-01'\ncustom:  x \n---\n" + body

    stamped = _inject_modified(content, "2026-09-23")
    assert stamped == content.replace(
        "date: '2026-01-01'\n", "date: '2026-01-01'\nmodified: '2026-09-23'\n", 1
    )

    schema = _inject_body_schema(stamped)
    assert schema.startswith(
        "---\ntags:\n  - '#adr'\ndate: '2026-01-01'\nmodified: '2026-09-23'\n"
        "body_schema: '"
    )
    assert schema.endswith("'\ncustom:  x \n---\n" + body)


def test_edit_engine_rewrites_only_the_edited_key(tmp_path: Path) -> None:
    path = _vault_doc(tmp_path, _DOC)

    proposed, newline = _compose_new_text(
        path, new_body=None, date=None, tags=["#adr", "#other"], related=None
    )

    lf = _DOC.replace("\r\n", "\n")
    expected = lf.replace("  - '#demo'\n", "  - '#other'\n", 1)
    assert newline == "\r\n"
    assert proposed == expected
