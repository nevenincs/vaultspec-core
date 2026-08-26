"""Tests for the ``find`` tool's query surface against a real MCPServer.

These pin what ``find`` returns for each query shape: the no-argument feature
roll-up, the enriched ``json`` roll-up, filtering by ``feature`` and by
``type``, the exec exclude-by-default rule, ``body`` inclusion, and the
``limit`` cap.  Documents are written to disk as raw markdown rather than
scaffolded through the ``create`` tool, so the vault scanner behind ``find``
is exercised directly; the complementary ``test_find_tool`` module pins the
global type-ordered semantics of ``limit`` over ``create``-scaffolded
documents.  No mocks, stubs, or skips: the real server runs over the
in-memory client transport against a real installed vault.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from mcp import Client

from vaultspec_core.mcp_server.app import create_server

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _write_doc(
    vault_root: Path,
    doc_type: str,
    feature: str,
    date: str,
    heading: str = "",
    body: str = "",
) -> Path:
    """Write a minimal raw vault document and return its path.

    Args:
        vault_root: The installed vault root.
        doc_type: The ``.vault/`` subfolder and directory tag.
        feature: The feature tag.
        date: The frontmatter ``date`` stamp.
        heading: An optional level-one heading.
        body: Optional body prose appended after the heading.

    Returns:
        The path the document was written to.
    """
    text = (
        "---\n"
        f"tags:\n  - '#{doc_type}'\n  - '#{feature}'\n"
        f"date: '{date}'\n"
        "related: []\n"
        "---\n"
    )
    if heading:
        text += f"{heading}\n"
    text += body
    directory = vault_root / ".vault" / doc_type
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{date}-{feature}-{doc_type}.md"
    path.write_text(text, encoding="utf-8")
    return path


async def test_find_lists_features_when_no_args(vault_root: Path) -> None:
    """A bare ``find`` rolls every feature up with a document count and weight."""
    _write_doc(vault_root, "adr", "feat-a", "2026-03-06", "# ADR A")
    _write_doc(vault_root, "plan", "feat-a", "2026-03-06", "# Plan A")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {})
        features = data_of(result)
        assert isinstance(features, list)
        # The no-args ``find`` payload is documented as a list of feature
        # summary dicts (name/doc_count/weight); cast narrows away the
        # Unknown element type isinstance leaves on an ``Any``-typed value.
        features = cast("list[dict[str, Any]]", features)
        assert len(features) >= 1
        feat_a = next((f for f in features if f["name"] == "feat-a"), None)
        assert feat_a is not None
        assert feat_a["doc_count"] >= 2
        assert "weight" in feat_a


async def test_find_json_returns_enriched_metadata(vault_root: Path) -> None:
    """``json`` mode carries the lifecycle status and the per-feature type set."""
    _write_doc(vault_root, "adr", "rich-feat", "2026-03-06", "# ADR")
    _write_doc(vault_root, "plan", "rich-feat", "2026-03-06", "# Plan")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"json": True})
        features = data_of(result)
        feat = next((f for f in features if f["name"] == "rich-feat"), None)
        assert feat is not None
        assert feat["status"] == "Planned"
        assert "adr" in feat["types"]
        assert "plan" in feat["types"]


async def test_find_by_feature(vault_root: Path) -> None:
    """A ``feature`` filter returns only that feature's documents."""
    _write_doc(vault_root, "adr", "my-feat", "2026-03-06", "# ADR")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"feature": "my-feat"})
        docs = data_of(result)
        assert len(docs) >= 1
        assert all(d["feature"] == "my-feat" for d in docs)


async def test_find_by_type(vault_root: Path) -> None:
    """A ``type`` filter returns only documents of that type."""
    _write_doc(vault_root, "adr", "typed-feat", "2026-03-06")
    _write_doc(vault_root, "plan", "typed-feat", "2026-03-06")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"type": ["plan"]})
        docs = data_of(result)
        assert all(d["type"] == "plan" for d in docs)


async def test_find_excludes_exec_by_default(vault_root: Path) -> None:
    """Execution records stay out of an unfiltered feature search."""
    _write_doc(vault_root, "adr", "exc-feat", "2026-03-06")
    _write_doc(vault_root, "exec", "exc-feat", "2026-03-06")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"feature": "exc-feat"})
        docs = data_of(result)
        types = {d["type"] for d in docs}
        assert "exec" not in types
        assert "adr" in types


async def test_find_includes_exec_when_explicit(vault_root: Path) -> None:
    """Naming ``exec`` in the type filter opts execution records back in."""
    _write_doc(vault_root, "exec", "exp-feat", "2026-03-06")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"type": ["exec"]})
        docs = data_of(result)
        assert len(docs) >= 1
        assert all(d["type"] == "exec" for d in docs)


async def test_find_with_body(vault_root: Path) -> None:
    """``body`` attaches each document's prose to its result row."""
    _write_doc(
        vault_root,
        "adr",
        "body-feat",
        "2026-03-06",
        "# Body Test",
        "\nSome body content.\n",
    )
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "find", {"feature": "body-feat", "body": "full", "limit": 5}
        )
        docs = data_of(result)
        assert len(docs) >= 1
        assert "body" in docs[0]
        assert "Some body content" in docs[0]["body"]


async def test_find_respects_limit(vault_root: Path) -> None:
    """``limit`` caps the number of returned document rows."""
    _write_doc(vault_root, "adr", "lim-a", "2026-03-06")
    _write_doc(vault_root, "adr", "lim-b", "2026-03-06")
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"type": ["adr"], "limit": 1})
        docs = data_of(result)
        assert len(docs) == 1


