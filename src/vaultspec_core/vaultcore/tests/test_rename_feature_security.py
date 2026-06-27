"""Adversarial security tests for the ``rename_feature`` backend.

These tests prove the hardening applied to
:mod:`vaultspec_core.vaultcore.query` and
:mod:`vaultspec_core.vaultcore.rename_ops` cannot be defeated: a feature
rename can never read, write, move, or delete a file whose true location is
outside the managed directory tree, can never lose or overwrite document data,
and can never be steered out of bounds through a crafted ``old``/``new``
argument, a planted symlink, or malformed document content.

No test doubles are used anywhere. Every vault is a real on-disk tree built
under a real ``tmp_path``; every symlink is a real OS symlink created with
:meth:`pathlib.Path.symlink_to`; every assertion reads real bytes off disk
or runs the real ``rename_feature`` against them. The only permitted skip is
an OS-capability gate: Windows requires developer mode or elevation to
create symlinks, so the four symlink-requiring tests are gated on a runtime
probe (:func:`_symlinks_supported`). Every other test - argument injection,
validation, reserved names, the lexical containment unit, malformed content,
CRLF/BOM byte preservation, and the collision/data-loss guard - runs
unconditionally on every platform.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...core.exceptions import VaultSpecError
from ..query import (
    _assert_within_docs,
    _rewrite_feature_tag_block,
    list_documents,
    rename_feature,
)
from .test_rename_feature import _authored_doc, _snapshot_md

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-06-26"


@pytest.fixture(autouse=True)
def _reset_cfg():
    """Reset the process-global config to defaults around every test."""
    reset_config()
    yield
    reset_config()


# ---------------------------------------------------------------------------
# Capability probes (real filesystem; never mocked).
# ---------------------------------------------------------------------------


def _symlinks_supported() -> bool:
    """Return whether this OS/account can create a real symlink right now.

    Attempts a real symlink in a throwaway temp directory. Windows refuses
    symlink creation without developer mode or elevation; on Linux CI this
    always succeeds, so the symlink-requiring tests run there.
    """
    with tempfile.TemporaryDirectory() as raw:
        from pathlib import Path

        base = Path(raw)
        target = base / "probe-target.txt"
        target.write_text("x", encoding="utf-8")
        link = base / "probe-link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        return link.is_symlink()


def _fs_is_case_insensitive(base: Path) -> bool:
    """Return whether *base*'s filesystem resolves names case-insensitively.

    Writes a mixed-case probe file and checks whether its lower-cased name
    resolves to the same entry. Real probe, no assumptions about the OS.
    """
    probe = base / "VsCaseProbe.tmp"
    probe.write_text("x", encoding="utf-8")
    try:
        return (base / "vscaseprobe.tmp").exists()
    finally:
        probe.unlink()


# ---------------------------------------------------------------------------
# Builders that mirror ``test_rename_feature`` but can write anywhere on disk
# (including OUTSIDE the vault, for the external symlink-target documents).
# ---------------------------------------------------------------------------


def _doc_text(
    doc_type: str,
    feature: str,
    *,
    date: str = DATE,
    related: list[str] | None = None,
    body: str | None = None,
) -> str:
    """Render a schema-valid document body as text."""
    if related:
        rel_block = "related:\n" + "".join(f"  - '[[{r}]]'\n" for r in related)
    else:
        rel_block = "related: []\n"
    if body is None:
        body = f"# {feature} {doc_type}\n\nBody for {feature}.\n"
    return (
        f"---\ntags:\n  - '#{doc_type}'\n  - '#{feature}'\n"
        f"date: '{date}'\nmodified: '{date}'\n{rel_block}---\n\n{body}"
    )


def _write(path: Path, text: str) -> Path:
    """Write *text* (UTF-8) to *path*, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _snapshot_real_md(root: Path) -> dict[Path, bytes]:
    """Snapshot bytes of every NON-symlink ``.md`` document under ``.vault``.

    Unlike ``_snapshot_md`` (which follows symlinks via ``is_file()``), this
    captures only legitimate regular vault files so symlink-targeted bytes
    never enter the comparison set; the symlink and its external target are
    asserted separately.
    """
    vault = root / ".vault"
    return {
        p: p.read_bytes()
        for p in vault.rglob("*.md")
        if p.is_file() and not p.is_symlink()
    }


