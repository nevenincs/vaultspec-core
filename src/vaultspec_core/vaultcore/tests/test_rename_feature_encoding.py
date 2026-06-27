"""Byte-fidelity tests for the feature-rename line-ending handling.

These tests prove that the two rewriters in the feature-rename backend -
:func:`vaultspec_core.vaultcore.query._rewrite_feature_tag_block` and
:func:`vaultspec_core.vaultcore.rename_ops.rewrite_incoming_refs` - touch only
the bytes of the lines they intend to edit. Cross-platform vaults carry mixed
line endings (LF, CRLF, classic-Mac CR, and all three mixed in one file) and
exotic in-line separators (form feed U+000C, vertical tab U+000B, NEL U+0085,
LS U+2028, PS U+2029). The previous ``str.splitlines()`` + ``newline.join()``
implementation silently normalized every ending and fabricated line breaks out
of the exotic separators; the :func:`split_keepends` representation preserves
each line's exact terminator.

No test doubles are used. Every fixture is hand-built with :meth:`Path.write_bytes`
and every assertion reads real bytes back with :meth:`Path.read_bytes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from ...config import reset_config
from ..checks._base import CheckResult
from ..query import _rewrite_feature_tag_block, rename_feature
from ..rename_ops import rewrite_incoming_refs, split_keepends

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-06-26"

# The five exotic separators that ``str.splitlines`` treats as line breaks but
# which must survive a rename byte-for-byte because they occur inside prose.
# Spelled as escapes so the literals stay unambiguous to readers and linters.
FF = "\x0c"  # form feed U+000C
VT = "\x0b"  # vertical tab U+000B
NEL = "\x85"  # next line U+0085
LS = "\u2028"  # line separator U+2028
PS = "\u2029"  # paragraph separator U+2029
EXOTICS = f"FF{FF}VT{VT}NEL{NEL}LS{LS}PS{PS}end"


# ---------------------------------------------------------------------------
# Builders and byte-diff helpers
# ---------------------------------------------------------------------------


def _fm_doc(
    nl: str,
    *,
    flow: bool = False,
    feature_tag: str = "#old",
    modified: str = DATE,
    related: list[str] | None = None,
    body: str = "",
) -> str:
    """Build a frontmatter document whose every line is terminated by *nl*."""
    if flow:
        tags = f"tags: ['#exec', '{feature_tag}']{nl}"
    else:
        tags = f"tags:{nl}  - '#exec'{nl}  - '{feature_tag}'{nl}"
    if related:
        rel = f"related:{nl}" + "".join(f"  - '[[{r}]]'{nl}" for r in related)
    else:
        rel = f"related: []{nl}"
    return (
        f"---{nl}{tags}date: '{DATE}'{nl}modified: '{modified}'{nl}{rel}---{nl}{body}"
    )


def _line_diff(before: str, after: str) -> tuple[list[int], list[tuple[int, str, str]]]:
    """Compare *before* and *after* line-by-line via :func:`split_keepends`.

    Returns ``(ending_violations, content_diffs)`` where *ending_violations* is
    the list of logical-line indices whose terminator changed (must be empty for
    a fidelity-preserving rewrite) and *content_diffs* lists
    ``(index, before_content, after_content)`` for every line whose content
    changed.
    """
    bp = split_keepends(before)
    ap = split_keepends(after)
    assert len(bp) == len(ap), (
        "line count changed",
        len(bp),
        len(ap),
    )
    ending_violations = [i for i in range(len(bp)) if bp[i][1] != ap[i][1]]
    content_diffs = [
        (i, bp[i][0], ap[i][0]) for i in range(len(bp)) if bp[i][0] != ap[i][0]
    ]
    return ending_violations, content_diffs


# ===========================================================================
# split_keepends round-trip and shape
# ===========================================================================


class TestSplitKeepends:
    @pytest.mark.parametrize(
        "text",
        [
            "a\nb\n",  # LF
            "a\r\nb\r\n",  # CRLF
            "a\rb\r",  # CR-only
            "a\r\nb\nc\rd",  # mixed, no trailing
            "a\nb",  # no trailing newline
            "",  # empty
            "\n",  # single newline
            "\r\n\r\n",  # blank CRLF lines
            f"a{FF}b\nc{VT}d\n",  # form feed / vertical tab in content
            f"x{NEL}y\nz{LS}w{PS}q\n",  # NEL / LS / PS in content
        ],
    )
    def test_round_trip_is_byte_exact(self, text: str) -> None:
        pairs = split_keepends(text)
        assert "".join(c + e for c, e in pairs) == text

    def test_shapes(self) -> None:
        assert split_keepends("a\nb\n") == [["a", "\n"], ["b", "\n"]]
        assert split_keepends("a\nb") == [["a", "\n"], ["b", ""]]
        assert split_keepends("") == []
        assert split_keepends("\n") == [["", "\n"]]
        assert split_keepends("a\rb\r") == [["a", "\r"], ["b", "\r"]]
        assert split_keepends("a\r\nb") == [["a", "\r\n"], ["b", ""]]

    def test_exotic_separators_stay_inside_content(self) -> None:
        # Each exotic separator must remain in the content slot, never become an
        # ending; the only break is the trailing LF.
        for sep in (FF, VT, NEL, LS, PS):
            assert split_keepends(f"left{sep}right\n") == [[f"left{sep}right", "\n"]]
        # All five at once with no trailing terminator -> a single pair.
        assert split_keepends(EXOTICS) == [[EXOTICS, ""]]


# ===========================================================================
# _rewrite_feature_tag_block byte fidelity
# ===========================================================================


class TestRewriteFeatureTagBlock:
    def _swap(self, src: str) -> tuple[str, bool]:
        return _rewrite_feature_tag_block(src, "old", "new")

    def _assert_byte_exact(self, src: str, expected: str) -> None:
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()

    def test_pure_crlf(self) -> None:
        src = _fm_doc("\r\n", body="# heading\r\nbody\r\n")
        expected = _fm_doc("\r\n", feature_tag="#new", body="# heading\r\nbody\r\n")
        self._assert_byte_exact(src, expected)

    def test_pure_lf(self) -> None:
        src = _fm_doc("\n", body="# heading\nbody\n")
        expected = _fm_doc("\n", feature_tag="#new", body="# heading\nbody\n")
        self._assert_byte_exact(src, expected)

    def test_cr_only_preserves_trailing_cr(self) -> None:
        src = _fm_doc("\r", body="# heading\rbody\r")
        expected = _fm_doc("\r", feature_tag="#new", body="# heading\rbody\r")
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()
        assert out.endswith("\r")
        assert "\n" not in out

    def test_mixed_crlf_lf_cr(self) -> None:
        # Each frontmatter line carries a deliberately different terminator.
        src = (
            "---\r\n"
            "tags:\n"
            "  - '#exec'\r\n"
            "  - '#old'\r"
            "date: '2026-06-26'\n"
            "modified: '2026-06-26'\r"
            "related: []\r\n"
            "---\n"
            f"body{FF}with form feed\nend"
        )
        expected = src.replace("  - '#old'", "  - '#new'")
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()
        violations, diffs = _line_diff(src, out)
        assert violations == []
        assert [(c_before, c_after) for _, c_before, c_after in diffs] == [
            ("  - '#old'", "  - '#new'")
        ]

    def test_exotic_separators_in_body_preserved(self) -> None:
        body = f"# heading\n{EXOTICS}\nmore\n"
        src = _fm_doc("\n", body=body)
        expected = _fm_doc("\n", feature_tag="#new", body=body)
        self._assert_byte_exact(src, expected)
        out, _ = self._swap(src)
        # The exotic glyphs survive intact, on a single body line.
        assert EXOTICS in out

    def test_frontmatter_only_document(self) -> None:
        src = _fm_doc("\n", body="")
        expected = _fm_doc("\n", feature_tag="#new", body="")
        self._assert_byte_exact(src, expected)

    def test_no_trailing_newline(self) -> None:
        src = _fm_doc("\n", body="last line no newline")
        expected = _fm_doc("\n", feature_tag="#new", body="last line no newline")
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()
        assert not out.endswith("\n")

    def test_bom_plus_crlf(self) -> None:
        src = "﻿" + _fm_doc("\r\n", body="body\r\n")
        expected = "﻿" + _fm_doc("\r\n", feature_tag="#new", body="body\r\n")
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()
        assert out.startswith("﻿")

    def test_flow_style_on_crlf_yields_crlf_block_entries(self) -> None:
        src = _fm_doc("\r\n", flow=True, body="body\r\n")
        # Flow ['#exec', '#old'] normalizes to block form with CRLF entries and
        # the feature tag swapped.
        expected = _fm_doc("\r\n", flow=False, feature_tag="#new", body="body\r\n")
        out, changed = self._swap(src)
        assert changed is True
        assert out.encode() == expected.encode()
        assert "  - '#exec'\r\n" in out
        assert "  - '#new'\r\n" in out

    def test_absent_tag_returns_unchanged(self) -> None:
        src = _fm_doc("\r\n", feature_tag="#other", body="body\r\n")
        out, changed = self._swap(src)
        assert changed is False
        assert out.encode() == src.encode()

    def test_unclosed_frontmatter_returns_unchanged(self) -> None:
        src = "---\r\ntags:\r\n  - '#old'\r\nbody never closes\r\n"
        out, changed = self._swap(src)
        assert changed is False
        assert out.encode() == src.encode()


# ===========================================================================
# rewrite_incoming_refs byte fidelity (direct calls)
# ===========================================================================


class TestRewriteIncomingRefsDirect:
    RENAME: ClassVar[list[tuple[str, str]]] = [
        ("2026-06-26-alpha-research", "2026-06-26-gamma-research")
    ]

    def _run(self, root: Path, body: bytes) -> tuple[Path, bytes, bytes]:
        reset_config()
        doc = root / ".vault" / "adr" / "2026-06-26-beta-adr.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_bytes(body)
        before = doc.read_bytes()
        result = CheckResult(check_name="probe")
        rewrite_incoming_refs(root, self.RENAME, result)
        return doc, before, doc.read_bytes()

    def test_mixed_endings_only_link_line_changes(self, tmp_path: Path) -> None:
        body = (
            "---\r\n"
            "tags:\n"
            "  - '#adr'\r\n"
            "  - '#beta'\r"
            "date: '2026-06-26'\n"
            "related:\r\n"
            "  - '[[2026-06-26-alpha-research]]'\r"
            "---\r\n"
            f"prose{FF}with{NEL}exotics\n"
            "tail no newline"
        ).encode()
        _doc, before, after = self._run(tmp_path, body)
        violations, diffs = _line_diff(before.decode(), after.decode())
        assert violations == []
        assert [(b, a) for _, b, a in diffs] == [
            (
                "  - '[[2026-06-26-alpha-research]]'",
                "  - '[[2026-06-26-gamma-research]]'",
            )
        ]
        # The trailing-no-newline tail and exotic body bytes are untouched.
        assert after.endswith(b"tail no newline")
        assert FF.encode() in after
        assert NEL.encode() in after

    def test_cr_only_preserves_trailing_cr(self, tmp_path: Path) -> None:
        body = (
            b"---\r"
            b"tags:\r"
            b"  - '#adr'\r"
            b"  - '#beta'\r"
            b"date: '2026-06-26'\r"
            b"related:\r"
            b"  - '[[2026-06-26-alpha-research]]'\r"
            b"---\r"
            b"body\r"
        )
        _doc, before, after = self._run(tmp_path, body)
        violations, diffs = _line_diff(before.decode(), after.decode())
        assert violations == []
        assert [(b, a) for _, b, a in diffs] == [
            (
                "  - '[[2026-06-26-alpha-research]]'",
                "  - '[[2026-06-26-gamma-research]]'",
            )
        ]
        assert after.endswith(b"\r")
        assert b"\n" not in after

    def test_no_matching_link_is_byte_identical(self, tmp_path: Path) -> None:
        body = (
            b"---\r\n"
            b"tags:\r\n"
            b"  - '#adr'\r\n"
            b"  - '#beta'\r\n"
            b"date: '2026-06-26'\r\n"
            b"related:\r\n"
            b"  - '[[2026-06-26-unrelated-doc]]'\r\n"
            b"---\r\n"
            b"body\r\n"
        )
        _doc, before, after = self._run(tmp_path, body)
        assert after == before

    def test_duplicate_collapse_drops_whole_pair(self, tmp_path: Path) -> None:
        # Renaming alpha -> beta collapses [[...-alpha]] onto the already-present
        # [[...-beta]] that precedes it; the duplicate line and its terminator
        # must both vanish, leaving no blank line or doubled terminator behind.
        reset_config()
        doc = tmp_path / ".vault" / "adr" / "2026-06-26-host-adr.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "---\r\n"
            "tags:\r\n"
            "  - '#adr'\r\n"
            "  - '#host'\r\n"
            "date: '2026-06-26'\r\n"
            "related:\r\n"
            "  - '[[2026-06-26-beta]]'\r\n"
            "  - '[[2026-06-26-alpha]]'\r\n"
            "---\r\n"
            "body\r\n"
        )
        doc.write_bytes(body.encode())
        result = CheckResult(check_name="probe")
        rewrite_incoming_refs(
            tmp_path, [("2026-06-26-alpha", "2026-06-26-beta")], result
        )
        after = doc.read_bytes()
        expected = body.replace("  - '[[2026-06-26-alpha]]'\r\n", "")
        assert after == expected.encode()
        # No blank line or doubled terminator introduced by the drop.
        assert b"\r\n\r\n" not in after.split(b"---\r\n")[1]


# ===========================================================================
# rewrite_incoming_refs byte fidelity (end-to-end rename_feature)
# ===========================================================================


class TestRewriteIncomingRefsEndToEnd:
    OLD = "widget"
    NEW = "gadget"

    def _renamed_research_doc(self, root: Path, nl: str) -> None:
        """Author the feature's single renamed doc with *nl* line endings."""
        doc = root / ".vault" / "research" / f"{DATE}-{self.OLD}-research.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_bytes(_fm_doc(nl, feature_tag=f"#{self.OLD}").encode())

    def _neighbour(self, root: Path, raw: bytes) -> Path:
        """Author a different-feature doc that links into the renamed one."""
        doc = root / ".vault" / "adr" / f"{DATE}-neighbour-adr.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_bytes(raw)
        return doc

    def _assert_link_and_modified_only(self, before: bytes, after: bytes) -> None:
        """Endings all preserved; content changed only on link and modified."""
        violations, diffs = _line_diff(before.decode(), after.decode())
        assert violations == [], "a line ending was normalized"
        changed_before = {b for _, b, _ in diffs}
        link_old = f"  - '[[{DATE}-{self.OLD}-research]]'"
        link_new = f"  - '[[{DATE}-{self.NEW}-research]]'"
        # The link line content changed exactly old -> new.
        link_diffs = [(b, a) for _, b, a in diffs if b == link_old]
        assert link_diffs == [(link_old, link_new)]
        # Every other changed line is the modified: stamp only.
        for _, b, a in diffs:
            if b == link_old:
                continue
            assert b.strip().startswith("modified:")
            assert a.strip().startswith("modified:")
        assert link_old in changed_before

    def test_mixed_endings_neighbour(self, tmp_path: Path) -> None:
        reset_config()
        self._renamed_research_doc(tmp_path, "\n")
        raw = (
            "---\r\n"
            "tags:\n"
            "  - '#adr'\r\n"
            "  - '#neighbour'\r"
            "date: '2026-06-26'\n"
            "modified: '2020-01-01'\r\n"
            "related:\r\n"
            f"  - '[[{DATE}-{self.OLD}-research]]'\r"
            "---\r\n"
            f"prose{FF}exotic{LS}kept\n"
            "no trailing newline"
        ).encode()
        neighbour = self._neighbour(tmp_path, raw)
        before = neighbour.read_bytes()

        rename_feature(tmp_path, self.OLD, self.NEW)

        after = neighbour.read_bytes()
        self._assert_link_and_modified_only(before, after)
        assert after.endswith(b"no trailing newline")
        assert FF.encode() in after
        assert LS.encode() in after

    def test_cr_only_neighbour(self, tmp_path: Path) -> None:
        reset_config()
        self._renamed_research_doc(tmp_path, "\n")
        raw = (
            "---\r"
            "tags:\r"
            "  - '#adr'\r"
            "  - '#neighbour'\r"
            "date: '2026-06-26'\r"
            "modified: '2020-01-01'\r"
            "related:\r"
            f"  - '[[{DATE}-{self.OLD}-research]]'\r"
            "---\r"
            "body\r"
        ).encode()
        neighbour = self._neighbour(tmp_path, raw)
        before = neighbour.read_bytes()

        rename_feature(tmp_path, self.OLD, self.NEW)

        after = neighbour.read_bytes()
        self._assert_link_and_modified_only(before, after)
        assert b"\n" not in after
        assert after.endswith(b"\r")

    def test_exotic_body_neighbour(self, tmp_path: Path) -> None:
        reset_config()
        self._renamed_research_doc(tmp_path, "\n")
        raw = (
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#neighbour'\n"
            "date: '2026-06-26'\n"
            "modified: '2020-01-01'\n"
            "related:\n"
            f"  - '[[{DATE}-{self.OLD}-research]]'\n"
            "---\n"
            f"{EXOTICS}\n"
        ).encode()
        neighbour = self._neighbour(tmp_path, raw)
        before = neighbour.read_bytes()

        rename_feature(tmp_path, self.OLD, self.NEW)

        after = neighbour.read_bytes()
        self._assert_link_and_modified_only(before, after)
        assert EXOTICS.encode() in after

    def test_no_matching_link_neighbour_is_byte_identical(self, tmp_path: Path) -> None:
        reset_config()
        self._renamed_research_doc(tmp_path, "\n")
        raw = (
            b"---\r\n"
            b"tags:\r\n"
            b"  - '#adr'\r\n"
            b"  - '#neighbour'\r\n"
            b"date: '2026-06-26'\r\n"
            b"modified: '2020-01-01'\r\n"
            b"related:\r\n"
            b"  - '[[2026-06-26-someone-else-research]]'\r\n"
            b"---\r\n"
            b"body\r\n"
        )
        neighbour = self._neighbour(tmp_path, raw)
        before = neighbour.read_bytes()

        rename_feature(tmp_path, self.OLD, self.NEW)

        # Not rewritten and not relinked, so its modified stamp is never
        # refreshed: the document is byte-for-byte identical.
        assert neighbour.read_bytes() == before


