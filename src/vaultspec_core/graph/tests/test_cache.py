"""Correctness tests proving the graph fingerprint cache is never stale.

Every test runs against a real on-disk synthetic vault with no mocks,
patches, or ``time.sleep`` hacks.  The contract under test is "stale never
trusted": a cache may only be served when the corpus on disk is byte-for-byte
the corpus the cache was built over.  The tests prove each invalidation
trigger independently:

- a content edit (changed size, and changed content hash even at equal size)
  forces a rebuild that reflects the new bytes;
- an added file appears in the next build;
- a removed file disappears from the next build;
- a corrupt or truncated cache file degrades silently to a full rebuild;
- a cache hit reconstructs a graph behaviourally identical to a fresh build;
- a real CLI mutation refreshes the cache so the next build is not stale.

Each assertion is anchored to an exact value derived from the fixture, not
copied from a prior run, so a regression that served stale data would fail
rather than pass quietly.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from ...cli import app
from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from .. import cache as cache_mod
from ..api import VaultGraph

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Build a fresh, writable synthetic vault for one test.

    Function-scoped (not session-scoped) because every test in this module
    mutates the corpus or the cache; a shared root would leak state across
    tests and mask the very staleness the suite exists to detect.
    """
    reset_config()
    build_synthetic_vault(
        tmp_path,
        n_docs=30,
        seed=9,
        pathologies=["cycle", "stem_collision", "phantom_only_links"],
    )
    return tmp_path


def _word_count(graph: VaultGraph, name: str) -> int:
    """Return the parsed word count for node *name* off the built graph."""
    return graph.nodes[name].word_count


def _scanned_fingerprints(root: Path) -> dict[str, cache_mod.Fingerprint]:
    """Fingerprint the current vault exactly as the graph build does."""
    from ...vaultcore import scan_vault

    return cache_mod.fingerprint_vault(list(scan_vault(root)), root)


# ---------------------------------------------------------------------------
# (a) content change forces a rebuild, never serves the cached old state
# ---------------------------------------------------------------------------


class TestContentChangeInvalidates:
    def test_changed_body_reflected_not_cached(self, vault_root: Path) -> None:
        first = VaultGraph(vault_root)
        # Pick a real, non-phantom document with a backing file.
        target_name = next(
            name
            for name, node in sorted(first.nodes.items())
            if not node.phantom and node.path is not None
        )
        target_path = first.nodes[target_name].path
        assert target_path is not None
        original_words = _word_count(first, target_name)

        # Append words: this changes the file size, so even the fast-path
        # (size, mtime) guard alone would catch it.
        added = " extra unique sentinel words appended to the document body"
        target_path.write_text(
            target_path.read_text(encoding="utf-8") + added,
            encoding="utf-8",
        )
        expected_words = original_words + len(added.split())

        # Sanity: validate must report the cache as stale now.
        payload = cache_mod.load(cache_mod.cache_path(vault_root))
        assert payload is not None
        assert (
            cache_mod.validate(payload.manifest, _scanned_fingerprints(vault_root))
            is False
        )

        second = VaultGraph(vault_root)
        assert _word_count(second, target_name) == expected_words
        assert _word_count(second, target_name) != original_words

    def test_same_size_edit_caught_by_content_hash(self, vault_root: Path) -> None:
        # Build, then overwrite a real document with content of the SAME byte
        # length but different bytes.  Size is unchanged; only the content
        # hash differs.  This is the case the bare (size, mtime) guard could
        # miss within one timestamp tick, and the hash must catch it.
        first = VaultGraph(vault_root)
        target_name = next(
            name
            for name, node in sorted(first.nodes.items())
            if not node.phantom and node.path is not None and node.title is not None
        )
        target_path = first.nodes[target_name].path
        assert target_path is not None
        original_text = target_path.read_text(encoding="utf-8")
        original_title = first.nodes[target_name].title
        assert original_title is not None

        # Flip a single character in the title heading, preserving length.
        # The title starts with "# "; replace the first title letter so the
        # parsed title text changes but the byte count does not.
        marker = f"# {original_title}"
        assert marker in original_text
        first_letter = original_title[0]
        flipped = "Z" if first_letter != "Z" else "Y"
        mutated = original_text.replace(
            marker,
            f"# {flipped}{original_title[1:]}",
            1,
        )
        assert len(mutated.encode("utf-8")) == len(original_text.encode("utf-8"))
        target_path.write_text(mutated, encoding="utf-8")

        current = _scanned_fingerprints(vault_root)
        payload = cache_mod.load(cache_mod.cache_path(vault_root))
        assert payload is not None
        # The size+mtime alone could collide; the content hash differs, so
        # validation must reject the cache.
        assert cache_mod.validate(payload.manifest, current) is False

        second = VaultGraph(vault_root)
        assert second.nodes[target_name].title == f"{flipped}{original_title[1:]}"


