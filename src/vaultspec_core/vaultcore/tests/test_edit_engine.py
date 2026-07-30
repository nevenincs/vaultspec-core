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
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory
from vaultspec_core.vaultcore.blob_hash import git_blob_oid
from vaultspec_core.vaultcore.edit_engine import (
    EditError,
    EditResult,
    _compose_new_text,
    _write_proposed,
    document_lock_target,
    enforce_blob_hash,
    execute_edit,
    resolve_document_path,
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
def vault_root() -> Iterator[Path]:
    """Yield an installed vault root holding two valid ADRs.

    Built via :class:`WorkspaceFactory` over a stdlib ``tempfile`` root and
    torn down after the test; the global path context is initialised so the
    engine's scanner, resolver, and checkers resolve the target.
    """
    reset_config()
    root = Path(tempfile.mkdtemp(prefix="vsc-edit-engine-")).resolve()
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
    def test_stem_resolves_to_backing_file(self, vault_root: Path) -> None:
        resolved = resolve_document_path("2026-01-01-alpha-adr", vault_root)
        assert resolved == _doc(vault_root)

    def test_unknown_ref_raises_typed_error(self, vault_root: Path) -> None:
        with pytest.raises(EditError) as excinfo:
            resolve_document_path("no-such-document", vault_root)
        assert excinfo.value.data["path"] == "no-such-document"


# ---------------------------------------------------------------------------
# blob-hash conflict
# ---------------------------------------------------------------------------


class TestBlobHashConflict:
    def test_guard_raises_typed_conflict(self, vault_root: Path) -> None:
        doc = _doc(vault_root)
        stale = "deadbeef" * 5
        with pytest.raises(EditError) as excinfo:
            enforce_blob_hash(doc, stale)
        data = excinfo.value.data
        assert data["conflict"] is True
        assert data["expected"] == stale
        assert data["actual"] == git_blob_oid(doc.read_bytes())

    def test_matching_hash_is_a_noop(self, vault_root: Path) -> None:
        doc = _doc(vault_root)
        current = git_blob_oid(doc.read_bytes())
        # No exception is the assertion: a matching guard permits the write.
        assert enforce_blob_hash(doc, current) is None

    def test_execute_edit_folds_conflict_into_failed_result(
        self, vault_root: Path
    ) -> None:
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
# concurrency: the guard-through-write sequence is lock-serialized
# ---------------------------------------------------------------------------


class TestConcurrencyGuard:
    """Proves the check-to-write window is closed, not merely narrow.

    ``enforce_blob_hash`` alone only compares hashes; it takes no lock. If
    the write that follows a passing check is not serialized against other
    writers, two concurrent editors can both read the same stale hash, both
    pass the check before either writes, and the second write silently
    clobbers the first with no conflict ever reported - a silent lost
    update, the worst class of bug in this area because nobody sees an
    error. ``execute_edit`` closes this by running the whole guard-through-
    write sequence under a per-document ``advisory_lock``.
    """

    def test_execute_edit_blocks_while_document_lock_is_held(
        self, vault_root: Path
    ) -> None:
        """A concurrent holder of the document's advisory lock blocks the edit.

        Proves ``execute_edit`` actually acquires ``advisory_lock`` on
        ``document_lock_target``'s sentinel for its guard-through-write
        sequence, the same primitive every other docs-domain mutator in this
        codebase (rename, structure cascade) uses to close a check-to-write
        race window. The probe is deterministic, not sleep-based: the holder
        only releases after the blocked-assertion window elapses, so a pass
        cannot be a timing fluke.
        """
        from vaultspec_core.core.helpers import advisory_lock

        doc = _doc(vault_root)
        lock_target = document_lock_target(doc, vault_root)
        # The holder must materialize the runtime lock directory itself -
        # execute_edit only does so for its own (non-dry-run) calls, and here
        # the holder acquires the sentinel first.
        lock_target.parent.mkdir(parents=True, exist_ok=True)
        holder_acquired = threading.Event()
        release_holder = threading.Event()
        worker_done = threading.Event()
        errors: list[Exception] = []
        result_box: list[EditResult] = []

        def _holder() -> None:
            with advisory_lock(lock_target):
                holder_acquired.set()
                assert release_holder.wait(timeout=10.0)

        def _worker() -> None:
            try:
                assert holder_acquired.wait(timeout=10.0)
                result_box.append(
                    execute_edit(
                        vault_root,
                        ref="2026-01-01-alpha-adr",
                        new_body="\n# Demo ADR\n\nWorker body.\n",
                    )
                )
                worker_done.set()
            except Exception as exc:  # surfaced via the post-join assertion
                errors.append(exc)

        holder = threading.Thread(target=_holder, name="lock-holder")
        worker = threading.Thread(target=_worker, name="lock-worker")
        holder.start()
        assert holder_acquired.wait(timeout=10.0)
        worker.start()

        # While the holder owns the sentinel, execute_edit cannot complete.
        assert not worker_done.wait(timeout=0.5), (
            "execute_edit completed while another owner held the document's "
            "advisory lock - the guard-through-write sequence is not "
            "serialized against a concurrent writer"
        )

        release_holder.set()
        assert worker_done.wait(timeout=10.0), (
            "execute_edit never completed after the document lock was released"
        )
        holder.join(timeout=10.0)
        worker.join(timeout=10.0)
        assert not errors, f"worker raised: {errors!r}"
        assert result_box[0].status == "updated"

    def test_concurrent_editors_on_same_stale_hash_never_both_win(
        self, vault_root: Path
    ) -> None:
        """Two editors racing on one hash: exactly one succeeds, one refused.

        Both threads read the document's current blob hash and submit a body
        edit guarded by that SAME hash - the real-world race two concurrent
        editors produce. Because the guard-through-write sequence is lock-
        serialized, whichever thread completes first changes the on-disk
        bytes before the other's guard re-check runs, so the loser's check
        sees the NEW bytes rather than the bytes it originally read and is
        refused. This is deterministic regardless of scheduling: only one
        thread can hold the document lock at a time, so the loser's check
        always runs strictly after the winner's write, never interleaved
        with it. The on-disk content ends up as exactly the winner's body -
        never a mix, never silently overwritten by the loser.
        """
        doc = _doc(vault_root)
        shared_hash = git_blob_oid(doc.read_bytes())
        results: dict[str, EditResult] = {}
        errors: list[Exception] = []

        def _edit(name: str, marker: str) -> None:
            try:
                results[name] = execute_edit(
                    vault_root,
                    ref="2026-01-01-alpha-adr",
                    new_body=f"\n# Demo ADR\n\n{marker}\n",
                    expected_blob_hash=shared_hash,
                )
            except Exception as exc:  # surfaced via the post-join assertion
                errors.append(exc)

        t1 = threading.Thread(target=_edit, args=("a", "Editor A body."))
        t2 = threading.Thread(target=_edit, args=("b", "Editor B body."))
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        assert not errors, f"editors raised: {errors!r}"
        statuses = {results["a"].status, results["b"].status}
        assert statuses == {"updated", "failed"}, (
            "expected exactly one winner and one conflict, got "
            f"a={results['a'].status} b={results['b'].status}"
        )

        winner = results["a"] if results["a"].status == "updated" else results["b"]
        loser = results["b"] if winner is results["a"] else results["a"]
        assert loser.error is not None
        assert loser.error.get("conflict") is True

        on_disk = doc.read_text(encoding="utf-8")
        winner_is_a = winner is results["a"]
        winner_marker = "Editor A body." if winner_is_a else "Editor B body."
        loser_marker = "Editor B body." if winner_is_a else "Editor A body."
        assert winner_marker in on_disk
        assert loser_marker not in on_disk


class TestDocumentLockDoesNotPolluteCorpus:
    """The per-document lock sentinel must not leave a mark beside the doc.

    A sibling ``<document>.md.lock`` is untracked yet NOT covered by
    ``.gitignore``'s managed block (which enumerates lock sentinels by exact
    path for a small fixed set of files it owns, never for arbitrary vault
    documents) - a real edit would leave every touched document with a
    permanent stray file a bare ``git add .`` could commit into the corpus.
    ``document_lock_target`` closes this by deriving the sentinel under the
    docs directory's already-ignored ``data/`` runtime subtree instead of as
    a sibling of the document.
    """

    def test_real_edit_leaves_no_lock_sibling_beside_the_document(
        self, vault_root: Path
    ) -> None:
        doc = _doc(vault_root)
        before_siblings = set(doc.parent.iterdir())

        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nNo stray lock.\n",
        )

        assert result.status == "updated"
        after_siblings = set(doc.parent.iterdir())
        # The edit changed nothing in the document's own directory beyond
        # (possibly) the document itself - no ``.lock``, no ``.bak`` left
        # behind, nothing new alongside the real content.
        assert after_siblings == before_siblings
        assert not doc.with_suffix(".md.lock").exists()
        sibling_lock = doc.parent / f"{doc.name}.lock"
        assert not sibling_lock.exists()

    def test_lock_sentinel_lives_under_the_ignored_data_subtree(
        self, vault_root: Path
    ) -> None:
        doc = _doc(vault_root)
        lock_target = document_lock_target(doc, vault_root)

        # The sentinel sits under <docs_dir>/data/locks/, the same ignored
        # runtime subtree the domain-wide rename sentinel already uses.
        assert "data" in lock_target.parts
        assert "locks" in lock_target.parts
        assert (vault_root / ".vault" / "data").resolve() in lock_target.parents

        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nSentinel location.\n",
        )
        assert result.status == "updated"
        # A real (non-dry-run) edit materializes the runtime lock directory
        # and, having acquired and released the lock, leaves an empty
        # sentinel there - never silently unlocked.
        sentinel = lock_target.with_suffix(lock_target.suffix + ".lock")
        assert sentinel.is_file()
        assert sentinel.stat().st_size == 0

    def test_lock_target_is_deterministic_for_the_same_document(
        self, vault_root: Path
    ) -> None:
        """Two independent resolutions of the same doc derive the same sentinel.

        The guard's whole purpose is serializing concurrent callers on the
        SAME document; if two callers referencing the identical on-disk file
        derived different sentinels the lock would not serialize anything.
        """
        doc = _doc(vault_root)
        first = document_lock_target(doc, vault_root)
        second = document_lock_target(
            resolve_document_path("2026-01-01-alpha-adr", vault_root), vault_root
        )
        assert first == second

    def test_lock_target_differs_across_documents(self, vault_root: Path) -> None:
        alpha = document_lock_target(_doc(vault_root), vault_root)
        beta_path = vault_root / ".vault" / "adr" / "2026-01-01-beta-adr.md"
        beta = document_lock_target(beta_path, vault_root)
        assert alpha != beta

    def test_dry_run_never_creates_the_lock_directory(self, vault_root: Path) -> None:
        """A preview must not materialize on-disk state that a real edit would.

        Mirrors ``advisory_lock``'s own no-side-effects-on-a-missing-parent
        contract: only a real write is worth guaranteeing the guard always
        engages for, per ``execute_edit``'s docstring.
        """
        doc = _doc(vault_root)
        lock_target = document_lock_target(doc, vault_root)
        assert not lock_target.parent.exists()

        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nPreview only.\n",
            dry_run=True,
        )
        assert result.status == "updated"
        assert result.dry_run is True
        assert not lock_target.parent.exists()


