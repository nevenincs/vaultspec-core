"""Concurrency-safety tests for the docs-domain advisory lock.

The rename-convergence work commits every docs-domain mutator - ``vault rename``,
``rename_feature``, and the structure-rename cascade
(``check_structure`` with ``fix=True``) - to one well-known advisory-lock
sentinel (:func:`~vaultspec_core.vaultcore.rename_engine.docs_lock_target`).
These tests prove that commitment deterministically: a holder thread acquires it
and a second caller that targets the SAME sentinel cannot proceed until the
holder releases.

The proofs are real-filesystem, mock-free, and free of sleep-based races. The
only timed wait is a bounded ``Event.wait`` used to assert that the second
caller is blocked WHILE the holder still holds the lock (the holder only
releases AFTER that assertion), so a pass cannot be a timing fluke: the second
caller's completion is strictly ordered after the holder's release.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...core.helpers import advisory_lock
from ..checks.structure import check_structure
from ..models import DocumentMetadata
from ..rename_engine import docs_lock_target

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

    from ..checks._base import VaultSnapshot

pytestmark = [pytest.mark.unit]


# Bounded wait used to confirm the second caller is blocked while the holder
# holds the lock. The holder releases only after this window elapses, so the
# probe cannot pass by luck - the second caller genuinely cannot complete.
_BLOCKED_PROBE_SECONDS = 0.5
# Generous ceiling for an unblocked caller to finish once the lock is free.
_COMPLETION_SECONDS = 10.0


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    """Reset the process-global config to defaults around every test."""
    reset_config()
    yield
    reset_config()


def _prove_serialized_by(lock_target: Path, second_caller: Callable[[], None]) -> None:
    """Assert *second_caller* blocks on *lock_target* until a holder releases.

    Spawns a holder thread that acquires ``advisory_lock(lock_target)`` and
    holds it, then runs *second_caller* (which must itself acquire the same
    sentinel) in a worker thread. The worker is asserted to be unable to finish
    while the holder holds the lock, and to finish once the holder releases.

    Args:
        lock_target: The sentinel both the holder and *second_caller* contend on.
        second_caller: A zero-arg callable performing the lock-protected work.
    """
    holder_acquired = threading.Event()
    release_holder = threading.Event()
    worker_done = threading.Event()
    errors: list[Exception] = []

    def _holder() -> None:
        with advisory_lock(lock_target):
            holder_acquired.set()
            # Hold until the test confirms the worker is blocked.
            assert release_holder.wait(timeout=_COMPLETION_SECONDS)

    def _worker() -> None:
        try:
            assert holder_acquired.wait(timeout=_COMPLETION_SECONDS)
            second_caller()
            worker_done.set()
        except Exception as exc:  # surfaced via the post-join assertion below
            errors.append(exc)

    holder = threading.Thread(target=_holder, name="lock-holder")
    worker = threading.Thread(target=_worker, name="lock-worker")
    holder.start()
    assert holder_acquired.wait(timeout=_COMPLETION_SECONDS)

    worker.start()
    # While the holder owns the sentinel the worker cannot complete.
    assert not worker_done.wait(timeout=_BLOCKED_PROBE_SECONDS), (
        "second caller completed while the docs lock was held - it is not "
        "serializing on the docs_lock_target sentinel"
    )

    # Release the holder; the worker must now run to completion.
    release_holder.set()
    assert worker_done.wait(timeout=_COMPLETION_SECONDS), (
        "second caller never completed after the docs lock was released"
    )

    holder.join(timeout=_COMPLETION_SECONDS)
    worker.join(timeout=_COMPLETION_SECONDS)
    assert not errors, f"worker raised: {errors!r}"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_docs_lock_target_serializes_concurrent_acquirers(tmp_path: Path) -> None:
    """Two acquirers of the docs sentinel run strictly one-after-another.

    The order list is the deterministic proof: the second acquirer's entry is
    recorded only after the first acquirer's release, never interleaved.
    """
    docs_dir = tmp_path / ".vault"
    (docs_dir / "data").mkdir(parents=True)
    target = docs_lock_target(docs_dir)

    order: list[str] = []
    order_guard = threading.Lock()

    def _record(event: str) -> None:
        with order_guard:
            order.append(event)

    second_acquirer = threading.Event()

    def _second() -> None:
        with advisory_lock(target):
            _record("second-acquire")
            second_acquirer.set()

    first_acquired = threading.Event()
    release_first = threading.Event()

    def _first() -> None:
        with advisory_lock(target):
            _record("first-acquire")
            first_acquired.set()
            assert release_first.wait(timeout=_COMPLETION_SECONDS)
            _record("first-release")

    t1 = threading.Thread(target=_first, name="first")
    t2 = threading.Thread(target=_second, name="second")
    t1.start()
    assert first_acquired.wait(timeout=_COMPLETION_SECONDS)
    t2.start()
    # The second acquirer must not get in while the first holds the lock.
    assert not second_acquirer.wait(timeout=_BLOCKED_PROBE_SECONDS)
    release_first.set()
    assert second_acquirer.wait(timeout=_COMPLETION_SECONDS)
    t1.join(timeout=_COMPLETION_SECONDS)
    t2.join(timeout=_COMPLETION_SECONDS)

    assert order == ["first-acquire", "first-release", "second-acquire"]


def test_structure_cascade_blocks_on_held_docs_lock(tmp_path: Path) -> None:
    """``check_structure(fix=True)`` serializes on the docs sentinel.

    The cascade renames a mis-suffixed research doc and rewrites the incoming
    ``related:`` link. With the docs sentinel held it cannot proceed; once
    released it completes and the on-disk state is consistent (the file is
    renamed and the referrer re-pointed - no partial or lost update).
    """
    root = tmp_path
    docs_dir = root / ".vault"
    (docs_dir / "data").mkdir(parents=True)

    misnamed = docs_dir / "research" / "2026-05-15-probe-case.md"
    renamed = docs_dir / "research" / "2026-05-15-probe-case-research.md"
    plan = docs_dir / "plan" / "2026-05-15-probe-plan.md"
    _write(
        misnamed,
        "---\ntags:\n  - '#research'\n  - '#probe'\n"
        "date: '2026-05-15'\nmodified: '2026-05-15'\nrelated: []\n---\n\n# Probe\n",
    )
    _write(
        plan,
        "---\ntags:\n  - '#plan'\n  - '#probe'\n"
        "date: '2026-05-15'\nmodified: '2026-05-15'\n"
        "related:\n  - '[[2026-05-15-probe-case]]'\n---\n\n# Probe plan\n",
    )

    snapshot: VaultSnapshot = {
        misnamed: (
            DocumentMetadata(
                tags=["#research", "#probe"], date="2026-05-15", related=[]
            ),
            "",
        ),
        plan: (
            DocumentMetadata(
                tags=["#plan", "#probe"],
                date="2026-05-15",
                related=["[[2026-05-15-probe-case]]"],
            ),
            "",
        ),
    }

    result_box: list[object] = []

    def _run_cascade() -> None:
        result_box.append(check_structure(root, snapshot=snapshot, fix=True))

    _prove_serialized_by(docs_lock_target(docs_dir), _run_cascade)

    # The cascade ran to completion after the lock was released.
    assert renamed.exists()
    assert not misnamed.exists()
    assert "[[2026-05-15-probe-case-research]]" in plan.read_text(encoding="utf-8")
    assert "[[2026-05-15-probe-case]]" not in plan.read_text(encoding="utf-8")


_ALPHA = (
    "---\ntags:\n  - '#adr'\n  - '#concurrency'\n"
    "date: '2026-01-01'\nmodified: '2026-01-01'\nrelated: []\n---\n\n# Alpha\n"
)
_BETA = (
    "---\ntags:\n  - '#adr'\n  - '#concurrency'\n"
    "date: '2026-01-01'\nmodified: '2026-01-01'\n"
    "related:\n  - '[[2026-01-01-alpha-adr]]'\n---\n\n# Beta\n"
)


def test_document_rename_blocks_on_held_docs_lock(tmp_path: Path) -> None:
    """``vault rename`` serializes on the docs sentinel.

    With the docs sentinel held, a real document rename cannot proceed; once
    released it completes and the final state is consistent: the file is moved,
    the old path is gone, and the incoming link is re-pointed (no lost update).
    Drives the rename through the public CLI entry point (``vault rename``)
    rather than the private ``_execute_rename`` helper it dispatches to.
    """
    from typer.testing import CliRunner

    from ...cli import app
    from ...core.commands import install_run

    root = tmp_path / "project"
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_ALPHA, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(_BETA, encoding="utf-8")
    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    # Materialise the lock-file parent so the advisory lock actually engages.
    (root / ".vault" / "data").mkdir(parents=True, exist_ok=True)

    docs_dir = root / ".vault"
    alpha = adr_dir / "2026-01-01-alpha-adr.md"
    beta = adr_dir / "2026-01-01-beta-adr.md"
    gamma = adr_dir / "2026-01-01-gamma-adr.md"

    def _run_rename() -> None:
        result = CliRunner().invoke(
            app,
            [
                "--target",
                str(root),
                "vault",
                "rename",
                "2026-01-01-alpha-adr",
                "--to",
                "2026-01-01-gamma-adr",
                "--no-check",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output

    _prove_serialized_by(docs_lock_target(docs_dir), _run_rename)

    # The rename ran to completion after the lock was released.
    assert gamma.exists()
    assert not alpha.exists()
    beta_text = beta.read_text(encoding="utf-8")
    assert "[[2026-01-01-gamma-adr]]" in beta_text
    assert "[[2026-01-01-alpha-adr]]" not in beta_text


def test_rename_blocks_while_the_renamed_document_is_locked_by_an_edit(
    tmp_path: Path,
) -> None:
    """``vault rename`` now serializes against a concurrent edit of the SAME doc.

    Closes repro B from the blob-hash concurrency audit: before this fix,
    ``execute_edit``'s per-document lock and the rename's domain lock were two
    disjoint sentinels, so a rename could complete while an edit of the SAME
    document was still in flight. The edit's eventual write - landing after
    the rename had already moved the file - silently RESURRECTED the old
    path: the renamed file left stale (missing the edit) and an orphaned
    duplicate at the old name with no incoming links (reproduced with real
    threads during the audit; the fix below makes that interleaving
    unconstructible, so this test proves the lock rather than re-deriving the
    race). With the renamed document's own advisory lock held by another
    holder, ``vault rename`` must block, and once released must complete
    correctly with no resurrection.
    """
    from typer.testing import CliRunner

    from ...cli import app
    from ...core.commands import install_run
    from ..edit_engine import document_lock_target

    root = tmp_path / "project"
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_ALPHA, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(_BETA, encoding="utf-8")
    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    # Materialise the lock-file parent so the advisory lock actually engages.
    (root / ".vault" / "data").mkdir(parents=True, exist_ok=True)

    alpha = adr_dir / "2026-01-01-alpha-adr.md"
    gamma = adr_dir / "2026-01-01-gamma-adr.md"
    lock_target = document_lock_target(alpha, root)
    lock_target.parent.mkdir(parents=True, exist_ok=True)

    def _run_rename() -> None:
        result = CliRunner().invoke(
            app,
            [
                "--target",
                str(root),
                "vault",
                "rename",
                "2026-01-01-alpha-adr",
                "--to",
                "2026-01-01-gamma-adr",
                "--no-check",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output

    _prove_serialized_by(lock_target, _run_rename)

    # No resurrection: the old path is gone and the new path exists - never a
    # stale-and-orphaned pair.
    assert gamma.exists()
    assert not alpha.exists()


def test_rename_blocks_while_a_referrer_document_is_locked_by_an_edit(
    tmp_path: Path,
) -> None:
    """``vault rename`` also serializes against an edit of a REFERRER document.

    Closes the wider half of the same gap: the cascade rewrites ``beta``'s
    ``related:`` block to point at the renamed stem, so an edit racing on
    ``beta`` (not the renamed document itself) needs the same exclusion, or
    the cascade's write and the edit's write could still race each other even
    with only the renamed document locked.
    :func:`~vaultspec_core.vaultcore.rename_ops.find_rewrite_targets` computes
    exactly this referrer set before the mutation begins, and the rename
    locks every document in it, sorted, alongside the renamed document.
    """
    from typer.testing import CliRunner

    from ...cli import app
    from ...core.commands import install_run
    from ..edit_engine import document_lock_target

    root = tmp_path / "project"
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_ALPHA, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(_BETA, encoding="utf-8")
    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    (root / ".vault" / "data").mkdir(parents=True, exist_ok=True)

    alpha = adr_dir / "2026-01-01-alpha-adr.md"
    beta = adr_dir / "2026-01-01-beta-adr.md"
    gamma = adr_dir / "2026-01-01-gamma-adr.md"
    lock_target = document_lock_target(beta, root)
    lock_target.parent.mkdir(parents=True, exist_ok=True)

    def _run_rename() -> None:
        result = CliRunner().invoke(
            app,
            [
                "--target",
                str(root),
                "vault",
                "rename",
                "2026-01-01-alpha-adr",
                "--to",
                "2026-01-01-gamma-adr",
                "--no-check",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output

    _prove_serialized_by(lock_target, _run_rename)

    assert gamma.exists()
    assert not alpha.exists()
    beta_text = beta.read_text(encoding="utf-8")
    assert "[[2026-01-01-gamma-adr]]" in beta_text
    assert "[[2026-01-01-alpha-adr]]" not in beta_text


def test_no_deadlock_under_concurrent_rename_and_edit_load(tmp_path: Path) -> None:
    """Real concurrent rename-plus-edit load never deadlocks, either direction.

    ``execute_edit`` only ever acquires a per-document lock; the rename-class
    mutators acquire the domain lock first, then per-document locks for the
    mutated set second. Since ``execute_edit`` never requests the domain
    lock, no thread can hold one lock type while waiting on the other in a
    way that forms a cycle - argued when the design was proposed, stress-
    tested here empirically instead of only argued: one rename thread races
    concurrent edit threads targeting the renamed document, a referrer, and
    an unrelated document, all under a generous bounded timeout. A real
    deadlock would leave a thread alive past that bound; correct behaviour
    completes well within it regardless of which side wins the race.

    Drives the rename through ``_execute_rename`` directly rather than
    through ``CliRunner`` - ``CliRunner.invoke`` swaps ``sys.stdout``
    process-globally for its duration, which is not safe to run
    concurrently with other threads that are themselves writing to stdout
    (the edit threads' own logging); that is a test-harness limitation of
    running Click's IO-capturing runner from multiple threads at once, not
    a product concern, so it is sidestepped here rather than worked around.
    """
    from vaultspec_core.cli.edit_cmd import _execute_rename

    from ...core.commands import install_run
    from ...core.types import init_paths
    from ..edit_engine import EditResult, execute_edit

    root = tmp_path / "project"
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_ALPHA, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(_BETA, encoding="utf-8")
    _write(
        adr_dir / "2026-01-01-gamma-adr.md",
        "---\ntags:\n  - '#adr'\n  - '#concurrency'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\nrelated: []\n---\n\n# Gamma\n",
    )
    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    (root / ".vault" / "data").mkdir(parents=True, exist_ok=True)

    errors: list[BaseException] = []
    gamma_results: list[EditResult] = []
    results_guard = threading.Lock()

    def _record_error(exc: BaseException) -> None:
        with results_guard:
            errors.append(exc)

    def _run_rename() -> None:
        try:
            # _execute_rename reads the target from the workspace context,
            # which is thread-local (a contextvars.ContextVar, not process-
            # global) - it must be initialised on THIS thread, not borrowed
            # from the thread that set it up.
            init_paths(root)
            _execute_rename(
                ref="2026-01-01-alpha-adr",
                new_stem="2026-01-01-zeta-adr",
                expected_blob_hash=None,
                run_checks=False,
                dry_run=False,
                json_output=True,
            )
        except BaseException as exc:
            _record_error(exc)

    def _run_edit(ref: str, marker: str, *, track: bool = False) -> None:
        try:
            # run_checks=False mirrors every other concurrency test in this
            # module (the CLI side runs `--no-check`) - keeps this test
            # targeted at locking rather than the conformance checkers.
            result = execute_edit(
                root,
                ref=ref,
                new_body=f"\n# Doc\n\n{marker}\n",
                run_checks=False,
            )
            # Any EditResult - including a clean "failed" once alpha has
            # been renamed away - is an acceptable outcome; only an escaped
            # exception (a crash) or a hang (caught by the join timeout
            # below) would be a bug.
            if track:
                with results_guard:
                    gamma_results.append(result)
        except BaseException as exc:
            _record_error(exc)

    threads = [threading.Thread(target=_run_rename, name="renamer")]
    for i in range(4):
        threads.append(
            threading.Thread(
                target=_run_edit,
                args=("2026-01-01-alpha-adr", f"alpha edit {i}"),
                name=f"edit-alpha-{i}",
            )
        )
        threads.append(
            threading.Thread(
                target=_run_edit,
                args=("2026-01-01-beta-adr", f"beta edit {i}"),
                name=f"edit-beta-{i}",
            )
        )
        threads.append(
            threading.Thread(
                target=_run_edit,
                kwargs={
                    "ref": "2026-01-01-gamma-adr",
                    "marker": f"gamma edit {i}",
                    "track": True,
                },
                name=f"edit-gamma-{i}",
            )
        )

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20.0)
        assert not t.is_alive(), f"{t.name} did not complete - possible deadlock"

    assert not errors, f"unexpected errors under concurrent load: {errors!r}"

    # Self-consistent final state: never both the old and new name present.
    alpha = adr_dir / "2026-01-01-alpha-adr.md"
    zeta = adr_dir / "2026-01-01-zeta-adr.md"
    assert not (alpha.exists() and zeta.exists())
    assert alpha.exists() or zeta.exists()

    # The unrelated document was never BLOCKED by the domain-wide rename -
    # per-document granularity survives the fix: every gamma thread completed
    # within the bounded join above rather than waiting out the whole rename,
    # and each produced a typed result, never a hang or a crash.
    #
    # One outcome is tolerated rather than asserted away here: gamma is
    # outside the rename's locked (mutated) set - correctly, since the
    # cascade never writes it - but `RenameTransaction.snapshot()` still
    # READS every non-archive document, gamma included, for the rollback
    # journal, without taking gamma's advisory lock (there is nothing to
    # exclude a reader from; only writers race writers). On Windows this can
    # transiently collide with a concurrent gamma WRITE: `os.replace` can
    # deny access to a destination another handle has open for read at that
    # exact instant. This is real, but it is a property of
    # `atomic_write_bytes` versus a concurrent reader in general - orthogonal
    # to the blob-hash guard and the per-document locking this test exists to
    # prove, and already folds cleanly into a typed failed EditResult rather
    # than crashing (confirming the repro-A fix generalises beyond the one
    # cause it was written for). Any OTHER failure shape is still a bug.
    assert len(gamma_results) == 4
    _access_denied = "Access is denied"
    for result in gamma_results:
        if result.status == "updated":
            continue
        message = str((result.error or {}).get("message", ""))
        assert _access_denied in message, (
            result.status,
            result.blob_hash,
            result.error,
        )


def test_feature_rename_blocks_on_held_docs_lock(tmp_path: Path) -> None:
    """``rename_feature`` serializes on the docs sentinel.

    Builds a real two-document feature vault and drives the real
    ``rename_feature`` backend (not a stand-in): with the docs sentinel held it
    cannot proceed, and once released it completes with a consistent final
    state - the authored docs are renamed to the new feature, the old-feature
    files are gone, and the incoming ``related:`` link is re-pointed to the
    renamed stem. This pins the third docs-domain mutator the module docstring
    claims, alongside ``vault rename`` and the structure cascade.
    """
    from ..query import rename_feature

    root = tmp_path / "project"
    docs_dir = root / ".vault"
    research_dir = docs_dir / "research"
    adr_dir = docs_dir / "adr"
    research_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)

    research = research_dir / "2026-01-01-alpha-feature-research.md"
    adr = adr_dir / "2026-01-01-alpha-feature-adr.md"
    _write(
        research,
        "---\ntags:\n  - '#research'\n  - '#alpha-feature'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\nrelated: []\n---\n\n# Alpha\n",
    )
    _write(
        adr,
        "---\ntags:\n  - '#adr'\n  - '#alpha-feature'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\n"
        "related:\n  - '[[2026-01-01-alpha-feature-research]]'\n---\n\n# Alpha ADR\n",
    )
    # Materialise the lock-file parent so the advisory lock actually engages.
    (docs_dir / "data").mkdir(parents=True, exist_ok=True)

    renamed_research = research_dir / "2026-01-01-beta-feature-research.md"
    renamed_adr = adr_dir / "2026-01-01-beta-feature-adr.md"

    def _run_rename() -> None:
        result = rename_feature(root, "alpha-feature", "beta-feature")
        assert result["status"] == "updated"

    _prove_serialized_by(docs_lock_target(docs_dir), _run_rename)

    # The rename ran to completion after the lock was released.
    assert renamed_research.exists()
    assert renamed_adr.exists()
    assert not research.exists()
    assert not adr.exists()
    adr_text = renamed_adr.read_text(encoding="utf-8")
    assert "[[2026-01-01-beta-feature-research]]" in adr_text
    assert "[[2026-01-01-alpha-feature-research]]" not in adr_text


def test_rename_feature_blocks_while_a_renamed_document_is_locked_by_an_edit(
    tmp_path: Path,
) -> None:
    """``rename_feature`` also takes per-document locks for its mutated set.

    Extends the ``vault rename`` fix to the second real docs-domain mutator:
    ``_apply_rename_plan`` now passes ``document_lock_targets`` -
    ``plan.file_renames``' sources plus ``find_rewrite_targets``'s referrer
    set - into ``RenameTransaction``, so the SAME repro-B race (an in-flight
    edit's write resurrecting a document a rename already moved) is closed
    for a whole-feature rename, not just a single-document one. Proven the
    same way: with the ADR's own advisory lock held by another holder,
    ``rename_feature`` must block, and once released must complete correctly.
    """
    from ..edit_engine import document_lock_target
    from ..query import rename_feature

    root = tmp_path / "project"
    docs_dir = root / ".vault"
    research_dir = docs_dir / "research"
    adr_dir = docs_dir / "adr"
    research_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)

    research = research_dir / "2026-01-01-alpha-feature-research.md"
    adr = adr_dir / "2026-01-01-alpha-feature-adr.md"
    _write(
        research,
        "---\ntags:\n  - '#research'\n  - '#alpha-feature'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\nrelated: []\n---\n\n# Alpha\n",
    )
    _write(
        adr,
        "---\ntags:\n  - '#adr'\n  - '#alpha-feature'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\n"
        "related:\n  - '[[2026-01-01-alpha-feature-research]]'\n---\n\n# Alpha ADR\n",
    )
    (docs_dir / "data").mkdir(parents=True, exist_ok=True)

    renamed_adr = adr_dir / "2026-01-01-beta-feature-adr.md"
    lock_target = document_lock_target(adr, root)
    lock_target.parent.mkdir(parents=True, exist_ok=True)

    def _run_rename() -> None:
        result = rename_feature(root, "alpha-feature", "beta-feature")
        assert result["status"] == "updated"

    _prove_serialized_by(lock_target, _run_rename)

    # No resurrection: the old-feature path is gone, the new one exists.
    assert renamed_adr.exists()
    assert not adr.exists()