# ---------------------------------------------------------------------------
# (b) added file appears, (c) removed file disappears
# ---------------------------------------------------------------------------


class TestFileSetChangesInvalidate:
    def test_added_file_appears(self, vault_root: Path) -> None:
        first = VaultGraph(vault_root)
        new_stem = "2026-01-01-cache-added-doc"
        assert new_stem not in first.nodes

        new_path = vault_root / ".vault" / "adr" / f"{new_stem}.md"
        new_path.write_text(
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#cache-add-feature'\n"
            "date: '2026-01-01'\n"
            "related: []\n"
            "---\n"
            "\n# cache added doc\n\nA freshly added document.\n",
            encoding="utf-8",
        )

        second = VaultGraph(vault_root)
        assert new_stem in second.nodes
        assert second.nodes[new_stem].feature == "cache-add-feature"

    def test_removed_file_disappears(self, vault_root: Path) -> None:
        first = VaultGraph(vault_root)
        removable = next(
            name
            for name, node in sorted(first.nodes.items())
            if not node.phantom and node.path is not None
        )
        target_path = first.nodes[removable].path
        assert target_path is not None
        target_path.unlink()

        second = VaultGraph(vault_root)
        assert removable not in second.nodes


# ---------------------------------------------------------------------------
# (d) corrupt / truncated cache degrades to a full rebuild
# ---------------------------------------------------------------------------


class TestCorruptCacheRebuilds:
    def test_truncated_cache_rebuilds(self, vault_root: Path) -> None:
        fresh = VaultGraph(vault_root, use_cache=False)
        expected_nodes = fresh.digraph.number_of_nodes()
        expected_edges = fresh.digraph.number_of_edges()

        # Prime the cache, then truncate the cache file to invalid JSON.
        VaultGraph(vault_root)
        cache_file = cache_mod.cache_path(vault_root)
        assert cache_file.exists()
        cache_file.write_text("{ this is not valid json", encoding="utf-8")

        assert cache_mod.load(cache_file) is None

        rebuilt = VaultGraph(vault_root)
        assert rebuilt.digraph.number_of_nodes() == expected_nodes
        assert rebuilt.digraph.number_of_edges() == expected_edges
        # The build must have rewritten a valid cache.
        assert cache_mod.load(cache_file) is not None

    def test_empty_cache_file_rebuilds(self, vault_root: Path) -> None:
        fresh = VaultGraph(vault_root, use_cache=False)
        expected_nodes = fresh.digraph.number_of_nodes()

        VaultGraph(vault_root)
        cache_file = cache_mod.cache_path(vault_root)
        cache_file.write_text("", encoding="utf-8")
        assert cache_mod.load(cache_file) is None

        rebuilt = VaultGraph(vault_root)
        assert rebuilt.digraph.number_of_nodes() == expected_nodes


# ---------------------------------------------------------------------------
# (e) cache hit is behaviourally identical to a fresh build
# ---------------------------------------------------------------------------