class TestVanishedTargetEndToEnd:
    """``execute_edit`` end-to-end when its target vanishes mid-flight.

    Companion to :class:`TestVanishedDocument`, which pins the exposure at
    ``_write_proposed`` directly (a synchronous, deterministic proof - no
    threading needed there, since the file only has to be gone by the time
    that single call runs). This class instead drives the race through the
    public :func:`execute_edit` entry point with a real second thread, to
    prove the OUTER contract - never raise, always return a typed failed
    result - holds however far into the pipeline the vanished target is
    actually discovered.
    """

    def test_execute_edit_never_raises_when_the_target_vanishes_underneath_it(
        self, vault_root: Path
    ) -> None:
        """``execute_edit`` folds a vanished target into a clean failure.

        A holder thread takes the document's own advisory lock first (the
        same deterministic technique used throughout this module), so the
        edit's worker thread is blocked at lock acquisition, having not yet
        touched the file. While the edit is blocked, the holder deletes the
        document directly - unlike a rename, a raw filesystem delete does
        not go through vaultspec-core's lock at all, exactly matching an
        external tool. Once released, the edit proceeds against a target
        that no longer exists. Whichever internal step first observes that
        (compose's pre-existing guard, or the write guard this fix adds -
        both now route through the same ``EditError`` -> ``failed`` fold),
        the one property under test is unconditional: ``execute_edit`` must
        never raise, only ever return a typed failed result.
        """
        from vaultspec_core.core.helpers import advisory_lock

        doc = _doc(vault_root)
        lock_target = document_lock_target(doc, vault_root)
        lock_target.parent.mkdir(parents=True, exist_ok=True)
        holder_acquired = threading.Event()
        release_holder = threading.Event()
        worker_done = threading.Event()
        errors: list[Exception] = []
        result_box: list[EditResult] = []

        def _holder() -> None:
            with advisory_lock(lock_target):
                holder_acquired.set()
                assert release_holder.wait(timeout=10.0)
                doc.unlink()

        def _worker() -> None:
            try:
                assert holder_acquired.wait(timeout=10.0)
                result_box.append(
                    execute_edit(
                        vault_root,
                        ref="2026-01-01-alpha-adr",
                        new_body="\n# Demo ADR\n\nRace the deleter.\n",
                    )
                )
                worker_done.set()
            except Exception as exc:  # THE assertion under test: must not fire
                errors.append(exc)
                worker_done.set()

        holder = threading.Thread(target=_holder, name="deleter-holder")
        worker = threading.Thread(target=_worker, name="edit-worker")
        holder.start()
        assert holder_acquired.wait(timeout=10.0)
        worker.start()

        assert not worker_done.wait(timeout=0.5), (
            "execute_edit completed while the deleter held the document lock"
        )
        release_holder.set()
        assert worker_done.wait(timeout=10.0)
        holder.join(timeout=10.0)
        worker.join(timeout=10.0)

        assert not errors, (
            f"execute_edit raised instead of returning a failed result: {errors!r}"
        )
        assert len(result_box) == 1
        result = result_box[0]
        assert result.status == "failed"
        assert result.error is not None
        assert not doc.exists()


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


