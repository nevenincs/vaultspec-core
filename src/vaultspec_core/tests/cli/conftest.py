"""Shared fixtures for the CLI test suite.

Provides the session-scoped ``runner``, the ``synthetic_project`` workspace
fixture backed by an on-the-fly synthetic vault corpus, and autouse isolation
that saves/restores the workspace context between tests.  Color output is
disabled globally via ``NO_COLOR=1``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import typer.rich_utils
from typer.testing import CliRunner, Result

import vaultspec_core.core.types as _t
from vaultspec_core.cli import app
from vaultspec_core.config.workspace import resolve_workspace
from vaultspec_core.core.types import init_paths
from vaultspec_core.testing import build_synthetic_vault

if TYPE_CHECKING:
    from collections.abc import Generator

    from vaultspec_core.testing.workspace_templates import (
        WorkspaceTemplates,
    )
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

# Disable Rich/Typer color output in tests.
os.environ["NO_COLOR"] = "1"
typer.rich_utils.COLOR_SYSTEM = None


def setup_rules_dir(root: Path) -> None:
    """Setup rules source directory in the given root."""
    (root / ".vaultspec" / "rules").mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def runner() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1"})


def _build_synthetic_project(dest: Path) -> None:
    """Populate *dest* with a synthetic corpus and a real install.

    The whole of what ``synthetic_project`` means, factored out so the session
    cache can call it once. Both halves are deterministic - the generator is
    seeded, and the install is a function of the bundled builtins and that
    corpus - which is what makes the result safe to copy rather than rebuild.
    """
    from vaultspec_core.core.commands import install_run

    dest.mkdir(parents=True)
    build_synthetic_vault(dest, n_docs=24, seed=42)
    install_run(path=dest, provider="all", upgrade=False, dry_run=False, force=True)


@pytest.fixture
def synthetic_project(tmp_path: Path, workspace_templates: WorkspaceTemplates) -> Path:
    """A fresh, fully-installed synthetic project for this test alone.

    ``tmp_path / "project"`` holds a synthetic ``.vault/`` corpus plus an
    installed ``.vaultspec/`` framework, and auto-cleans via ``tmp_path``.

    The tree is copied from a session-scoped template rather than rebuilt:
    every test that asked for this fixture used to run a full ``install_run``,
    which was 59% of all fixture time in the suite. The copy is private and
    writable, so mutation isolation is exactly what it was.

    The workspace context is initialised via ``init_paths`` so that unit tests
    calling internal functions (``collect_rules``, ``rules_sync``, etc.) have
    the paths they rely on.
    """
    dest = workspace_templates.clone(
        "synthetic-project", tmp_path / "project", _build_synthetic_project
    )

    layout = resolve_workspace(target_override=dest)
    init_paths(layout)

    return dest


def run_vaultspec(runner: CliRunner, *args: str, target: Path | None = None) -> Result:
    """Invoke the CLI with optional --target."""
    args_list = list(args)
    if target and "--target" not in args_list and "-t" not in args_list:
        args_list = [*args_list, "--target", str(target)]
    return runner.invoke(app, args_list)


def run_vault(runner: CliRunner, *args: str, target: Path | None = None) -> Result:
    """Invoke the CLI with ``vault`` prefix and optional --target."""
    args_list = list(args)
    if target and "--target" not in args_list and "-t" not in args_list:
        args_list = [*args_list, "--target", str(target)]
    if "vault" not in args_list:
        args_list.insert(0, "vault")
    return runner.invoke(app, args_list)


def run_spec(runner: CliRunner, *args: str, target: Path | None = None) -> Result:
    """Invoke the CLI with optional --target (spec commands)."""
    args_list = list(args)
    if target and "--target" not in args_list and "-t" not in args_list:
        args_list = [*args_list, "--target", str(target)]
    return runner.invoke(app, args_list)


@pytest.fixture
def factory(tmp_path: Path) -> WorkspaceFactory:
    """Return a :class:`WorkspaceFactory` for composing on-disk test states."""
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

    return WorkspaceFactory(tmp_path)


@pytest.fixture(autouse=True)
def isolate_state() -> Generator[None]:
    """Give each test a neutral workspace context, then restore the prior one.

    This prevents state leakage when one test's CLI invocation sets the
    workspace context and the next test inherits stale values pointing
    at the wrong tmp_path. Preserving an inherited context is not enough:
    a test in another package that initialises a workspace and never rolls
    it back (installing into a tmp_path, say) would otherwise hand its own
    project directory to every test here, and the tests that assert on the
    absence of a real workspace would fail on collection order alone.

    So the neutral placeholder is established unconditionally rather than
    only when no context exists. Tests needing a real workspace build one
    through ``synthetic_project`` or ``workspace_factory``, which run after
    this autouse fixture and set the context themselves.
    """
    from vaultspec_core.cli._target import reset as reset_target
    from vaultspec_core.config import reset_config
    from vaultspec_core.console import reset_console
    from vaultspec_core.core.types import workspace_ctx

    # The token restores the exact prior state on teardown - including
    # "unset" when no context existed before this test.
    _sentinel = Path(".")
    token = workspace_ctx.set(
        _t.WorkspaceContext(
            root_dir=_sentinel,
            target_dir=_sentinel,
            rules_src_dir=_sentinel,
            skills_src_dir=_sentinel,
            agents_src_dir=_sentinel,
            system_src_dir=_sentinel,
            templates_dir=_sentinel,
            hooks_dir=_sentinel,
        )
    )

    reset_console()
    reset_target()
    reset_config()

    yield

    # Restore original context (including "unset" if that was the prior state).
    workspace_ctx.reset(token)
    reset_console()
    reset_target()
    reset_config()
