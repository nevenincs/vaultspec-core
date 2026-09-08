"""Repository-root pytest configuration.

Holds the one session-level behaviour that must apply to every invocation,
however a lane reaches pytest.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.testing.workspace_templates import WorkspaceTemplates

if TYPE_CHECKING:
    from collections.abc import Iterator


# --- machine-readable CI reports -------------------------------------------
#
# A test lane's result is human-readable text and nothing else, so CI can only
# learn "the process exited non-zero" and has to scrape scrollback for what
# actually failed. `VAULTSPEC_CI_REPORTS` names a directory to write a JUnit
# XML report into; when it is UNSET - every local run, and any CI job that does
# not opt in - nothing changes and no artifact is produced.
#
# The junitxml plugin reads `xmlpath` in its own `pytest_configure`. A conftest
# is registered after the builtin plugins and pytest calls hook implementations
# last-registered-first, so this conftest's configure runs BEFORE the plugin
# reads the option - which is what makes setting it here take effect.
#
# The filename distinguishes lanes: `VAULTSPEC_CI_REPORT_NAME` when the caller
# names one, otherwise a short digest of the invocation, so two lanes in one
# job do not overwrite each other's report. An explicit `--junitxml` on the
# command line always wins.
_CI_REPORTS_ENV = "VAULTSPEC_CI_REPORTS"
_CI_REPORT_NAME_ENV = "VAULTSPEC_CI_REPORT_NAME"


def _ci_report_path(args: tuple[str, ...] | list[str]) -> str | None:
    """Return the JUnit path this run should write, or ``None`` to write none.

    Args:
        args: The pytest command-line arguments for this run.

    Returns:
        The report path, or ``None`` when reporting is not enabled or the
        caller already named a report.
    """
    directory = os.environ.get(_CI_REPORTS_ENV, "").strip()
    if not directory:
        return None
    if any(arg == "--junitxml" or arg.startswith("--junitxml=") for arg in args):
        return None
    name = os.environ.get(_CI_REPORT_NAME_ENV, "").strip()
    if not name:
        digest = hashlib.sha256(" ".join(args).encode("utf-8")).hexdigest()[:8]
        name = f"pytest-{digest}"
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    return str(target / f"{name}.xml")


def _enable_ci_report(config: pytest.Config) -> None:
    """Point the junitxml plugin at this run's report, when one is asked for."""
    if getattr(config.option, "xmlpath", None):
        return
    path = _ci_report_path(list(config.invocation_params.args))
    if path is not None:
        config.option.xmlpath = path


# --- the durability boundary -----------------------------------------------
#
# `atomic_write_bytes` fsyncs every file it writes. That call buys durability
# across power loss and nothing else: the helper's ATOMICITY comes from the
# `O_EXCL` temporary and the rename, neither of which involves fsync. No test
# asserts the durability half - `core/tests/test_manifest_exclusive_atomicity.py`
# says so in its own docstring - so under pytest the suite pays for a guarantee
# it cannot observe.
#
# It pays a lot. One `install --provider all` issues 426 fsyncs, 61% of its
# runtime, and the fixtures reprovision such a workspace hundreds of times per
# run. Worse than the cost is its shape: fsync serialises at the DEVICE, so it
# does not shrink when workers are added, which is what kept this suite
# effectively unparallelisable.
#
# So the harness skips it, on the stated principle that it may skip work whose
# effect no test can observe and nothing else. Production is untouched: the call
# site stays exactly where it is, and an installed `vaultspec-core` fsyncs as it
# always has. The divergence is confined to this file, which no production code
# path can import, and `dev/guards/test_durability_boundary.py` fails if it ever
# stops being confined.
#
# The patch is on `os` itself rather than on the helper, because the helper is
# not the only writer in a run and a boundary that named one function would be a
# statement about that function rather than about the harness.
#
# Child processes are NOT covered - a test that shells out to a real CLI gets a
# real fsync, because the patch lives in this interpreter. That is a limit, not
# an oversight: those tests are few, and reaching into a subprocess to disable a
# durability call is exactly the kind of production-visible mechanism this
# boundary refuses.
_real_fsync = os.fsync


def _no_fsync(fd: int) -> None:
    """Stand in for :func:`os.fsync` while a test session is running."""


def pytest_configure(config: pytest.Config) -> None:
    """Apply the session-level configuration this repository's runs share."""
    _enable_ci_report(config)
    os.fsync = _no_fsync