class TestCompose:
    def test_frontmatter_edit_preserves_body_and_refreshes_stamp(
        self, vault_root: Path
    ) -> None:
        from vaultspec_core.vaultcore import vault_today

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
        # The modified stamp was refreshed to today (the vault's canonical
        # UTC clock), not left at 2026-01-01.
        today = vault_today().isoformat()
        assert f"modified: '{today}'" in proposed

    def test_body_replacement_keeps_frontmatter(self, vault_root: Path) -> None:
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
    def test_non_conformant_proposal_is_refused_and_file_unchanged(
        self, vault_root: Path
    ) -> None:
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
    def test_set_body_round_trip_updates_then_unchanged(self, vault_root: Path) -> None:
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

    def test_matching_guard_allows_write(self, vault_root: Path) -> None:
        current = git_blob_oid(_doc(vault_root).read_bytes())
        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nGuarded write.\n",
            expected_blob_hash=current,
        )
        assert result.status == "updated"
        assert b"Guarded write." in _doc(vault_root).read_bytes()

    def test_dry_run_writes_nothing(self, vault_root: Path) -> None:
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

    def test_write_proposed_persists_bytes(self, vault_root: Path) -> None:
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

    def test_crlf_document_guard_and_write_agree_on_real_bytes(
        self, vault_root: Path
    ) -> None:
        """A real CRLF document round-trips through the guard without drift.

        The blob hash a caller reads is computed over raw CRLF bytes
        (:func:`git_blob_oid` never text-decodes), so submitting that exact
        hash as ``expected_blob_hash`` must be accepted - a text-mode read
        anywhere on the hashing side would translate CRLF to LF and produce
        a spurious conflict here. The write then preserves the CRLF
        convention for the untouched frontmatter, and the returned
        post-write hash matches a fresh read of the actual on-disk bytes.
        """
        doc = _doc(vault_root)
        crlf_bytes = doc.read_bytes().replace(b"\n", b"\r\n")
        doc.write_bytes(crlf_bytes)
        current_hash = git_blob_oid(doc.read_bytes())

        result = execute_edit(
            vault_root,
            ref="2026-01-01-alpha-adr",
            new_body="\n# Demo ADR\n\nCRLF body.\n",
            expected_blob_hash=current_hash,
        )

        assert result.status == "updated"
        on_disk = doc.read_bytes()
        # The edit did not spuriously conflict, and the untouched
        # frontmatter's CRLF convention survived the round trip.
        assert b"tags:\r\n" in on_disk
        assert b"CRLF body.\r\n" in on_disk
        assert result.blob_hash == git_blob_oid(on_disk)


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


