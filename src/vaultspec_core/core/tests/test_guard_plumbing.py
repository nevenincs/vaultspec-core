"""Regression tests for ``--dev`` plumbing through ``install_run``.

The dev-repo guard fires at multiple call sites: once at the top of
:func:`install_run` and again inside :func:`sync_provider`, which the
install/upgrade paths invoke as a sub-step.  When ``install_run`` does
not forward ``dev`` to its nested ``sync_provider`` call, the inner
guard rejects the write even though the user passed ``--dev`` --
producing a confusing "Refusing to modify ... Hint: Pass --dev" error
*after* the install has already partially run.

These tests pin the contract that ``dev=True`` reaches every guarded
sub-call inside ``install_run``.
"""

from __future__ import annotations

from typing import cast

import pytest

from vaultspec_core.core.guards import (
    DevRepoProtectionError,
    _cached_is_dev_repo,
    is_dev_repo,
)
from vaultspec_core.core.types import WorkspaceContext, _workspace_ctx

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the LRU cache between tests so per-tmp_path repos are re-detected."""
    _cached_is_dev_repo.cache_clear()
    yield
    _cached_is_dev_repo.cache_clear()


@pytest.fixture(autouse=True)
def _reset_workspace_ctx():
    """Reset the global :class:`WorkspaceContext` after each test.

    ``install_run`` calls ``init_paths`` internally, which sets a
    process-global :class:`~contextvars.ContextVar`. Without an
    explicit reset, the context leaks into every subsequent test in
    the unit suite and breaks tests that assert "no context exists"
    (e.g. ``test_collectors.py::TestConfigState::test_missing_no_context``).

    Use the ``ContextVar.set + reset`` token mechanism: set a sentinel
    value at fixture entry to obtain a token whose later ``reset``
    restores the var to the state it had BEFORE that ``set`` call.
    This works regardless of whether the var was previously set
    (``reset`` puts back the prior value) or unset (``reset`` puts it
    back into the unset state). The test body is free to overwrite
    the var; we still hold the token from our entry call.

    The sentinel is typed as :class:`WorkspaceContext` via :func:`cast`
    to satisfy the strict ContextVar generic; the value is never
    observed because the test body overwrites it before any read.
    """
    sentinel = cast("WorkspaceContext", object())
    token = _workspace_ctx.set(sentinel)
    try:
        yield
    finally:
        _workspace_ctx.reset(token)


def _materialise_source_layout(root) -> None:
    """Make *root* satisfy :func:`is_dev_repo`."""
    pyproject = root / "pyproject.toml"
    pyproject.write_text('[project]\nname = "vaultspec-core"\n', encoding="utf-8")
    pkg = root / "src" / "vaultspec_core"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")


def test_install_upgrade_forwards_dev_to_sync_provider(tmp_path) -> None:
    """``install_run(upgrade=True, dev=True)`` on a dev repo must not raise the guard.

    Reproduces the regression where the upgrade path called
    ``sync_provider`` without forwarding ``dev``, causing the inner
    guard to reject the write after the outer guard had already
    authorised it.
    """
    from vaultspec_core.core.commands import install_run

    install_run(path=tmp_path, provider="all", force=True)

    _materialise_source_layout(tmp_path)
    assert is_dev_repo(tmp_path) is True
    _cached_is_dev_repo.cache_clear()

    # Must NOT raise DevRepoProtectionError.  Any other exception type
    # here would indicate an unrelated failure and should bubble up.
    install_run(path=tmp_path, provider="all", upgrade=True, dev=True)


def test_install_upgrade_without_dev_on_dev_repo_still_refuses(tmp_path) -> None:
    """The guard must still fire when ``dev=False`` on a dev repo.

    Counter-test: confirms the fix didn't accidentally weaken the guard
    -- forwarding ``dev`` only matters when the user explicitly opts in.
    """
    from vaultspec_core.core.commands import install_run

    install_run(path=tmp_path, provider="all", force=True)

    _materialise_source_layout(tmp_path)
    _cached_is_dev_repo.cache_clear()

    with pytest.raises(DevRepoProtectionError, match="source repository"):
        install_run(path=tmp_path, provider="all", upgrade=True)