# ===========================================================================
# Full rename over CRLF / CR-only / mixed feature documents
# ===========================================================================


class TestRenameFeatureDocBytes:
    OLD = "source-feat"
    NEW = "target-feat"

    def _author(self, root: Path, nl: str, body: str) -> Path:
        doc = root / ".vault" / "research" / f"{DATE}-{self.OLD}-research.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_bytes(
            _fm_doc(
                nl, feature_tag=f"#{self.OLD}", modified="2020-01-01", body=body
            ).encode()
        )
        return doc

    def _assert_tag_and_modified_only(self, before: bytes, after: bytes) -> None:
        violations, diffs = _line_diff(before.decode(), after.decode())
        assert violations == [], "a line ending was normalized by the rename"
        tag_old = f"  - '#{self.OLD}'"
        tag_new = f"  - '#{self.NEW}'"
        tag_diffs = [(b, a) for _, b, a in diffs if b == tag_old]
        assert tag_diffs == [(tag_old, tag_new)]
        for _, b, a in diffs:
            if b == tag_old:
                continue
            assert b.strip().startswith("modified:")
            assert a.strip().startswith("modified:")

    def _run(self, tmp_path: Path, nl: str, body: str) -> None:
        reset_config()
        src = self._author(tmp_path, nl, body)
        before = src.read_bytes()
        rename_feature(tmp_path, self.OLD, self.NEW)
        dst = tmp_path / ".vault" / "research" / f"{DATE}-{self.NEW}-research.md"
        assert dst.is_file(), "renamed document not found at expected path"
        assert not src.exists(), "old document path should be gone"
        self._assert_tag_and_modified_only(before, dst.read_bytes())

    def test_crlf_document(self, tmp_path: Path) -> None:
        self._run(tmp_path, "\r\n", body="# heading\r\nbody line\r\n")

    def test_cr_only_document(self, tmp_path: Path) -> None:
        reset_config()
        src = self._author(tmp_path, "\r", body="# heading\rbody line\r")
        before = src.read_bytes()
        rename_feature(tmp_path, self.OLD, self.NEW)
        dst = tmp_path / ".vault" / "research" / f"{DATE}-{self.NEW}-research.md"
        after = dst.read_bytes()
        self._assert_tag_and_modified_only(before, after)
        assert b"\n" not in after
        assert after.endswith(b"\r")

    def test_mixed_document(self, tmp_path: Path) -> None:
        reset_config()
        # Hand-build a single doc with three different terminators plus an
        # exotic body separator.
        raw = (
            "---\r\n"
            "tags:\n"
            "  - '#exec'\r\n"
            f"  - '#{self.OLD}'\r"
            "date: '2026-06-26'\n"
            "modified: '2020-01-01'\r\n"
            "related: []\r\n"
            "---\n"
            f"body{FF}with exotic{PS}sep\nend no newline"
        )
        src = tmp_path / ".vault" / "research" / f"{DATE}-{self.OLD}-research.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(raw.encode())
        before = src.read_bytes()

        rename_feature(tmp_path, self.OLD, self.NEW)

        dst = tmp_path / ".vault" / "research" / f"{DATE}-{self.NEW}-research.md"
        after = dst.read_bytes()
        self._assert_tag_and_modified_only(before, after)
        assert after.endswith(b"end no newline")
        assert FF.encode() in after
        assert PS.encode() in after