class TestVanishedDocument:
    """A document removed mid-edit must fail cleanly, never raise.

    ``execute_edit``'s contract is that every reachable failure arrives as an
    ``EditResult`` with ``status == "failed"``. That did not hold when the
    target vanished between resolution and write: ``atomic_write_restore``
    copies the original to a ``.bak`` BEFORE its own ``try``, so the read
    raised ``FileNotFoundError`` outside every handler and the bare ``OSError``
    escaped the engine entirely.

    The advisory lock serializes vaultspec-core's own mutators, so a concurrent
    rename can no longer open this window. Nothing binds an external actor
    though - an open editor, a ``git checkout``, a sync client - so the file is
    deleted directly here rather than through a rename. That keeps the test
    meaningful now that the rename path is closed, and pins the contract
    against the cause rather than one route to it.
    """

    def test_write_to_a_vanished_document_raises_edit_error_not_oserror(
        self, vault_root: Path
    ) -> None:
        """The write helper folds a vanished target into the pipeline's error.

        Targeted at ``_write_proposed`` directly rather than through
        ``execute_edit``: with the document already gone, ``execute_edit``
        would fail at RESOLUTION and return a failed result without ever
        reaching the write, so an end-to-end assertion would pass whether or
        not this fix exists. Exercising the write helper is what actually
        pins the behaviour.
        """
        doc = _doc(vault_root)
        doc.unlink()

        with pytest.raises(EditError) as excinfo:
            _write_proposed(doc, "---\ntags: []\n---\n\nBody\n", "\n")

        assert excinfo.value.data.get("write_failed") is True
        assert excinfo.value.data.get("path") == str(doc)
