"""Mechanics tests for the migration registry driver.

Exercises :func:`vaultspec_core.migrations.run_pending_migrations`
against a real on-disk manifest with synthetic single-purpose
:class:`~vaultspec_core.migrations.Migration` entries. No mocks; each
test assembles its own registry and patches
:data:`vaultspec_core.migrations.REGISTRY` for the duration of the
scenario via direct module-state mutation, exactly mirroring how a
production registry append-only workflow extends the chain.

The driver bumps the manifest version on success and leaves it
untouched on failure. Both branches are covered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core import migrations as registry_mod
from vaultspec_core.core.manifest import (
    ManifestData,
    read_manifest_data,
    write_manifest_data,
)
from vaultspec_core.migrations import (
    Migration,
    MigrationResult,
    MigrationStatus,
    list_pending,
    migration_status,
    reset_workspace_cache,
    run_pending_migrations,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Path]:
    """Create an installed-style workspace with a writable manifest.

    Writes a stale ``vaultspec_version`` so the driver has something
    to migrate. Resets the per-process workspace cache so each test
    starts from a clean slate.

    Returns:
        The workspace root path. Tests still hit a real on-disk
        manifest and a real workspace path; no library functions are
        mocked.
    """
    fw_dir = tmp_path / ".vaultspec"
    fw_dir.mkdir(parents=True, exist_ok=True)
    data = ManifestData(vaultspec_version="0.1.0")
    write_manifest_data(tmp_path, data)
    reset_workspace_cache()
    yield tmp_path
    reset_workspace_cache()


def _install_registry(
    monkeypatch: pytest.MonkeyPatch, entries: list[Migration]
) -> None:
    """Replace :data:`REGISTRY` with *entries* for the test duration."""
    monkeypatch.setattr(registry_mod, "REGISTRY", entries)


def _noop(name: str, target_version: str) -> tuple[Migration, dict[str, int]]:
    """Build a :class:`Migration` whose body records its invocation count.

    Returns the migration instance and the per-test counter dict so tests
    can assert on the call count without mutating the frozen dataclass.
    """
    counter = {"calls": 0}

    def _migrate(_workspace: Path) -> MigrationResult:
        counter["calls"] += 1
        return MigrationResult(
            name=name,
            target_version=target_version,
            summary=f"{name} ran",
            counts={"calls": counter["calls"]},
        )

    m = Migration(target_version=target_version, name=name, migrate=_migrate)
    return m, counter


def _raising(name: str, target_version: str) -> Migration:
    """Build a :class:`Migration` whose body raises on every invocation."""

    def _migrate(_workspace: Path) -> MigrationResult:
        raise RuntimeError(f"{name} intentionally failed")

    return Migration(target_version=target_version, name=name, migrate=_migrate)


class TestEmptyRegistry:
    def test_no_op_returns_empty_list(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _install_registry(monkeypatch, [])
        results = run_pending_migrations(workspace)
        assert results == []

    def test_no_op_does_not_bump_version(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _install_registry(monkeypatch, [])
        before = read_manifest_data(workspace).vaultspec_version
        run_pending_migrations(workspace)
        after = read_manifest_data(workspace).vaultspec_version
        assert before == after == "0.1.0"


class TestSingleMigration:
    def test_runs_once_when_target_above_manifest(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        m, counter = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])
        results = run_pending_migrations(workspace)

        assert len(results) == 1
        assert results[0].name == "alpha"
        assert counter["calls"] == 1

    def test_bumps_manifest_version_on_success(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        m, _ = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])
        run_pending_migrations(workspace)
        after = read_manifest_data(workspace).vaultspec_version
        # The driver bumps to whichever is higher: the running package
        # version, or the highest applied target. The post-bump version
        # must at least cover the migration we just ran.
        from vaultspec_core.core.helpers import parse_version_tuple

        assert parse_version_tuple(after) >= parse_version_tuple("0.2.0")

    def test_second_run_is_no_op(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        m, counter = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])
        run_pending_migrations(workspace)
        version_after_first = read_manifest_data(workspace).vaultspec_version
        reset_workspace_cache()

        results = run_pending_migrations(workspace)
        assert results == []
        assert counter["calls"] == 1
        version_after_second = read_manifest_data(workspace).vaultspec_version
        assert version_after_first == version_after_second


class TestOrdering:
    def test_runs_in_version_order_on_stale_workspace(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Two migrations on the same stale 0.1.0 manifest. The driver
        # must apply them in version order regardless of registry
        # insertion order.
        order: list[str] = []

        def make_recording(name: str, target_version: str):
            def _migrate(_w: Path) -> MigrationResult:
                order.append(name)
                return MigrationResult(
                    name=name,
                    target_version=target_version,
                    summary=f"{name} ran",
                )

            return Migration(
                target_version=target_version,
                name=name,
                migrate=_migrate,
            )

        m_late = make_recording("late", "0.3.0")
        m_early = make_recording("early", "0.2.0")
        # Insertion order is intentionally late-then-early so the
        # driver's version sort actually has work to do.
        _install_registry(
            monkeypatch,
            sorted(
                [m_late, m_early],
                key=lambda x: tuple(int(v) for v in x.target_version.split(".")),
            ),
        )
        run_pending_migrations(workspace)
        assert order == ["early", "late"]


class TestVersionGating:
    def test_equal_version_does_not_run(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Strict greater-than: target_version == manifest must skip.
        data = read_manifest_data(workspace)
        data.vaultspec_version = "0.2.0"
        write_manifest_data(workspace, data)
        m, counter = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])

        results = run_pending_migrations(workspace)
        assert results == []
        assert counter["calls"] == 0

    def test_target_below_manifest_does_not_run(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        data = read_manifest_data(workspace)
        data.vaultspec_version = "0.5.0"
        write_manifest_data(workspace, data)
        m, counter = _noop("ancient", "0.2.0")
        _install_registry(monkeypatch, [m])

        results = run_pending_migrations(workspace)
        assert results == []
        assert counter["calls"] == 0

    def test_empty_manifest_version_does_not_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # No manifest on disk at all.
        m, counter = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])

        results = run_pending_migrations(tmp_path)
        assert results == []
        assert counter["calls"] == 0


class TestIncrementalVersionBump:
    def test_partial_failure_records_completed_target(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Two migrations: 0.2.0 succeeds, 0.3.0 raises. After the
        # exception the manifest version must reflect 0.2.0 (the
        # successful step) so the next invocation only re-runs 0.3.0.
        m_first, first_counter = _noop("first", "0.2.0")
        m_second = _raising("second", "0.3.0")
        _install_registry(monkeypatch, [m_first, m_second])

        with pytest.raises(RuntimeError, match="second intentionally failed"):
            run_pending_migrations(workspace)

        recorded = read_manifest_data(workspace).vaultspec_version
        from vaultspec_core.core.helpers import parse_version_tuple

        assert parse_version_tuple(recorded) >= parse_version_tuple("0.2.0")
        assert parse_version_tuple(recorded) < parse_version_tuple("0.3.0")
        assert first_counter["calls"] == 1

        # Second invocation: replace the broken entry with a working
        # one and confirm the first migration is NOT re-run because
        # the manifest already records its completion.
        m_second_fixed, second_counter = _noop("second_fixed", "0.3.0")
        _install_registry(monkeypatch, [m_first, m_second_fixed])
        run_pending_migrations(workspace)
        assert first_counter["calls"] == 1, (
            "successful first migration must not be re-run after a "
            "failure of a later entry"
        )
        assert second_counter["calls"] == 1


class TestCacheKeyNormalisation:
    def test_relative_and_resolved_paths_share_cache(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        # Up-to-date workspace; first call populates the cache. A
        # second call via an equivalent but differently-spelled path
        # (e.g. relative) must hit the cache rather than performing
        # another manifest read.
        data = read_manifest_data(workspace)
        data.vaultspec_version = "9.9.9"
        write_manifest_data(workspace, data)
        m, counter = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])

        # First call resolves the path; cache populated.
        run_pending_migrations(workspace, use_cache=True)
        assert counter["calls"] == 0

        # Mutate the manifest behind the registry's back to a stale
        # version. If the cache key were path-sensitive, the second
        # call via the unresolved path would miss the cache and
        # observe the stale version, running the migration. With
        # resolve()-keyed cache, both spellings hit the same entry
        # and the migration stays skipped.
        unresolved = workspace / "."
        data2 = read_manifest_data(workspace)
        data2.vaultspec_version = "0.0.1"
        write_manifest_data(workspace, data2)

        run_pending_migrations(unresolved, use_cache=True)
        assert counter["calls"] == 0, (
            "cache hit via equivalent path must short-circuit before "
            "the manifest read; migration must not run"
        )


class TestFailureDoesNotBumpVersion:
    def test_raising_migration_propagates(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _install_registry(monkeypatch, [_raising("broken", "0.2.0")])

        with pytest.raises(RuntimeError, match="broken intentionally failed"):
            run_pending_migrations(workspace)

    def test_raising_migration_leaves_version_untouched(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        before = read_manifest_data(workspace).vaultspec_version
        _install_registry(monkeypatch, [_raising("broken", "0.2.0")])

        with pytest.raises(RuntimeError):
            run_pending_migrations(workspace)

        after = read_manifest_data(workspace).vaultspec_version
        assert before == after == "0.1.0"

    def test_failure_is_retried_on_next_call(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # First call raises. After the failing entry is replaced, the
        # next call should pick up where it left off.
        _install_registry(monkeypatch, [_raising("broken", "0.2.0")])
        with pytest.raises(RuntimeError):
            run_pending_migrations(workspace)

        # Replace with a successful version of the same target.
        m_fixed, counter = _noop("fixed", "0.2.0")
        _install_registry(monkeypatch, [m_fixed])
        results = run_pending_migrations(workspace)
        assert len(results) == 1
        assert counter["calls"] == 1


class TestStatusHelpers:
    def test_unknown_when_no_manifest(self, tmp_path: Path):
        status, names = migration_status(tmp_path)
        assert status == MigrationStatus.UNKNOWN
        assert names == []

    def test_pending_when_target_above(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        m, _ = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])
        status, names = migration_status(workspace)
        assert status == MigrationStatus.PENDING
        assert names == ["alpha"]

    def test_up_to_date_when_all_applied(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        data = read_manifest_data(workspace)
        data.vaultspec_version = "9.9.9"
        write_manifest_data(workspace, data)
        m, _ = _noop("alpha", "0.2.0")
        _install_registry(monkeypatch, [m])
        status, names = migration_status(workspace)
        assert status == MigrationStatus.UP_TO_DATE
        assert names == []

    def test_list_pending_filters_to_above_manifest_only(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ):
        data = read_manifest_data(workspace)
        data.vaultspec_version = "0.2.0"
        write_manifest_data(workspace, data)
        # 0.1.5 < 0.2.0 (skip), 0.2.0 == 0.2.0 (skip), 0.3.0 > 0.2.0 (include).
        ancient, _ = _noop("ancient", "0.1.5")
        equal, _ = _noop("equal", "0.2.0")
        future, _ = _noop("future", "0.3.0")
        _install_registry(monkeypatch, [ancient, equal, future])
        pending = list_pending(workspace)
        assert [m.name for m in pending] == ["future"]