class TestCacheHitIsIdentical:
    def test_cached_graph_matches_fresh_build(self, vault_root: Path) -> None:
        fresh = VaultGraph(vault_root, use_cache=False)
        fresh_json = fresh.to_json(include_body=True)

        # First cached build writes the cache; second is a guaranteed hit.
        VaultGraph(vault_root)
        cached = VaultGraph(vault_root)
        cached_json = cached.to_json(include_body=True)

        assert cached_json == fresh_json

        # Node set, edges, and per-node metrics match exactly.
        assert set(cached.nodes) == set(fresh.nodes)
        assert cached.digraph.number_of_edges() == fresh.digraph.number_of_edges()
        for name in fresh.digraph.nodes():
            fresh_attrs = fresh.digraph.nodes[name]
            cached_attrs = cached.digraph.nodes[name]
            assert cached_attrs["pagerank"] == fresh_attrs["pagerank"]
            assert cached_attrs["in_degree"] == fresh_attrs["in_degree"]
        for src, dst, data in fresh.digraph.edges(data=True):
            cached_data = cached.digraph.edges[src, dst]
            assert cached_data["kind"] == data["kind"]
            assert cached_data["multiplicity"] == data["multiplicity"]
            assert cached_data["weight"] == data["weight"]
        assert sorted(cached.get_dangling_links()) == sorted(fresh.get_dangling_links())

    def test_cache_hit_validates(self, vault_root: Path) -> None:
        VaultGraph(vault_root)
        payload = cache_mod.load(cache_mod.cache_path(vault_root))
        assert payload is not None
        # Unchanged corpus: validation must pass.
        assert cache_mod.validate(payload.manifest, _scanned_fingerprints(vault_root))


# ---------------------------------------------------------------------------
# (f) a CLI mutation refreshes the cache
# ---------------------------------------------------------------------------


class TestCliMutationRefreshesCache:
    def test_link_add_invalidates_cache(self, vault_root: Path) -> None:
        # Prime the cache.
        VaultGraph(vault_root)
        cache_file = cache_mod.cache_path(vault_root)
        assert cache_file.exists()

        # Choose a real source document and a real target it does not link to.
        graph = VaultGraph(vault_root)
        src_name = next(
            name
            for name, node in sorted(graph.nodes.items())
            if not node.phantom and node.path is not None
        )
        dst_name = next(
            name
            for name, node in sorted(graph.nodes.items())
            if not node.phantom
            and node.path is not None
            and name != src_name
            and name not in graph.nodes[src_name].out_links
        )

        runner = CliRunner(env={"NO_COLOR": "1"})
        result = runner.invoke(
            app,
            [
                "--target",
                str(vault_root),
                "vault",
                "link",
                "add",
                src_name,
                dst_name,
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["status"] == "created"

        # The mutating verb must have dropped the cache file.
        assert not cache_file.exists()

        # The next build reflects the new edge (not the stale cached graph).
        reset_config()
        rebuilt = VaultGraph(vault_root)
        assert dst_name in rebuilt.nodes[src_name].out_links


# ---------------------------------------------------------------------------
# (g) validate() content-hash guard - pure unit tests
# ---------------------------------------------------------------------------


class TestValidateHashGuard:
    """Isolate the content-hash guard in :func:`~vaultspec_core.graph.cache.validate`.

    These tests call ``validate`` directly with hand-built manifest dicts so
    the hash guard is exercised independently of mtime or size changes, which
    is the scenario the existing filesystem-level test
    ``test_same_size_edit_caught_by_content_hash`` cannot isolate (a real
    write also bumps mtime, so the size-or-mtime guard fires first).
    """

    def test_identical_fingerprints_validate(self) -> None:
        # Same size, same mtime, same hash: valid.
        manifest: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        current: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        assert cache_mod.validate(manifest, current) is True

    def test_different_hash_invalidates(self) -> None:
        # Identical size and mtime, different hash: must invalidate.
        manifest: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        current: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h2")}
        assert cache_mod.validate(manifest, current) is False

    def test_different_size_invalidates(self) -> None:
        manifest: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        current: dict[str, cache_mod.Fingerprint] = {"a.md": (11, 5, "h1")}
        assert cache_mod.validate(manifest, current) is False

    def test_different_mtime_invalidates(self) -> None:
        manifest: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        current: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 6, "h1")}
        assert cache_mod.validate(manifest, current) is False

    def test_added_key_invalidates(self) -> None:
        manifest: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        current: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2"),
        }
        assert cache_mod.validate(manifest, current) is False

    def test_removed_key_invalidates(self) -> None:
        manifest: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2"),
        }
        current: dict[str, cache_mod.Fingerprint] = {"a.md": (10, 5, "h1")}
        assert cache_mod.validate(manifest, current) is False

    def test_empty_manifests_validate(self) -> None:
        assert cache_mod.validate({}, {}) is True

    def test_multiple_keys_all_match(self) -> None:
        manifest: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2"),
        }
        current: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2"),
        }
        assert cache_mod.validate(manifest, current) is True

    def test_multiple_keys_one_hash_differs(self) -> None:
        # One entry has same size+mtime but different hash: must invalidate.
        manifest: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2"),
        }
        current: dict[str, cache_mod.Fingerprint] = {
            "a.md": (10, 5, "h1"),
            "b.md": (20, 7, "h2-changed"),
        }
        assert cache_mod.validate(manifest, current) is False