# ---------------------------------------------------------------------------
# Argument injection via the ``new`` target (no symlinks required).
#
# Each crafted target must be refused by the validation gate before any plan
# is computed, leaving the vault byte-identical.
# ---------------------------------------------------------------------------

_MALFORMED_TARGETS = [
    pytest.param("../evil", id="parent-traversal"),
    pytest.param("../../etc", id="deep-traversal"),
    pytest.param("a/b", id="posix-separator"),
    pytest.param("a\\b", id="windows-separator"),
    pytest.param("/abs", id="absolute-posix"),
    pytest.param("C:evil", id="windows-drive"),
    pytest.param("feat\x00nul", id="null-byte"),
    pytest.param("feat\nnewline", id="embedded-newline"),
    pytest.param("feat.*regex", id="regex-metachars"),
    pytest.param("feat(grp)", id="regex-group"),
    pytest.param("feat[set]", id="regex-charclass"),
    pytest.param("UPPER", id="uppercase"),
    pytest.param("_leading", id="leading-underscore"),
    pytest.param("-leading", id="leading-hyphen"),
    # U+0430 CYRILLIC SMALL LETTER A homoglyph, written as an escape so the
    # source stays ASCII-clean while still exercising the homoglyph rejection.
    pytest.param("fe\u0430ture", id="cyrillic-homoglyph"),
]


class TestTargetArgumentInjection:
    @pytest.mark.parametrize("new", _MALFORMED_TARGETS)
    def test_malformed_target_refuses_and_no_mutation(self, tmp_path: Path, new: str):
        _authored_doc(tmp_path, "research", "real-feature")
        before = _snapshot_md(tmp_path)

        with pytest.raises(VaultSpecError):
            rename_feature(tmp_path, "real-feature", new)

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before), (
            f"injection target {new!r} added/removed a document"
        )
        for path, original in before.items():
            assert after[path] == original, f"injection target {new!r} mutated {path}"

    def test_trailing_hyphen_target_is_accepted_kebab_and_stays_in_bounds(
        self, tmp_path: Path
    ):
        # A trailing hyphen is permitted by the kebab gate
        # (``^[a-z0-9][a-z0-9-]*$``), consistent with the schema feature-tag
        # form (``^#[a-z0-9-]+$``). It is therefore NOT an injection vector:
        # asserting it raises would test for behaviour the spec intentionally
        # lacks. The real security property is that the accepted name still
        # produces only in-vault paths and loses no data.
        _authored_doc(tmp_path, "research", "real-feature")

        result = rename_feature(tmp_path, "real-feature", "trailing-")
        assert result["status"] == "updated"

        vault = tmp_path / ".vault"
        for entry in result["paths"]:
            new_abs = (tmp_path / entry["new"]).resolve()
            assert vault.resolve() in new_abs.parents, (
                f"renamed file escaped the vault: {entry['new']}"
            )
        # Every document still lives under .vault and is readable.
        assert list_documents(tmp_path, feature="trailing-")
        assert list_documents(tmp_path, feature="real-feature") == []


# ---------------------------------------------------------------------------
# Argument injection via the ``old`` source (shape gate / defense in depth).
# ---------------------------------------------------------------------------

_MALFORMED_SOURCES = [
    pytest.param("../x", id="parent-traversal"),
    pytest.param("a/b", id="posix-separator"),
    pytest.param("x\x00", id="null-byte"),
    pytest.param("..", id="dotdot"),
]


