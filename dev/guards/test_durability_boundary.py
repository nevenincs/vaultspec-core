"""The fsync boundary is the harness's, and it stays there.

The root ``conftest.py`` replaces :func:`os.fsync` with a no-op for the length
of a test session. That is a deliberate, recorded divergence between the test
harness and production: ``atomic_write_bytes`` fsyncs every file it writes,
which buys durability across power loss, and no test asserts that property.
Removing it takes 61% off an install and - more to the point - takes the write
path off a device-serialised call that never scaled with workers.

A divergence like that is only defensible while it is CONFINED. Two things can
erode it quietly, and this guard exists for both.

The first is production learning about the harness. The moment a shipped module
branches on ``PYTEST_CURRENT_TEST``, an installed ``vaultspec-core`` starts
behaving one way for a user and another way under test, and the suite stops
proving anything about the product. That is a different and much worse failure
than a slow lane, so the check is on the *shipped* trees only: ``dev/`` and
``docs/`` are development instruments, and their guards legitimately ask
whether they are running under pytest.

The second is a second fsync appearing somewhere the harness patch does not
reach - a direct ``os.fsync`` in a module the boundary was never reasoned
about, or a helper that opens its own descriptor and syncs it. One call site is
what makes the boundary a single, checkable fact; two make it a habit nobody
has audited.

Neither check is a style rule. Both encode the two ways the recorded decision
can be true on paper and false in the tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.repo, pytest.mark.precommit]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The tree that ships. `dev` and `docs` are development instruments, excluded
#: on purpose: a guard that asks whether it is running under pytest is doing
#: its job, while a shipped module that asks is the defect.
SHIPPED_ROOT = PROJECT_ROOT / "src"

#: The one place the durability call is allowed to live, relative to the root.
_SANCTIONED_FSYNC = Path("src/vaultspec_core/core/helpers.py")

#: The harness file that owns the boundary.
_BOUNDARY_OWNER = Path("conftest.py")

#: Names that mean "am I running under a test right now?". A shipped module
#: that reads any of them has learned about the harness.
_HARNESS_TELLS = (
    "PYTEST_CURRENT_TEST",
    "PYTEST_VERSION",
    "PYTEST_XDIST_WORKER",
)

#: The one violation that predates this guard, held here rather than hidden by
#: a weaker assertion. `_resolve_framework_root` returns early under pytest, so
#: the CWD/target split it implements is unreachable in the suite and ships
#: untested. Removing the branch is a resolution-semantics decision, not a test
#: fix, and is tracked as issue #515. The entry is deliberately a single exact
#: path: a new violation anywhere else still fails, and deleting this line is
#: what closing #515 looks like.
_KNOWN_HARNESS_AWARE = frozenset({"src/vaultspec_core/cli/_target.py"})


def _shipped_python_files() -> list[Path]:
    """Return every committed Python file in the tree that ships."""
    found = sorted(
        path for path in SHIPPED_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )
    # Same reason as every other derived corpus in dev/guards: nothing to scan
    # reads exactly like nothing to report.
    assert found, f"no Python sources found under {SHIPPED_ROOT}"
    return found


def _fsync_call_sites(path: Path) -> list[int]:
    """Return the line numbers at which *path* calls ``os.fsync``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "fsync"
    ]


