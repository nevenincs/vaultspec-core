"""Shared fixtures for the batch MCP document-tool tests.

Builds a real installed vault through the :class:`WorkspaceFactory` unified
fixture over a stdlib ``tempfile`` root (the repo ``tmp_path`` compat shim is
deliberately sidestepped), initialises the global path context, and exposes
a helper to unwrap a ``CallToolResult`` into its structured payload.  No
mocks, stubs, or skips: every test drives the real FastMCP server over the
in-memory session transport against the real filesystem.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.unit]


@pytest.fixture
def vault_root():
    """Yield an installed vault root with the global path context set.

    Built via :class:`WorkspaceFactory` over a stdlib ``tempfile`` root and
    torn down afterwards, so the create/edit cores resolve real templates,
    scan a real vault, and write real files.
    """
    reset_config()
    root = Path(tempfile.mkdtemp(prefix="vsc-mcp-doc-"))
    try:
        WorkspaceFactory(root).install()
        init_paths(root)
        yield root
    finally:
        reset_config()
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def data_of(result: Any) -> Any:
    """Unwrap a ``CallToolResult`` into its structured payload.

    Asserts the call did not surface a protocol error, then returns the
    structured content (unwrapping FastMCP's ``{"result": ...}`` envelope
    when present).

    Args:
        result: The ``CallToolResult`` from an in-memory tool call.

    Returns:
        The structured Python payload the tool returned.
    """
    error_texts = [c.text for c in result.content if hasattr(c, "text")]
    assert not result.isError, f"Tool returned error: {error_texts}"
    sc = result.structuredContent
    if isinstance(sc, dict) and list(sc.keys()) == ["result"]:
        return sc["result"]
    return sc
