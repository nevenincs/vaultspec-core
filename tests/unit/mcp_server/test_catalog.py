"""Tests for the gateway command catalog parsed from the CLI reference.

Builds the catalog from the real ``.vaultspec/reference/cli.md`` shipped into a
:class:`WorkspaceFactory`-installed vault - no fixtures, mocks, or hand-written
inventories - and asserts the marker block yields the expected verb paths and
enriched flag schemas, the static denylist is removed from the catalog and
reported by :meth:`CommandCatalog.is_denied`, a missing marker block raises
loudly, and the ranking surfaces a known verb for a plausible query.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vaultspec_core.mcp_server.catalog import DENYLIST, build_catalog

from .conftest import vault_root  # noqa: F401 - re-exported fixture

pytestmark = [pytest.mark.unit]


def _reference(root: Path) -> Path:
    return root / ".vaultspec" / "reference" / "cli.md"


def test_marker_block_yields_expected_verb_paths(vault_root):  # noqa: F811
    """The parsed catalog contains hot and long-tail verb paths verbatim."""
    catalog = build_catalog(_reference(vault_root))

    assert catalog.declares(("vault", "list"))
    assert catalog.declares(("status",))
    assert catalog.declares(("vault", "plan", "status"))
    # The catalog is non-trivial: the CLI declares over a hundred verbs.
    assert len(catalog.entries) > 100


def test_verb_entry_carries_flag_schema_and_json_support(vault_root):  # noqa: F811
    """A cataloged verb exposes its declared flags and ``--json`` support."""
    catalog = build_catalog(_reference(vault_root))

    entry = catalog.get(("vault", "list"))
    assert entry is not None
    assert entry.verb == "vault list"
    assert entry.description  # curated help text from the marker block
    flag_names = {flag.name for flag in entry.flags}
    assert "--feature" in flag_names
    assert "--json" in flag_names
    assert entry.supports_json is True
    # ``--feature`` takes a value; the boolean ``--json`` switch does not.
    feature_flag = entry.flag("--feature")
    json_flag = entry.flag("--json")
    assert feature_flag is not None
    assert json_flag is not None
    assert feature_flag.takes_value is True
    assert json_flag.takes_value is False


def test_denylisted_verbs_absent_from_catalog(vault_root):  # noqa: F811
    """Every denylisted verb is excluded from entries yet reported as denied."""
    catalog = build_catalog(_reference(vault_root))

    for denied in DENYLIST:
        assert not catalog.declares(denied), denied
        assert catalog.get(denied) is None, denied
        assert catalog.is_denied(denied), denied

    # Spot-check the specific classes the ADR names.
    assert catalog.is_denied(("uninstall",))
    assert catalog.is_denied(("spec", "mcps", "add"))
    assert catalog.is_denied(("spec", "mcps", "uninstall"))
    assert catalog.is_denied(("vault", "feature", "index"))
    # Read-only MCP-registry inspection stays reachable.
    assert catalog.declares(("spec", "mcps", "list"))
    assert catalog.declares(("spec", "mcps", "status"))


def test_denylisted_verbs_never_ranked(vault_root):  # noqa: F811
    """A denied verb never surfaces through the ranking used by ``discover``."""
    catalog = build_catalog(_reference(vault_root))

    ranked = catalog.search("index feature", limit=50)
    verbs = {entry.verb for _, entry in ranked}
    assert "vault feature index" not in verbs


def test_search_ranks_a_known_verb_for_its_intent(vault_root):  # noqa: F811
    """A verb-word query ranks the matching verb among the top results."""
    catalog = build_catalog(_reference(vault_root))

    ranked = catalog.search("list vault documents", limit=5)
    assert ranked, "expected at least one ranked result"
    top_verbs = {entry.verb for _, entry in ranked}
    assert "vault list" in top_verbs
    # Scores are non-increasing (best match first).
    scores = [score for score, _ in ranked]
    assert scores == sorted(scores, reverse=True)


def test_missing_marker_block_raises(vault_root):  # noqa: F811
    """A reference without the generated markers fails loudly, not silently."""
    bare = Path(tempfile.mkdtemp(prefix="vsc-cat-nomark-"))
    try:
        ref = bare / "cli.md"
        ref.write_text("# CLI reference\n\nNo inventory here.\n", encoding="utf-8")
        with pytest.raises(ValueError, match="command-inventory markers"):
            build_catalog(ref)
    finally:
        import shutil

        shutil.rmtree(bare, ignore_errors=True)