class TestSourceArgumentInjection:
    @pytest.mark.parametrize("old", _MALFORMED_SOURCES)
    def test_malformed_source_refuses_and_no_mutation(self, tmp_path: Path, old: str):
        _authored_doc(tmp_path, "research", "real-feature")
        before = _snapshot_md(tmp_path)

        with pytest.raises(VaultSpecError):
            rename_feature(tmp_path, old, "new-feature")

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"injection source {old!r} mutated {path}"


# ---------------------------------------------------------------------------
# Reserved names: DocType values and Windows device names are refused.
# ---------------------------------------------------------------------------

_RESERVED_TARGETS = [
    pytest.param(name, id=f"doctype-{name}")
    for name in ("adr", "audit", "exec", "plan", "reference", "research", "index")
] + [
    pytest.param(name, id=f"windev-{name}")
    for name in ("con", "aux", "nul", "com1", "lpt1")
]


class TestReservedTargetNames:
    @pytest.mark.parametrize("new", _RESERVED_TARGETS)
    def test_reserved_target_refuses_and_no_mutation(self, tmp_path: Path, new: str):
        _authored_doc(tmp_path, "research", "real-feature")
        before = _snapshot_md(tmp_path)

        with pytest.raises(VaultSpecError):
            rename_feature(tmp_path, "real-feature", new)

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"reserved target {new!r} mutated {path}"


# ---------------------------------------------------------------------------
# Containment guard unit tests (lexical cases need no symlink).
# ---------------------------------------------------------------------------


class TestContainmentGuardUnit:
    def test_within_docs_returns_contained_path(self, tmp_path: Path):
        docs_dir = tmp_path / ".vault"
        docs_dir.mkdir()
        candidate = docs_dir / "adr" / "2026-06-26-x-adr.md"
        assert _assert_within_docs(docs_dir, candidate) == candidate

    def test_sibling_outside_docs_raises(self, tmp_path: Path):
        docs_dir = tmp_path / ".vault"
        docs_dir.mkdir()
        with pytest.raises(VaultSpecError, match="outside the managed directory tree"):
            _assert_within_docs(docs_dir, docs_dir.parent / "outside.md")

    def test_parent_traversal_raises(self, tmp_path: Path):
        docs_dir = tmp_path / ".vault"
        docs_dir.mkdir()
        traversal = docs_dir / "adr" / ".." / ".." / "outside.md"
        with pytest.raises(VaultSpecError, match="outside the managed directory tree"):
            _assert_within_docs(docs_dir, traversal)