def pytest_unconfigure() -> None:
    """Hand back the real durability guarantee when the session ends."""
    os.fsync = _real_fsync


def pytest_report_header() -> str:
    """Announce the boundary, so no one has to find it in a conftest.

    A run that silently differs from production is the failure mode this
    boundary is most likely to cause, so it names itself in every run's header
    rather than waiting to be discovered.
    """
    return "durability: os.fsync suppressed for this session (production unaffected)"


# --- a deadline for fixture setup: NOT IMPLEMENTED --------------------------
#
# `timeout_func_only = true` restricts pytest-timeout to the CALL phase, so
# fixture setup has no deadline at all - and setup is where this suite spends
# nearly all of its time. A wedged fixture still takes the lane down silently.
#
# That flag has to stay true: its budget is derived from the advisory lock's
# 120s wait so `AdvisoryLockTimeoutError` can fire first, and
# `dev/guards/test_automation_contracts.py` holds the relationship. Ten minutes
# is the right number for a body waiting on a lock and the wrong one for a
# fixture. So setup needs its OWN, shorter budget rather than the body's.
#
# Two mechanisms were tried and both broke pytest's fixture bookkeeping,
# tripping `assert not self._finalizers` in `FixtureDef.execute` across every
# guard with a finaliser: wrapping `pytest_fixture_setup` with a hookwrapper,
# and arming a `faulthandler` alarm from the plain `pytest_runtest_*` phase
# hooks. Whatever the interaction is, it is not understood well enough to ship,
# and a harness change that breaks 138 guards to catch a hypothetical hang is a
# bad trade.
#
# Left undone deliberately rather than half-done. The exposure is much smaller
# than it was - the slowest setup in a full run is now ~27s, against six minutes
# before the workspace templates landed - so this is a gap to close on its own
# terms, not an emergency. See issue #514.


@pytest.fixture(autouse=True)
def _durability_boundary(request: pytest.FixtureRequest) -> Iterator[None]:
    """Give a `durable`-marked test the real ``os.fsync`` back.

    The boundary is licensed by one property: no test can observe the
    suppression. Where that stops being true the licence stops with it, and a
    test that CAN observe it has to run against the real call rather than have
    its subject quietly changed.

    Exactly one cohort qualifies today. ``test_fix_writer_concurrency`` races a
    writer against a fix pass and asserts no committed edit is lost, so what it
    measures is the timing of the atomic-write path itself. Suppressing fsync
    tightens that loop enough to exhaust ``_WINDOWS_REPLACE_RETRY_BUDGET_SECONDS``:
    measured over 20 runs each, the test failed 4 times with fsync suppressed
    and 0 times with it restored.

    That is the boundary's own rule catching the boundary, which is what the
    rule is for. It is a narrow opt-out rather than a reason to abandon the
    suppression, because the property still holds everywhere else.
    """
    if request.node.get_closest_marker("durable") is None:
        yield
        return
    os.fsync = _real_fsync
    try:
        yield
    finally:
        os.fsync = _no_fsync


# --- provisioned-workspace reuse -------------------------------------------
#
# Several packages need "a real, fully installed workspace" per test, and each
# used to build one from scratch: `build_synthetic_vault` plus a real
# `install_run`, 245 files, hundreds of times a run. One fixture alone accounted
# for 59% of all fixture time.
#
# Every one of those trees was IDENTICAL at the moment the fixture yielded - the
# corpus generator is seeded and the install is a pure function of the bundled
# builtins - so the construction is what repeats, not the result. This builds
# each distinct tree once per session and hands out copies.
#
# Copying rather than sharing is the load-bearing half. Tests mutate their
# workspace, so a shared root would couple every test to every other; the
# isolation each test had before is exactly preserved, and only the work of
# reaching the starting state is amortised.
#
# The cache itself is `vaultspec_core.testing.workspace_templates`, importable
# by name from the three packages whose conftests annotate with it. Only the
# fixture lives here, which is where a fixture has to be to reach every lane.


@pytest.fixture(scope="session")
def workspace_templates(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceTemplates:
    """Session-wide cache of provisioned workspaces, one build per shape.

    Under xdist each worker holds its own cache, so the build cost is paid once
    per worker rather than once per test - twelve times instead of hundreds.
    """
    return WorkspaceTemplates(tmp_path_factory.mktemp("workspace-templates"))