class TestProductionDoesNotKnowAboutTheHarness:
    """No shipped module may branch on being under test."""

    def test_no_shipped_module_reads_a_pytest_environment_variable(self) -> None:
        offenders: list[str] = []
        for path in _shipped_python_files():
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            # A cohabiting test may read its own harness; the subject is the
            # library. The known exception is named, not pattern-matched.
            if "/tests/" in relative or relative in _KNOWN_HARNESS_AWARE:
                continue
            text = path.read_text(encoding="utf-8")
            for tell in _HARNESS_TELLS:
                if tell in text:
                    offenders.append(f"{relative} reads {tell}")

        assert not offenders, (
            "Shipped code must not detect the test harness. The durability "
            "boundary in conftest.py is only defensible while production is "
            "unaware of it; a module that branches on being under test makes "
            "the suite prove something the user never runs.\n  "
            + "\n  ".join(offenders)
        )

    def test_the_known_exception_is_still_a_real_one(self) -> None:
        """An allowlist that outlives its violation is worse than no allowlist.

        Once #515 is fixed the entry stops describing anything, and a stale
        exemption silently widens the guard. Failing here is the reminder to
        delete the line.
        """
        for relative in sorted(_KNOWN_HARNESS_AWARE):
            path = PROJECT_ROOT / relative
            assert path.is_file(), (
                f"{relative} is exempted from the harness-awareness check but "
                "no longer exists. Remove it from _KNOWN_HARNESS_AWARE."
            )
            text = path.read_text(encoding="utf-8")
            assert any(tell in text for tell in _HARNESS_TELLS), (
                f"{relative} no longer detects the test harness, so its "
                "exemption is stale. Remove it from _KNOWN_HARNESS_AWARE and "
                "close the tracking issue."
            )

    def test_no_shipped_module_imports_pytest(self) -> None:
        offenders: list[str] = []
        for path in _shipped_python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imports_pytest = (
                    isinstance(node, ast.Import)
                    and any(alias.name == "pytest" for alias in node.names)
                ) or (isinstance(node, ast.ImportFrom) and node.module == "pytest")
                if imports_pytest:
                    offenders.append(path.relative_to(PROJECT_ROOT).as_posix())
                    break

        # `tests` packages cohabit with the source they exercise, so they live
        # under `src` and import pytest legitimately. The subject here is the
        # library, not its tests.
        offenders = [name for name in offenders if "/tests/" not in name]
        assert not offenders, (
            "Shipped library modules must not import pytest.\n  "
            + "\n  ".join(offenders)
        )


class TestTheDurabilityCallHasOneHome:
    """`os.fsync` stays where the boundary was reasoned about."""

    def test_exactly_one_shipped_fsync_call_site(self) -> None:
        sites = {
            path.relative_to(PROJECT_ROOT).as_posix(): lines
            for path in _shipped_python_files()
            if (lines := _fsync_call_sites(path))
        }
        # A tests package may exercise fsync behaviour directly; the boundary
        # is about the library's own write path.
        sites = {name: lines for name, lines in sites.items() if "/tests/" not in name}

        expected = _SANCTIONED_FSYNC.as_posix()
        assert set(sites) == {expected}, (
            "The durability call must have exactly one home. The harness "
            "suppresses os.fsync process-wide, so a second call site is a "
            "write path whose durability nobody has reasoned about - it is "
            "silently unsynced under test and synced in production.\n"
            f"  expected: {expected}\n"
            f"  found:    {sorted(sites) or 'none'}"
        )
        assert len(sites[expected]) == 1, (
            f"Expected a single fsync call in {expected}, "
            f"found {len(sites[expected])} at lines {sites[expected]}."
        )


class TestTheBoundaryIsDeclaredWhereItIsOwned:
    """The suppression lives in the root conftest and announces itself."""

    def test_the_root_conftest_restores_fsync_and_reports_itself(self) -> None:
        conftest = (PROJECT_ROOT / _BOUNDARY_OWNER).read_text(encoding="utf-8")

        assert "os.fsync = _no_fsync" in conftest, (
            "The durability boundary is not established in conftest.py. If it "
            "has moved, this guard must move with it."
        )
        assert "os.fsync = _real_fsync" in conftest, (
            "conftest.py suppresses os.fsync without restoring it. A session "
            "that leaves the process without a durability call poisons "
            "anything running after pytest in the same interpreter."
        )
        assert "pytest_report_header" in conftest, (
            "The boundary must name itself in the run header. A harness that "
            "differs from production silently is the failure mode this "
            "decision is most likely to cause."
        )