# ---------------------------------------------------------------------------
# Symlink: out-of-bounds protection (real symlinks; OS-capability gated).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _symlinks_supported(), reason="OS symlink creation not permitted"
)
class TestSymlinkOutOfBounds:
    def test_bystander_symlink_not_in_feature_is_untouched(self, tmp_path: Path):
        # A real external .md with a DIFFERENT feature tag, reached through an
        # in-vault symlink that is not part of the renamed feature.
        external = tmp_path / "external" / "secret.md"
        _write(external, _doc_text("adr", "bystander-ext", body="# EXTERNAL-SECRET\n"))
        external_before = external.read_bytes()

        _authored_doc(tmp_path, "research", "real-feature")
        link = tmp_path / ".vault" / "adr" / "2026-01-01-bystander-adr.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(external)

        result = rename_feature(tmp_path, "real-feature", "new-feature")
        assert result["status"] == "updated"

        # The external target is untouched, the in-vault path is STILL a
        # symlink (never replaced by a snapshot/cascade/stamp write), and the
        # external bytes were never copied into a real vault document.
        assert external.read_bytes() == external_before
        assert link.is_symlink()
        for real_doc in _snapshot_real_md(tmp_path).values():
            assert b"EXTERNAL-SECRET" not in real_doc

    def test_symlink_tagged_to_feature_refuses_via_containment(self, tmp_path: Path):
        # The external target IS tagged to the renamed feature, so the scanner
        # includes the in-vault symlink in the rename plan; the containment
        # backstop must refuse before moving it.
        external = tmp_path / "external" / "adr.md"
        _write(external, _doc_text("adr", "real-feature", body="# EXTERNAL-ADR\n"))
        external_before = external.read_bytes()

        _authored_doc(tmp_path, "research", "real-feature")
        link = tmp_path / ".vault" / "adr" / f"{DATE}-real-feature-adr.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(external)

        # Sanity: the symlink is discovered as part of the feature.
        names = {d.path.name for d in list_documents(tmp_path, feature="real-feature")}
        assert f"{DATE}-real-feature-adr.md" in names

        before = _snapshot_real_md(tmp_path)
        with pytest.raises(VaultSpecError) as excinfo:
            rename_feature(tmp_path, "real-feature", "new-feature")
        assert "outside the managed directory tree" in str(excinfo.value.__cause__)

        after = _snapshot_real_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"refused rename mutated {path}"
        assert external.read_bytes() == external_before
        assert link.is_symlink()

    def test_dry_run_does_not_tag_read_symlinked_source(self, tmp_path: Path):
        # A symlinked source tagged to the feature must not be read through during
        # the dry-run preview's tag-rewrite count; only the real, in-bounds doc is
        # counted. (Reading the external target would be an out-of-bounds read;
        # the apply path refuses the symlinked source outright.)
        external = tmp_path / "external" / "adr.md"
        _write(external, _doc_text("adr", "real-feature", body="# EXTERNAL\n"))
        _authored_doc(tmp_path, "research", "real-feature")
        link = tmp_path / ".vault" / "adr" / f"{DATE}-real-feature-adr.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(external)

        plan = rename_feature(tmp_path, "real-feature", "new-feature", dry_run=True)
        # Only the real research doc is tag-counted; the symlinked adr is skipped,
        # so its external target is never read.
        assert plan["tag_rewrites"] == 1

    def test_index_dir_symlink_escape_refuses_and_rolls_back(self, tmp_path: Path):
        # HIGH#2: ``.vault/index`` is a directory symlink pointing outside the
        # vault. The index regen must be refused on containment, and the
        # already-applied document renames must roll back so the original
        # feature docs survive under their old names byte-for-byte.
        external_index = tmp_path / "external_index"
        external_index.mkdir()

        _authored_doc(tmp_path, "research", "real-feature")
        _authored_doc(
            tmp_path, "adr", "real-feature", related=[f"{DATE}-real-feature-research"]
        )
        index_link = tmp_path / ".vault" / "index"
        index_link.symlink_to(external_index, target_is_directory=True)

        before = _snapshot_real_md(tmp_path)
        with pytest.raises(VaultSpecError) as excinfo:
            rename_feature(tmp_path, "real-feature", "new-feature")
        assert "outside the managed directory tree" in str(excinfo.value.__cause__)

        # No index file was written to the escaped external directory.
        assert list(external_index.glob("*.index.md")) == []

        # The renamed docs were rolled back to their pre-call state.
        after = _snapshot_real_md(tmp_path)
        assert set(after) == set(before), (
            f"rollback added/removed docs: added={set(after) - set(before)} "
            f"removed={set(before) - set(after)}"
        )
        for path, original in before.items():
            assert after[path] == original, f"rollback did not restore {path}"
        research = tmp_path / ".vault" / "research" / f"{DATE}-real-feature-research.md"
        adr = tmp_path / ".vault" / "adr" / f"{DATE}-real-feature-adr.md"
        assert research.is_file() and adr.is_file()

    def test_rollback_through_symlink_preserves_external_target(self, tmp_path: Path):
        # A real mid-apply failure (a directory planted at the 2nd computed
        # destination) forces a reverse-journal rollback while an UNRELATED
        # in-vault symlink to an external file is present. The rollback must
        # never snapshot or restore through the symlink, leaving the external
        # target and every real vault file byte-identical.
        external = tmp_path / "external" / "unrelated.txt.md"
        _write(external, "EXTERNAL-UNRELATED-BYTES\n")
        external_before = external.read_bytes()

        _authored_doc(tmp_path, "research", "widget-engine")
        _authored_doc(
            tmp_path, "adr", "widget-engine", related=[f"{DATE}-widget-engine-research"]
        )
        _authored_doc(
            tmp_path,
            "plan",
            "widget-engine",
            related=[f"{DATE}-widget-engine-adr"],
            extra_fm="tier: L2\n",
        )
        link = tmp_path / ".vault" / "reference" / "2026-01-01-bystander-reference.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(external)

        before = _snapshot_real_md(tmp_path)

        dry = rename_feature(tmp_path, "widget-engine", "gadget-engine", dry_run=True)
        assert len(dry["paths"]) >= 2
        obstacle = tmp_path / dry["paths"][1]["new"]
        obstacle.mkdir(parents=False, exist_ok=False)

        with pytest.raises(VaultSpecError, match="rolled back"):
            rename_feature(tmp_path, "widget-engine", "gadget-engine")

        obstacle.rmdir()

        assert external.read_bytes() == external_before
        assert link.is_symlink()
        after = _snapshot_real_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"rollback did not restore {path}"


