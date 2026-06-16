"""CLI tests for the composed vault edit verbs.

Exercises ``vault set-body``, ``vault set-frontmatter``, and ``vault edit``
through the real Typer CliRunner against on-disk vault fixtures (no mocks).

Coverage:
    - blob_hash: git-blob-OID parity for known byte vectors
    - set-body: success (updated + post-write blob_hash), refuse-on-error
      (invalid frontmatter blocks the write, file unchanged), blob-hash
      conflict (stale expected hash refuses, file unchanged), --dry-run
      writes nothing
    - set-frontmatter: validate-then-write (good edit lands), refuse on bad
      tags (file unchanged)
    - edit: combined atomic body+frontmatter write
    - exit codes: 0 updated/unchanged, 1 conflict/refusal/resolution failure
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

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


def _make_vault(tmp_path: Path) -> Path:
    """Build a minimal installed vault with one valid ADR.

    Returns the project root holding ``.vault/adr/2026-01-01-alpha-adr.md``
    and an installed ``.vaultspec/`` framework so the workspace resolves.
    """
    root = tmp_path / "project"
    root.mkdir()
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_VALID_ADR, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(
        _VALID_ADR.replace("# Demo ADR", "# Beta ADR"), encoding="utf-8"
    )

    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.commands import install_run
    from vaultspec_core.core.types import init_paths

    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    layout = resolve_workspace(target_override=root)
    init_paths(layout)
    return root


def _doc(root: Path) -> Path:
    """Return the path to the primary fixture ADR."""
    return root / ".vault" / "adr" / "2026-01-01-alpha-adr.md"


def _run(runner, *args: str, target: Path, stdin: str | None = None) -> Result:
    """Invoke the CLI with ``--target`` and optional stdin."""
    return runner.invoke(app, ["--target", str(target), *args], input=stdin)


def _envelope(result: Result) -> dict:
    """Parse the JSON envelope from a CLI result, asserting it is present."""
    return json.loads(result.output)


# ---------------------------------------------------------------------------
# blob_hash parity
# ---------------------------------------------------------------------------


class TestBlobHashParity:
    def test_empty_blob_known_vector(self):
        # The git blob OID of the empty string is a fixed, well-known value.
        assert git_blob_oid(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"

    def test_hello_blob_known_vector(self):
        # `printf 'hello\n' | git hash-object --stdin` => ce0136...
        assert git_blob_oid(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"

    def test_matches_header_construction(self):
        # The hash is sha1("blob <len>\0<data>"); reconstruct independently.
        import hashlib

        data = b"some document bytes\nwith two lines\n"
        expected = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data,
            usedforsecurity=False,
        ).hexdigest()
        assert git_blob_oid(data) == expected


# ---------------------------------------------------------------------------
# set-body
# ---------------------------------------------------------------------------


class TestSetBody:
    def test_success_returns_updated_and_post_hash(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        body_file = tmp_path / "newbody.md"
        body_file.write_text("\n# Demo ADR\n\nReplaced body.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        env = _envelope(result)
        assert env["schema"] == "vaultspec.vault.set-body.v1"
        assert env["status"] == "updated"

        # The returned blob_hash matches the actual on-disk bytes post-write.
        on_disk = _doc(root).read_bytes()
        assert env["data"]["blob_hash"] == git_blob_oid(on_disk)
        assert b"Replaced body." in on_disk
        # Frontmatter survived byte-for-byte (still carries the original tags).
        assert b"#test-feat" in on_disk

    def test_stdin_channel(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-stdin",
            "--json",
            target=root,
            stdin="\n# Demo ADR\n\nFrom stdin.\n",
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["status"] == "updated"
        assert b"From stdin." in _doc(root).read_bytes()

    def test_refuse_on_error_leaves_file_unchanged(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        # Corrupt the fixture's frontmatter so the proposed content is invalid
        # (a single tag fails the >=2-tag rule). The body replacement is fine,
        # but the document as a whole is non-conformant and must be refused.
        bad = (
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "date: '2026-01-01'\n"
            "modified: '2026-01-01'\n"
            "related: []\n"
            "---\n"
            "\n# Bad ADR\n"
        )
        _doc(root).write_text(bad, encoding="utf-8")
        before = _doc(root).read_bytes()

        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Bad ADR\n\nNew body.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        env = _envelope(result)
        assert env["status"] == "failed"
        assert env["data"]["refused"] is True
        assert any(d["severity"] == "error" for d in env["data"]["checks"])
        # The file is untouched.
        assert _doc(root).read_bytes() == before

    def test_no_check_allows_warning_but_still_blocks_error(self, runner, tmp_path):
        # --no-check skips the snapshot checkers, but the frontmatter model
        # validator still runs and an ERROR still refuses the write.
        root = _make_vault(tmp_path)
        bad = (
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "date: '2026-01-01'\n"
            "modified: '2026-01-01'\n"
            "related: []\n"
            "---\n"
            "\n# Bad ADR\n"
        )
        _doc(root).write_text(bad, encoding="utf-8")
        before = _doc(root).read_bytes()
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Bad ADR\n\nNew body.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--no-check",
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        assert _envelope(result)["data"]["refused"] is True
        assert _doc(root).read_bytes() == before

    def test_blob_hash_conflict_refuses(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Demo ADR\n\nNope.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--expected-blob-hash",
            "deadbeef" * 5,
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        env = _envelope(result)
        assert env["status"] == "failed"
        assert env["data"]["conflict"] is True
        assert env["data"]["expected"] == "deadbeef" * 5
        assert env["data"]["actual"] == git_blob_oid(before)
        # No write occurred.
        assert _doc(root).read_bytes() == before

    def test_blob_hash_match_allows_write(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        current = git_blob_oid(_doc(root).read_bytes())
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Demo ADR\n\nMatched.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--expected-blob-hash",
            current,
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["status"] == "updated"
        assert b"Matched." in _doc(root).read_bytes()

    def test_dry_run_writes_nothing(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Demo ADR\n\nDry run only.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        env = _envelope(result)
        assert env["data"]["dry_run"] is True
        assert env["data"]["changed"] is True
        # File is unchanged on disk.
        assert _doc(root).read_bytes() == before
        # The previewed blob_hash equals what a real write would produce.
        result2 = _run(
            runner,
            "vault",
            "set-body",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--json",
            target=root,
        )
        assert env["data"]["blob_hash"] == _envelope(result2)["data"]["blob_hash"]

    def test_unresolvable_ref_fails(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        body_file = tmp_path / "b.md"
        body_file.write_text("body\n", encoding="utf-8")
        result = _run(
            runner,
            "vault",
            "set-body",
            "no-such-document",
            "--body-file",
            str(body_file),
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        assert _envelope(result)["status"] == "failed"


# ---------------------------------------------------------------------------
# set-frontmatter
# ---------------------------------------------------------------------------


class TestSetFrontmatter:
    def test_set_date_validates_then_writes(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "set-frontmatter",
            "2026-01-01-alpha-adr",
            "--date",
            "2026-02-02",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["status"] == "updated"
        text = _doc(root).read_text(encoding="utf-8")
        assert "date: '2026-02-02'" in text
        # The body survived the frontmatter edit byte-for-byte.
        assert "Original body." in text

    def test_set_related_resolves_and_writes(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "set-frontmatter",
            "2026-01-01-alpha-adr",
            "--related",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        text = _doc(root).read_text(encoding="utf-8")
        assert "[[2026-01-01-beta-adr]]" in text

    def test_refuse_on_bad_tags(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        # A single tag fails the >=2-tag and one-feature-tag rules.
        result = _run(
            runner,
            "vault",
            "set-frontmatter",
            "2026-01-01-alpha-adr",
            "--tags",
            "#adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        env = _envelope(result)
        assert env["status"] == "failed"
        assert env["data"]["errors"]
        assert _doc(root).read_bytes() == before

    def test_nothing_to_edit_fails(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "set-frontmatter",
            "2026-01-01-alpha-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        assert _envelope(result)["status"] == "failed"

    def test_dry_run_writes_nothing(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        result = _run(
            runner,
            "vault",
            "set-frontmatter",
            "2026-01-01-alpha-adr",
            "--date",
            "2026-03-03",
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["data"]["dry_run"] is True
        assert _doc(root).read_bytes() == before


# ---------------------------------------------------------------------------
# edit (combined)
# ---------------------------------------------------------------------------


class TestEdit:
    def test_combined_atomic_write(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Demo ADR\n\nCombined body.\n", encoding="utf-8")

        result = _run(
            runner,
            "vault",
            "edit",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--date",
            "2026-04-04",
            "--related",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        env = _envelope(result)
        assert env["schema"] == "vaultspec.vault.edit.v1"
        assert env["status"] == "updated"

        text = _doc(root).read_text(encoding="utf-8")
        # All three edits landed in one write.
        assert "Combined body." in text
        assert "date: '2026-04-04'" in text
        assert "[[2026-01-01-beta-adr]]" in text
        assert env["data"]["blob_hash"] == git_blob_oid(_doc(root).read_bytes())

    def test_frontmatter_only_edit(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "edit",
            "2026-01-01-alpha-adr",
            "--date",
            "2026-05-05",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["status"] == "updated"
        text = _doc(root).read_text(encoding="utf-8")
        assert "date: '2026-05-05'" in text
        assert "Original body." in text

    def test_nothing_to_edit_fails(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "edit",
            "2026-01-01-alpha-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        assert _envelope(result)["status"] == "failed"

    def test_dry_run_writes_nothing(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        body_file = tmp_path / "b.md"
        body_file.write_text("\n# Demo ADR\n\nDry combined.\n", encoding="utf-8")
        result = _run(
            runner,
            "vault",
            "edit",
            "2026-01-01-alpha-adr",
            "--body-file",
            str(body_file),
            "--date",
            "2026-06-06",
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _envelope(result)["data"]["dry_run"] is True
        assert _doc(root).read_bytes() == before

    def test_conflict_refuses_combined(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _doc(root).read_bytes()
        result = _run(
            runner,
            "vault",
            "edit",
            "2026-01-01-alpha-adr",
            "--date",
            "2026-07-07",
            "--expected-blob-hash",
            "0" * 40,
            "--json",
            target=root,
        )
        assert result.exit_code == 1, result.output
        env = _envelope(result)
        assert env["data"]["conflict"] is True
        assert _doc(root).read_bytes() == before
