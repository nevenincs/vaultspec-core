"""Repository-root pytest configuration.

Holds the one session-level behaviour that must apply to every invocation,
however a lane reaches pytest.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


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
# It lives here rather than in one package's conftest because three packages
# want it and a helper that only one can reach is how the duplication started.


class WorkspaceTemplates:
    """Builds each distinct workspace once, then clones it per test."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._templates: dict[str, Path] = {}

    def clone(self, key: str, dest: Path, build: Callable[[Path], None]) -> Path:
        """Return *dest*, populated as a copy of the template named *key*.

        Args:
            key: Identifies the tree. Two callers passing the same key must
                want byte-identical trees, because the second one gets a copy
                of whatever the first one built.
            dest: Directory to create. Must not already exist.
            build: Populates a fresh directory. Called at most once per key
                per session.

        Returns:
            *dest*, now holding a private copy of the template.
        """
        from vaultspec_core.tests.cli.workspace_factory import rebase_workspace_paths

        template = self._templates.get(key)
        if template is None:
            template = self._root / key
            build(template)
            self._templates[key] = template
        # `dirs_exist_ok` stays False: a caller handing us an existing
        # directory has confused this with a merge, and silently blending two
        # workspaces would be a very hard failure to read.
        shutil.copytree(template, dest, symlinks=True)
        # An installed workspace records where it lives, so a raw copy would
        # claim the template's files as its own.
        rebase_workspace_paths(template, dest)
        return dest


@pytest.fixture(scope="session")
def workspace_templates(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceTemplates:
    """Session-wide cache of provisioned workspaces, one build per shape.

    Under xdist each worker holds its own cache, so the build cost is paid once
    per worker rather than once per test - twelve times instead of hundreds.
    """
    return WorkspaceTemplates(tmp_path_factory.mktemp("workspace-templates"))