# ---------------------------------------------------------------------------
# Malformed / adversarial document content (no symlink required).
# ---------------------------------------------------------------------------


class TestMalformedContent:
    _UNCLOSED = (
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        "  - '#widget-engine'\n"
        "NO CLOSING FENCE HERE\n"
        "- '#widget-engine'\n"
        "# widget-engine body line that must never be mutated\n"
    )

    # A multi-line YAML flow sequence: the full-block frontmatter parser
    # accepts it (so the doc IS in scope), but the line-oriented tag rewriter
    # sees ``tags: [`` alone and must refuse rather than write corrupt YAML.
    _MULTILINE_FLOW = (
        "---\n"
        "tags: [\n"
        "  '#research',\n"
        "  '#widget-engine'\n"
        "]\n"
        "date: '2026-06-26'\n"
        "modified: '2026-06-26'\n"
        "related: []\n"
        "---\n"
        "\n"
        "# body\n"
    )

    def test_unclosed_frontmatter_tag_rewriter_bails(self):
        # The rewriter must refuse to persist a rewrite of a never-closed
        # frontmatter: it returns the content unchanged with changed=False.
        out, changed = _rewrite_feature_tag_block(
            self._UNCLOSED, "widget-engine", "gadget-engine"
        )
        assert out == self._UNCLOSED
        assert changed is False

    def test_unclosed_frontmatter_doc_byte_identical_through_rename(
        self, tmp_path: Path
    ):
        # A real rename of a sibling feature must leave an unclosed-frontmatter
        # document byte-identical: the scanner never routes it into scope and
        # the cascade's missing-fence guard refuses to write it.
        _authored_doc(tmp_path, "research", "real-feature")
        malformed = tmp_path / ".vault" / "adr" / f"{DATE}-real-feature-adr.md"
        _write(malformed, self._UNCLOSED)
        before = malformed.read_bytes()

        result = rename_feature(tmp_path, "real-feature", "new-feature")
        assert result["status"] == "updated"
        assert malformed.read_bytes() == before
        assert malformed.is_file()

    def test_malformed_inline_tags_rewriter_raises(self):
        # The rewriter must refuse (not silently corrupt) an unbalanced inline
        # tags value rather than writing broken YAML back to disk.
        content = (
            "---\n"
            "tags: [unbalanced\n"
            "date: '2026-06-26'\n"
            "modified: '2026-06-26'\n"
            "related: []\n"
            "---\n"
            "\n"
            "# body\n"
        )
        with pytest.raises(VaultSpecError, match="inline tags"):
            _rewrite_feature_tag_block(content, "widget-engine", "gadget-engine")

    def test_malformed_inline_tags_raises_and_rolls_back(self, tmp_path: Path):
        # End to end: a doc whose tags span a multi-line flow sequence parses
        # into scope, but the tag rewriter refuses it mid-apply, forcing a full
        # rollback to a byte-identical vault.
        doc = tmp_path / ".vault" / "research" / f"{DATE}-widget-engine-research.md"
        _write(doc, self._MULTILINE_FLOW)
        before = _snapshot_md(tmp_path)

        with pytest.raises(VaultSpecError, match="rolled back") as excinfo:
            rename_feature(tmp_path, "widget-engine", "gadget-engine")
        assert "inline tags" in str(excinfo.value.__cause__)

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"failed rename mutated {path}"

    def test_non_utf8_body_doc_preserved_and_no_crash(self, tmp_path: Path):
        # A document with invalid UTF-8 in its body is skipped by the scanner
        # (so it is out of scope) and must survive a sibling rename unchanged,
        # without the rename crashing.
        _authored_doc(tmp_path, "adr", "real-feature")
        non_utf8 = (
            tmp_path / ".vault" / "reference" / f"{DATE}-real-feature-reference.md"
        )
        non_utf8.parent.mkdir(parents=True, exist_ok=True)
        raw = (
            b"---\ntags:\n  - '#reference'\n  - '#real-feature'\n"
            b"date: '2026-06-26'\nmodified: '2026-06-26'\nrelated: []\n---\n\n"
            b"# ref \xff\xfe invalid \x80\x81 utf8\n"
        )
        non_utf8.write_bytes(raw)

        result = rename_feature(tmp_path, "real-feature", "new-feature")
        assert result["status"] == "updated"
        assert non_utf8.read_bytes() == raw
        assert non_utf8.is_file()

    def test_crlf_doc_byte_level_preserved_through_rename(self, tmp_path: Path):
        # A CRLF document in the renamed feature keeps CRLF endings byte-for-
        # byte through the tag rewrite, and gains no bare LF or BOM.
        doc = tmp_path / ".vault" / "research" / f"{DATE}-widget-engine-research.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        crlf = (
            "---\r\n"
            "tags:\r\n"
            "  - '#research'\r\n"
            "  - '#widget-engine'\r\n"
            "date: '2026-06-26'\r\n"
            "modified: '2026-06-26'\r\n"
            "related: []\r\n"
            "---\r\n"
            "\r\n"
            "# crlf body\r\n"
        )
        doc.write_bytes(crlf.encode("utf-8"))

        rename_feature(tmp_path, "widget-engine", "gadget-engine")

        renamed = tmp_path / ".vault" / "research" / f"{DATE}-gadget-engine-research.md"
        raw = renamed.read_bytes()
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b""), "a bare LF leaked in"
        assert not raw.startswith(b"\xef\xbb\xbf"), "a spurious BOM was added"
        assert b"#gadget-engine" in raw and b"#widget-engine" not in raw

    def test_bom_crlf_preserved_by_tag_rewriter(self):
        # The tag rewriter preserves a leading UTF-8 BOM and CRLF endings while
        # swapping the feature tag (proved at the unit level: a leading BOM
        # makes a document invisible to the frontmatter scanner, so it never
        # reaches the rewriter through the public rename path).
        bom_crlf = (
            "﻿---\r\n"
            "tags:\r\n"
            "  - '#research'\r\n"
            "  - '#widget-engine'\r\n"
            "date: '2026-06-26'\r\n"
            "modified: '2026-06-26'\r\n"
            "related: []\r\n"
            "---\r\n"
            "\r\n"
            "# body\r\n"
        )
        out, changed = _rewrite_feature_tag_block(
            bom_crlf, "widget-engine", "gadget-engine"
        )
        assert changed is True
        assert out.startswith("﻿")
        assert "\r\n" in out
        assert "\n" not in out.replace("\r\n", ""), "a bare LF leaked in"
        assert "#gadget-engine" in out and "#widget-engine" not in out

    def test_bom_crlf_preserved_through_related_cascade(self, tmp_path: Path):
        # A neighbour BOM+CRLF document whose related: link points into the
        # renamed feature is rewritten by the cascade with its BOM and CRLF
        # endings preserved byte-for-byte.
        _authored_doc(tmp_path, "research", "widget-engine")
        neighbour = tmp_path / ".vault" / "adr" / f"{DATE}-neighbour-adr.md"
        neighbour.parent.mkdir(parents=True, exist_ok=True)
        bom_crlf = (
            "﻿---\r\n"
            "tags:\r\n"
            "  - '#adr'\r\n"
            "  - '#neighbour'\r\n"
            f"date: '{DATE}'\r\n"
            f"modified: '{DATE}'\r\n"
            "related:\r\n"
            f"  - '[[{DATE}-widget-engine-research]]'\r\n"
            "---\r\n"
            "\r\n"
            "# neighbour\r\n"
        )
        neighbour.write_bytes(bom_crlf.encode("utf-8"))

        rename_feature(tmp_path, "widget-engine", "gadget-engine")

        raw = neighbour.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), "BOM dropped by cascade"
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b""), "a bare LF leaked in"
        assert b"gadget-engine-research" in raw
        assert b"widget-engine-research" not in raw


