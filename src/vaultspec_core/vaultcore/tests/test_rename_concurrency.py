"""Concurrency-safety tests for the docs-domain advisory lock.

The rename-convergence work commits every docs-domain mutator - ``vault rename``
(``_execute_rename``), ``rename_feature``, and the structure-rename cascade
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
    from collections.abc import Callable
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
def _reset_cfg():
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
    """``vault rename`` (``_execute_rename``) serializes on the docs sentinel.

    With the docs sentinel held, a real document rename cannot proceed; once
    released it completes and the final state is consistent: the file is moved,
    the old path is gone, and the incoming link is re-pointed (no lost update).
    """
    from ...cli.edit_cmd import _execute_rename
    from ...core.commands import install_run
    from ...core.types import init_paths

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
        # ContextVars do not propagate to a fresh thread; establish this
        # thread's workspace context before driving the real rename verb.
        init_paths(root)
        _execute_rename(
            ref="2026-01-01-alpha-adr",
            new_stem="2026-01-01-gamma-adr",
            expected_blob_hash=None,
            run_checks=False,
            dry_run=False,
            json_output=True,
        )

    _prove_serialized_by(docs_lock_target(docs_dir), _run_rename)

    # The rename ran to completion after the lock was released.
    assert gamma.exists()
    assert not alpha.exists()
    beta_text = beta.read_text(encoding="utf-8")
    assert "[[2026-01-01-gamma-adr]]" in beta_text
    assert "[[2026-01-01-alpha-adr]]" not in beta_text
