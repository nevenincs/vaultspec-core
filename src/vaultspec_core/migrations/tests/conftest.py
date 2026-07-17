"""Shared fixtures for migration tests.

Mirrors the CLI suite's autouse workspace-context isolation: migration tests
that provision real workspaces bind the global workspace context via
``init_paths``, and without a save/restore boundary that context leaks into
whichever test collects next (the no-context collector tests are the first
casualties under full-gate ordering).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import vaultspec_core.core.types as _t


@pytest.fixture(autouse=True)
def _isolate_state():
    """Save and restore workspace context, target, config, and console."""
    from vaultspec_core.cli._target import reset as reset_target
    from vaultspec_core.config import reset_config
    from vaultspec_core.console import reset_console
    from vaultspec_core.core.types import _workspace_ctx

    try:
        current = _workspace_ctx.get()
        token = _workspace_ctx.set(current)
    except LookupError:
        _sentinel = Path(".")
        token = _workspace_ctx.set(
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

    _workspace_ctx.reset(token)
    reset_console()
    reset_target()
    reset_config()