# ---------------------------------------------------------------------------
# Collision / data-loss: no document is ever silently overwritten.
# ---------------------------------------------------------------------------


class TestCollisionDataLoss:
    def _audit(self, root: Path, feature: str, topic: str) -> Path:
        path = root / ".vault" / "audit" / f"{DATE}-{feature}-{topic}-audit.md"
        return _write(
            path,
            _doc_text("audit", feature, body=f"# {topic}\n\nBODY-{topic}.\n"),
        )

    def test_normcase_destination_collision_no_data_loss(self, tmp_path: Path):
        # ``widget-engine-perf`` and ``gadget-engine-PERF`` differ in more than
        # case, so both coexist on every filesystem. After renaming
        # widget-engine -> gadget-engine the source's destination
        # (``gadget-engine-perf-audit.md``) is normcase-equal to the existing
        # ``gadget-engine-PERF-audit.md`` on a case-insensitive filesystem.
        self._audit(tmp_path, "widget-engine", "perf")
        self._audit(tmp_path, "gadget-engine", "PERF")
        before = _snapshot_md(tmp_path)

        if _fs_is_case_insensitive(tmp_path):
            # The destinations collide case-insensitively: the rename must
            # refuse (even in dry-run) and overwrite nothing.
            with pytest.raises(VaultSpecError, match="collision"):
                rename_feature(tmp_path, "widget-engine", "gadget-engine", force=True)
            with pytest.raises(VaultSpecError, match="collision"):
                rename_feature(
                    tmp_path,
                    "widget-engine",
                    "gadget-engine",
                    force=True,
                    dry_run=True,
                )
            after = _snapshot_md(tmp_path)
            assert set(after) == set(before)
            for path, original in before.items():
                assert after[path] == original, f"collision refusal mutated {path}"
        else:
            # On a case-sensitive filesystem the two destinations are genuinely
            # distinct files: the merge succeeds and BOTH bodies survive on
            # disk (no silent overwrite / data loss).
            result = rename_feature(
                tmp_path, "widget-engine", "gadget-engine", force=True
            )
            assert result["status"] == "updated"
            on_disk = b"".join(
                p.read_bytes()
                for p in (tmp_path / ".vault").rglob("*.md")
                if p.is_file()
            )
            assert b"BODY-perf." in on_disk
            assert b"BODY-PERF." in on_disk
