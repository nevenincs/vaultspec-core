"""Tests for the tool description a model reads: docstrings trimmed, not emptied.

``tool_description`` drops what the model cannot act on - the ``Returns:`` and
``Raises:`` sections and the ``ctx`` argument no input schema carries - and
must keep every argument a caller can pass, rendered in the Markdown a model
reads rather than reST's layout. The unit tests pin the trimming on
a docstring shaped as ``inspect.getdoc`` leaves it; the server test reads the
registered tools themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import tool_description

from .conftest import vault_root

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]


def _documented(ctx: object, query: str, limit: int) -> None:
    """Answer a question.

    Args:
        ctx: The MCP request context (unused; logging routes through the
            module logger).
        query: The question, in plain language.
        limit: Hits to return, clamped to
            the ceiling.

    Returns:
        Nothing a model can see.
    """
    _ = (ctx, query, limit)


def _only_ctx(ctx: object) -> None:
    """Report the project.

    Args:
        ctx: The MCP request context.
    """
    _ = ctx


@pytest.mark.unit
def test_every_argument_after_ctx_survives() -> None:
    assert tool_description(_documented) == (
        "Answer a question.\n"
        "\n"
        "Args:\n"
        "query: The question, in plain language.\n"
        "limit: Hits to return, clamped to the ceiling."
    )


def _literal(path: str) -> None:
    """Read ``path`` and pass ``--json`` or ``--dry-run``.

    Args:
        path: A path, as ``stem`` or
            ``stem.md``; see ``find``.
    """
    _ = path


@pytest.mark.unit
def test_a_rest_literal_renders_as_a_markdown_literal() -> None:
    assert tool_description(_literal) == (
        "Read `path` and pass `--json` or `--dry-run`.\n"
        "\n"
        "Args:\n"
        "path: A path, as `stem` or `stem.md`; see `find`."
    )


@pytest.mark.unit
def test_an_args_block_holding_only_ctx_is_dropped() -> None:
    assert tool_description(_only_ctx) == "Report the project."


@pytest.mark.unit
async def test_the_search_tool_documents_its_parameters(vault_root: Path) -> None:
    tools = {tool.name: tool for tool in await create_server().list_tools()}

    search = tools["search"].description or ""
    assert "query: The question, in plain language." in search
    assert "limit: Hits to return." in search
    for tool in tools.values():
        description = tool.description or ""
        assert "ctx:" not in description, tool.name
        assert "request context" not in description, tool.name