# ---------------------------------------------------------------------------
# (h) _stem_index parity between fresh build and cache-loaded graph (L1)
# ---------------------------------------------------------------------------


class TestStemIndexParity:
    """Assert that a cache-loaded graph's ``_stem_index`` excludes phantom nodes
    and therefore equals a fresh build's ``_stem_index`` for a corpus with phantoms.
    """

    def test_stem_index_excludes_phantoms_after_cache_load(
        self, vault_root: Path
    ) -> None:
        # Ensure the fixture contains at least one phantom node.
        fresh = VaultGraph(vault_root, use_cache=False)
        phantoms = [n for n, node in fresh.nodes.items() if node.phantom]
        assert phantoms, (
            "Test corpus must have phantom nodes (use the 'phantom_only_links' "
            "pathology when building the fixture)."
        )

        # Prime the on-disk cache.
        VaultGraph(vault_root)
        assert cache_mod.cache_path(vault_root).exists()

        # Load from cache; verify _stem_index excludes every phantom key.
        cached = VaultGraph(vault_root)
        for phantom_key in phantoms:
            bare_stem = (
                phantom_key.split("/", 1)[1] if "/" in phantom_key else phantom_key
            )
            # The bare stem must not appear as a key in _stem_index that
            # maps to the phantom key.  (It may still be present if a real
            # node shares the same bare stem, but that is not the phantom
            # contributing it.)
            if bare_stem in cached._stem_index:
                for mapped_key in cached._stem_index[bare_stem]:
                    assert not cached.nodes[mapped_key].phantom, (
                        f"_stem_index[{bare_stem!r}] contains phantom key "
                        f"{mapped_key!r} after cache load."
                    )

    def test_stem_index_matches_fresh_build(self, vault_root: Path) -> None:
        fresh = VaultGraph(vault_root, use_cache=False)
        fresh_stem_index = dict(fresh._stem_index)

        # Prime cache and load from it.
        VaultGraph(vault_root)
        cached = VaultGraph(vault_root)
        cached_stem_index = dict(cached._stem_index)

        assert cached_stem_index == fresh_stem_index, (
            f"_stem_index mismatch between cached and fresh build.\n"
            f"Keys only in fresh: {set(fresh_stem_index) - set(cached_stem_index)}\n"
            f"Keys only in cached: {set(cached_stem_index) - set(fresh_stem_index)}"
        )