async def test_body_full_is_refused_above_a_handful_of_rows(vault_root: Path) -> None:
    """Whole documents are reserved for a caller that has already narrowed.

    Twenty documents at ``body="full"`` measured 196,176 bytes - past the
    ceiling for one response, using nothing but the default limit. The refusal
    names ``excerpt`` so the caller has somewhere to go.
    """
    _write_doc(vault_root, "research", "full-guard", "2026-01-01")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "find", {"type": ["research"], "body": "full", "limit": 20}
        )

    assert result.is_error
    text = " ".join(str(getattr(c, "text", "")) for c in result.content)
    assert "excerpt" in text


async def test_an_excerpt_says_what_it_left_behind(vault_root: Path) -> None:
    """An excerpt carries the full size, so a caller knows what it did not get."""
    _write_doc(
        vault_root,
        "research",
        "excerpt-feat",
        "2026-01-01",
        body="x" * 5000,
    )

    mcp = create_server()
    async with Client(mcp) as client:
        rows = data_of(
            await client.call_tool(
                "find", {"feature": "excerpt-feat", "body": "excerpt"}
            )
        )

    row = rows[0]
    assert row["body_truncated"] is True
    assert row["body_bytes"] > len(row["body"])


async def test_a_hostile_limit_is_refused_rather_than_clamped(
    vault_root: Path,
) -> None:
    """A negative limit fails loudly instead of returning nearly everything.

    Regression: an unbounded ``int`` limit reached a Python slice, so
    ``limit=-1`` silently returned 659 of 660 rows.
    """
    mcp = create_server()
    async with Client(mcp) as client:
        for bad in (-1, 0, 10_000):
            result = await client.call_tool("find", {"limit": bad})
            assert result.is_error, f"limit={bad} was accepted"


async def test_text_filter_matches_document_stem(vault_root: Path) -> None:
    """A substring of the stem selects the document.

    This is the degraded discovery path made real: without it the answer to
    "rag is not installed" was grep, which cannot see the vault's structure.
    """
    _write_doc(vault_root, "research", "payment-gateway", "2026-01-01")
    _write_doc(vault_root, "research", "user-profile", "2026-01-02")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "gateway"})

    names = [row["name"] for row in cast("list[dict[str, Any]]", data_of(result))]
    assert any("payment-gateway" in n for n in names)
    assert not any("user-profile" in n for n in names)


async def test_text_filter_matches_feature(vault_root: Path) -> None:
    """The feature tag is matched as well as the stem."""
    _write_doc(vault_root, "adr", "billing-engine", "2026-01-01")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "billing"})

    rows = cast("list[dict[str, Any]]", data_of(result))
    assert rows
    assert all("billing" in (r.get("feature") or "") for r in rows)


async def test_text_filter_is_case_insensitive(vault_root: Path) -> None:
    _write_doc(vault_root, "research", "payment-gateway", "2026-01-01")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "GATEWAY"})

    assert cast("list[dict[str, Any]]", data_of(result))


async def test_text_filter_switches_to_search_mode_on_its_own(
    vault_root: Path,
) -> None:
    """``text`` alone is a document search, not a feature roll-up.

    A roll-up row carries ``doc_count``; a search row carries ``path``.
    Asserting on the shape catches a mode-switch regression that a name-only
    assertion would sail past.
    """
    _write_doc(vault_root, "research", "payment-gateway", "2026-01-01")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "payment"})

    rows = cast("list[dict[str, Any]]", data_of(result))
    assert rows
    assert all(r.get("path") for r in rows)


async def test_text_filter_composes_with_type(vault_root: Path) -> None:
    """``text`` narrows within the type filter rather than replacing it."""
    _write_doc(vault_root, "adr", "shared-name", "2026-01-01")
    _write_doc(vault_root, "research", "shared-name", "2026-01-02")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "shared", "type": ["adr"]})

    rows = cast("list[dict[str, Any]]", data_of(result))
    assert rows
    assert all(r["type"] == "adr" for r in rows)


async def test_text_filter_caps_matches_not_candidates(vault_root: Path) -> None:
    """``limit`` bounds what matched, not what was scanned.

    Filtering after the cap would let non-matching documents consume the
    budget and return fewer matches than exist - the failure mode that makes
    a filter look broken on a large vault and fine on a small one.
    """
    for i in range(6):
        _write_doc(vault_root, "research", f"alpha-{i}", f"2026-02-0{i + 1}")
    for i in range(6):
        _write_doc(vault_root, "research", f"beta-{i}", f"2026-03-0{i + 1}")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "beta", "limit": 5})

    rows = cast("list[dict[str, Any]]", data_of(result))
    assert len(rows) == 5
    assert all("beta" in r["name"] for r in rows)


async def test_text_filter_with_no_match_returns_empty(vault_root: Path) -> None:
    _write_doc(vault_root, "research", "payment-gateway", "2026-01-01")

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "nothing-matches-this"})

    assert cast("list[dict[str, Any]]", data_of(result)) == []


async def test_text_filter_composes_with_body_tiering(vault_root: Path) -> None:
    """``text`` and ``body`` compose; the excerpt accounting still applies."""
    _write_doc(
        vault_root,
        "research",
        "payment-gateway",
        "2026-01-01",
        heading="# Heading",
        body="x" * 4000,
    )

    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("find", {"text": "gateway", "body": "excerpt"})

    rows = cast("list[dict[str, Any]]", data_of(result))
    assert rows
    assert rows[0]["body_truncated"] is True
    assert rows[0]["body_bytes"] > len(rows[0]["body"])
