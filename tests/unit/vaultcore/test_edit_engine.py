"""Unit tests for the vaultcore edit engine and the kebab-case normalizer.

Exercises :mod:`vaultspec_core.vaultcore.edit_engine` and
:mod:`vaultspec_core.vaultcore.normalize` directly, below the Typer layer,
on the real filesystem with zero mocks.  The vault is built through the
:class:`WorkspaceFactory` unified fixture over a stdlib ``tempfile`` root
(the repo's ``tmp_path`` compat shim is deliberately sidestepped).

Coverage:
    - resolve: stem -> backing file, unknown ref raises the typed error
    - blob-hash conflict: the guard raises ``EditError`` with the conflict
      payload, and ``execute_edit`` folds it into a ``failed`` result
    - compose: frontmatter edit + body preserved + ``modified:`` refreshed
    - validate-refusal: a non-conformant proposal is refused, file unchanged
    - write: round-trip set-body updates bytes and returns the post-write
      blob hash; a matching guard allows the write; ``dry_run`` writes nothing
    - normalizer: hash-strip, lowercase, traversal rejection, pattern
      validation, and the label-scoped failure message
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory
from vaultspec_core.vaultcore.blob_hash import git_blob_oid
from vaultspec_core.vaultcore.edit_engine import (
    EditError,
    EditResult,
    _compose_new_text,
    _enforce_blob_hash,
    _resolve_doc_path,
    _write_proposed,
    execute_edit,
)
from vaultspec_core.vaultcore.normalize import (
    NormalizeResult,
    normalize_feature_tag,
)

pytestmark = [pytest.mark.unit]


_VALID_ADR = (
    "---\n"
    "tags:\n"
    "  - '#adr'\n"
    "  - '#test-feat'\n"
    "date: '2026-01-01'\n"
    "modified: '2026-01-01'\n"
    "related: []\n"
    "---\n"
    "\n# Demo ADR\n\nOriginal body.\n"
)

_SINGLE_TAG_ADR = (
    "---\n"
    "tags:\n"
    "  - '#adr'\n"
    "date: '2026-01-01'\n"
    "modified: '2026-01-01'\n"
    "related: []\n"
    "---\n"
    "\n# Demo ADR\n\nOriginal body.\n"
)


@pytest.fixture
def vault_root():
    """Yield an installed vault root holding two valid ADRs.

    Built via :class:`WorkspaceFactory` over a stdlib ``tempfile`` root and
    torn down after the test; the global path context is initialised so the
    engine's scanner, resolver, and checkers resolve the target.
    """
    reset_config()
    root = Path(tempfile.mkdtemp(prefix="vsc-edit-engine-"))
    try:
        WorkspaceFactory(root).install()
        adr_dir = root / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        # Write with explicit LF so the on-disk convention is the canonical
        # vault newline regardless of the host platform's text-mode default.
        (adr_dir / "2026-01-01-alpha-adr.md").write_text(
            _VALID_ADR, encoding="utf-8", newline="\n"
        )
        (adr_dir / "2026-01-01-beta-adr.md").write_text(
            _VALID_ADR.replace("# Demo ADR", "# Beta ADR"),
            encoding="utf-8",
            newline="\n",
        )
        init_paths(root)
        yield root
    finally:
        reset_config()
        shutil.rmtree(root, ignore_errors=True)


def _doc(root: Path) -> Path:
    """Return the primary fixture ADR path."""
    return root / ".vault" / "adr" / "2026-01-01-alpha-adr.md"


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_stem_resolves_to_backing_file(self, vault_root):
        resolved = _resolve_doc_path("2026-01-01-alpha-adr", vault_root)
        assert resolved == _doc(vault_root)

    def test_unknown_ref_raises_typed_error(self, vault_root):
        with pytest.raises(EditError) as excinfo:
            _resolve_doc_path("no-such-document", vault_root)
        assert excinfo.value.data["path"] == "no-such-document"


# ---------------------------------------------------------------------------
# blob-hash conflict
# ---------------------------------------------------------------------------


class TestBlobHashConflict:
    def test_guard_raises_typed_conflict(self, vault_root):
        doc = _doc(vault_root)
        stale = "deadbeef" * 5
        with pytest.raises(EditError) as excinfo:
            _enforce_blob_hash(doc, stale)
        data = excinfo.value.data
        assert data["conflict"] is True
        assert data["expected"] == stale
        assert data["actual"] == git_blob_oid(doc.read_bytes())

    def test_matching_hash_is_a_noop(self, vault_root):
        doc = _doc(vault_root)
        current = git_blob_oid(doc.read_bytes())
        # No exception is the assertion: a matching guard permits the write.
        assert _enforce_blob_hash(doc, current) is None

    def test_execute_edit_folds_conflict_into_failed_result(self, vault_root):
        before = _doc(vault_root).read_bytes()
        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nNope.\n",
            expected_blob_hash="0" * 40,
        )
        assert isinstance(result, EditResult)
        assert result.status == "failed"
        assert result.error is not None
        assert result.error["conflict"] is True
        assert result.error["actual"] == git_blob_oid(before)
        # No write occurred.
        assert _doc(vault_root).read_bytes() == before


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


class TestCompose:
    def test_frontmatter_edit_preserves_body_and_refreshes_stamp(self, vault_root):
        import datetime as _dt

        proposed, newline = _compose_new_text(
            _doc(vault_root),
            new_body=None,
            date="2026-09-09",
            tags=None,
            related=None,
        )
        assert newline == "\n"
        assert "date: '2026-09-09'" in proposed
        # The body survived the frontmatter-only edit.
        assert "Original body." in proposed
        # The modified stamp was refreshed to today, not left at 2026-01-01.
        today = _dt.date.today().isoformat()
        assert f"modified: '{today}'" in proposed

    def test_body_replacement_keeps_frontmatter(self, vault_root):
        proposed, _newline = _compose_new_text(
            _doc(vault_root),
            new_body="\n# Demo ADR\n\nComposed body.\n",
            date=None,
            tags=None,
            related=None,
        )
        assert "Composed body." in proposed
        assert "Original body." not in proposed
        assert "#test-feat" in proposed


# ---------------------------------------------------------------------------
# validate-refusal
# ---------------------------------------------------------------------------


class TestValidateRefusal:
    def test_non_conformant_proposal_is_refused_and_file_unchanged(self, vault_root):
        # A single-tag frontmatter fails the >=2-tag rule: the whole proposal
        # is non-conformant and must be refused strictly pre-write.
        _doc(vault_root).write_text(_SINGLE_TAG_ADR, encoding="utf-8", newline="\n")
        before = _doc(vault_root).read_bytes()

        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nReplacement.\n",
        )
        assert result.status == "failed"
        assert result.error is not None
        assert result.error["refused"] is True
        # The typed ``checks`` field mirrors the error payload's checks list.
        assert result.error["checks"] == result.checks
        assert any(d["severity"] == "error" for d in result.checks)
        # The file is untouched.
        assert _doc(vault_root).read_bytes() == before


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    def test_set_body_round_trip_updates_then_unchanged(self, vault_root):
        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nEngine body.\n",
        )
        assert result.status == "updated"
        on_disk = _doc(vault_root).read_bytes()
        assert b"Engine body." in on_disk
        # Frontmatter survived byte-for-byte.
        assert b"#test-feat" in on_disk
        # The returned hash matches the actual on-disk post-write bytes.
        assert result.blob_hash == git_blob_oid(on_disk)

        # Re-applying the identical body is a no-op (stamp already today).
        again = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nEngine body.\n",
        )
        assert again.status == "unchanged"
        assert again.blob_hash == git_blob_oid(_doc(vault_root).read_bytes())

    def test_matching_guard_allows_write(self, vault_root):
        current = git_blob_oid(_doc(vault_root).read_bytes())
        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nGuarded write.\n",
            expected_blob_hash=current,
        )
        assert result.status == "updated"
        assert b"Guarded write." in _doc(vault_root).read_bytes()

    def test_dry_run_writes_nothing(self, vault_root):
        before = _doc(vault_root).read_bytes()
        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nDry only.\n",
            dry_run=True,
        )
        assert result.status == "updated"
        assert result.dry_run is True
        assert result.changed is True
        # File untouched; the previewed hash equals what a real write produces.
        assert _doc(vault_root).read_bytes() == before
        real = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nDry only.\n",
        )
        assert result.blob_hash == real.blob_hash

    def test_write_proposed_persists_bytes(self, vault_root):
        doc = _doc(vault_root)
        proposed, newline = _compose_new_text(
            doc,
            new_body="\n# Demo ADR\n\nDirect write.\n",
            date=None,
            tags=None,
            related=None,
        )
        _write_proposed(doc, proposed, newline)
        assert "Direct write." in doc.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# normalizer
# ---------------------------------------------------------------------------


class TestNormalizeFeatureTag:
    def test_strips_hash_lowercases_and_accepts(self):
        result = normalize_feature_tag("#My-Feature")
        assert isinstance(result, NormalizeResult)
        assert result.ok is True
        assert result.value == "my-feature"
        assert result.error is None

    def test_already_canonical_is_unchanged(self):
        result = normalize_feature_tag("editor-demo")
        assert result.ok is True
        assert result.value == "editor-demo"

    def test_digits_and_hash_tag_accepted(self):
        result = normalize_feature_tag("#tag123", label="tag")
        assert result.ok is True
        assert result.value == "tag123"

    def test_empty_is_rejected_as_required(self):
        result = normalize_feature_tag("   ")
        assert result.ok is False
        assert result.value is None
        assert "required" in (result.error or "")

    def test_path_traversal_is_rejected(self):
        result = normalize_feature_tag("../evil")
        assert result.ok is False
        assert result.value is None

    def test_whitespace_interior_is_rejected(self):
        result = normalize_feature_tag("Feature Name")
        assert result.ok is False

    def test_underscore_is_rejected(self):
        result = normalize_feature_tag("bad_token")
        assert result.ok is False

    def test_label_scopes_the_error_message(self):
        result = normalize_feature_tag("Bad!Tag", label="tag")
        assert result.ok is False
        assert result.error is not None
        assert "tag" in result.error
