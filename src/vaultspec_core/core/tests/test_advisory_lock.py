"""Tests for advisory_lock: file-level locking for scaffold operations."""

from __future__ import annotations

import errno
import json
import subprocess
import sys
import textwrap
import threading
import time
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.helpers import (
    _WINDOWS_LOCK_RETRY_INTERVAL_SECONDS,
    _is_windows_lock_contention,
    advisory_lock,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
class TestAdvisoryLock:
    def test_creates_lock_file(self, tmp_path: Path):
        root = tmp_path
        target = root / "test.json"
        target.write_text("{}")

        with advisory_lock(target):
            lock_file = target.with_suffix(".json.lock")
            assert lock_file.exists()

    def test_lock_on_nonexistent_file(self, tmp_path: Path):
        """Lock can be acquired even if the target file does not exist yet."""
        root = tmp_path
        target = root / "new.json"

        with advisory_lock(target):
            target.write_text('{"created": true}')

        assert target.read_text() == '{"created": true}'

    def test_lock_file_suffix_preserves_original(self, tmp_path: Path):
        """Lock file is .ext.lock, not replacing the original suffix."""
        root = tmp_path
        target = root / "config.yaml"
        target.write_text("key: value")

        with advisory_lock(target):
            lock_file = root / "config.yaml.lock"
            assert lock_file.exists()
            assert not (root / "config.lock").exists()


@pytest.mark.unit
class TestAdvisoryLockConcurrency:
    """Verify serialization under multi-process contention."""

    def test_lock_protects_concurrent_writes(self, tmp_path: Path):
        """Spawn a subprocess that holds the lock while we try to acquire.

        Both platforms use blocking lock acquisition, so the parent blocks
        until the child releases, ensuring serialized access.
        """
        root = tmp_path
        target = root / "data.json"
        target.write_text('{"value": 0}')

        child_script = textwrap.dedent(f"""\
            import time, json
            from pathlib import Path
            from vaultspec_core.core.helpers import advisory_lock

            target = Path(r"{target}")
            with advisory_lock(target):
                data = json.loads(target.read_text())
                data["child"] = True
                target.write_text(json.dumps(data))
                time.sleep(0.3)
        """)

        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            cwd=str(root),
        )

        time.sleep(0.1)

        # Parent blocks until child releases, then reads child's write.
        with advisory_lock(target):
            data = json.loads(target.read_text())
            data["parent"] = True
            target.write_text(json.dumps(data))

        proc.wait(timeout=10)
        assert proc.returncode == 0

        final = json.loads(target.read_text())
        assert final.get("parent") is True
        assert final.get("child") is True

    def test_high_contention_no_deadlock(self, tmp_path: Path):
        """Spawn many subprocesses that all compete for the same lock.

        Each process reads a counter, increments it, and writes it back
        under the advisory lock. If any process deadlocks, the 30-second
        timeout fires and the test fails.
        """
        root = tmp_path
        target = root / "counter.json"
        n_workers = 8
        target.write_text(json.dumps({"counter": 0}))

        worker_script = textwrap.dedent(f"""\
            import json
            from pathlib import Path
            from vaultspec_core.core.helpers import advisory_lock

            target = Path(r"{target}")
            for _ in range(10):
                with advisory_lock(target):
                    data = json.loads(target.read_text())
                    data["counter"] += 1
                    target.write_text(json.dumps(data))
        """)

        procs = [
            subprocess.Popen(
                [sys.executable, "-c", worker_script],
                cwd=str(root),
            )
            for _ in range(n_workers)
        ]

        for proc in procs:
            proc.wait(timeout=30)
            assert proc.returncode == 0, (
                f"Worker exited with {proc.returncode} (deadlock or error)"
            )

        final = json.loads(target.read_text())
        assert final["counter"] == n_workers * 10

    def test_multithreaded_no_deadlock(self, tmp_path: Path):
        """Many threads competing for the same lock must not deadlock.

        advisory_lock uses OS-level file locks which are per-process on
        most platforms. This test verifies the lock mechanism does not
        cause thread-level deadlocks or corruption when many threads
        call it concurrently within a single process.
        """
        root = tmp_path
        target = root / "threaded.json"
        n_threads = 20
        increments_per_thread = 50
        target.write_text(json.dumps({"counter": 0}))

        errors: list[str] = []
        barrier = threading.Barrier(n_threads)

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(increments_per_thread):
                    with advisory_lock(target):
                        data = json.loads(target.read_text())
                        data["counter"] += 1
                        target.write_text(json.dumps(data))
            except Exception as exc:
                errors.append(f"{threading.current_thread().name}: {exc}")

        threads = [
            threading.Thread(target=worker, name=f"worker-{i}")
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
            assert not t.is_alive(), f"Thread {t.name} still alive after 30s (deadlock)"

        assert not errors, f"Thread errors: {errors}"

        final = json.loads(target.read_text())
        expected = n_threads * increments_per_thread
        assert final["counter"] == expected

    def test_different_files_no_contention(self, tmp_path: Path):
        """Locks on different files must not interfere with each other.

        Verifies that two threads locking different files proceed
        independently without blocking or deadlocking.
        """
        root = tmp_path
        file_a = root / "a.json"
        file_b = root / "b.json"
        file_a.write_text(json.dumps({"owner": ""}))
        file_b.write_text(json.dumps({"owner": ""}))

        results: dict[str, bool] = {}
        barrier = threading.Barrier(2)

        def lock_file(path: Path, name: str):
            barrier.wait(timeout=5)
            with advisory_lock(path):
                data = json.loads(path.read_text())
                data["owner"] = name
                path.write_text(json.dumps(data))
                results[name] = True

        t1 = threading.Thread(target=lock_file, args=(file_a, "thread-a"))
        t2 = threading.Thread(target=lock_file, args=(file_b, "thread-b"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not t1.is_alive()
        assert not t2.is_alive()
        assert results == {"thread-a": True, "thread-b": True}
        assert json.loads(file_a.read_text())["owner"] == "thread-a"
        assert json.loads(file_b.read_text())["owner"] == "thread-b"

    def test_blocks_past_the_windows_retry_budget(self, tmp_path: Path):
        """A hold longer than msvcrt's retry budget must block, not raise.

        ``msvcrt.locking(fd, LK_LOCK, 1)`` is not a blocking acquire despite
        the name: it retries ten times at one-second intervals and then raises
        ``OSError(EDEADLOCK, "Resource deadlock avoided")``. Before this was
        wrapped in a retry, any operation holding a lock past that budget - a
        large repair, a slow or network volume, an antivirus scan mid-write -
        made a concurrent caller crash with an opaque error instead of waiting
        its turn, silently diverging from ``fcntl.flock(LOCK_EX)`` on Unix and
        from this module's own documented contract.

        The hold deliberately exceeds that budget, so a regression fails here
        rather than only under real-world contention.
        """
        target = tmp_path / "slow.json"
        target.write_text('{"value": 0}')
        hold_seconds = 12

        child_script = textwrap.dedent(f"""\
            import time
            from pathlib import Path
            from vaultspec_core.core.helpers import advisory_lock

            target = Path(r"{target}")
            with advisory_lock(target):
                print("held", flush=True)
                time.sleep({hold_seconds})
        """)

        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "held"

        started = time.monotonic()
        with advisory_lock(target):
            waited = time.monotonic() - started

        proc.wait(timeout=30)
        assert proc.returncode == 0
        # Having waited out the holder proves the acquire blocked rather than
        # giving up: the retry budget expires around nine seconds.
        assert waited > 10, f"acquired after only {waited:.1f}s; lock did not block"


class TestWindowsLockContentionClassification:
    """Which `msvcrt.locking` failures mean "wait" rather than "give up".

    `LK_LOCK` reports a LOCKING VIOLATION - someone else holds the range -
    through two different errnos, and Microsoft documents both:

      EDEADLK    the range could not be locked after its ten internal attempts
      EACCES     locking violation (the region is already locked)

    Only EDEADLOCK used to be retried, so contention that arrived as EACCES
    escaped as `PermissionError(13, 'Permission denied')` and was
    indistinguishable from a filesystem permission fault. That is what made the
    Windows concurrency suite intermittently red (issue #321).

    Classified by a pure predicate so this is provable on every platform: the
    acquire loop needs a real Windows descriptor, the decision does not.
    """

    def test_deadlock_is_contention(self) -> None:
        """The documented "could not lock after ten attempts" outcome waits."""
        assert _is_windows_lock_contention(OSError(errno.EDEADLK, "deadlock"))

    def test_access_denied_is_contention_not_a_permission_fault(self) -> None:
        """EACCES from `_locking` means the region is held, not unreachable.

        This is the regression. The exception carries errno 13 and NO
        `winerror`, because it comes from the CRT rather than the Win32 error
        layer - which is exactly why it reads like a permission problem and
        why retrying it is correct rather than papering over a fault.
        """
        exc = PermissionError(errno.EACCES, "Permission denied")

        assert getattr(exc, "winerror", None) is None
        assert _is_windows_lock_contention(exc)

    @pytest.mark.parametrize(
        "code",
        [errno.EBADF, errno.EINVAL, errno.ENOSPC],
    )
    def test_a_genuine_failure_still_propagates(self, code: int) -> None:
        """A bad descriptor or invalid argument must never spin forever."""
        assert not _is_windows_lock_contention(OSError(code, "genuine failure"))

    def test_the_retry_interval_is_short_but_not_a_hot_spin(self) -> None:
        """EACCES can return instantly, so the loop must pause between tries.

        Zero would burn a core while another writer holds the lock; a long
        wait would make every contended acquire feel stalled.
        """
        assert 0 < _WINDOWS_LOCK_RETRY_INTERVAL_SECONDS <= 0.5
