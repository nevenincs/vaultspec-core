"""Correctness tests proving the graph fingerprint cache is never stale.

Every test runs against a real on-disk synthetic vault with no mocks,
patches, or ``time.sleep`` hacks.  The contract under test is the
racily-clean rule: a cache is served only when the file set matches, every
file's size and mtime match the manifest, and any file whose mtime is not
older than the cache file's own mtime additionally matches its stored
content hash.  The tests prove each trigger independently:

- a content edit (changed size or mtime) forces a rebuild that reflects the
  new bytes;
- a same-size edit on a racy file (mtime not older than the cache write) is
  caught by the hash guard;
- the accepted residual window - a same-size edit whose mtime is restored
  below the cache write tick - is served stale by design and caught by the
  explicit ``deep=True`` verification path;
- an added file appears in the next build;
- a removed file disappears from the next build;
- a corrupt or truncated cache file degrades silently to a full rebuild;
- a cache file whose manifest or encoding-issue rows are structurally
  malformed is rejected whole rather than partly trusted;
- a cache hit reconstructs a graph behaviourally identical to a fresh build;
- a real CLI mutation refreshes the cache so the next build is not stale.

Each assertion is anchored to an exact value derived from the fixture, not
copied from a prior run, so a regression that served stale data would fail
rather than pass quietly.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from ...cli import app
from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from .. import cache as cache_mod
from ..api import VaultGraph
from .conftest import stem_index_of

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


def _validate_against_disk(root: Path, *, deep: bool = False) -> bool:
    """Validate the on-disk cache against the corpus exactly as the build does."""
    from ...vaultcore import scan_vault

    cache_file = cache_mod.cache_path(root)
    payload = cache_mod.load(cache_file)
    assert payload is not None
    return cache_mod.validate(
        payload.manifest,
        list(scan_vault(root)),
        root,
        cache_mtime_ns=cache_file.stat().st_mtime_ns,
        deep=deep,
    )


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
        assert _validate_against_disk(vault_root) is False

        second = VaultGraph(vault_root)
        assert _word_count(second, target_name) == expected_words
        assert _word_count(second, target_name) != original_words

    def _same_size_title_flip(self, vault_root: Path) -> tuple[Path, str, str]:
        """Build once and apply a same-size title edit with the mtime restored.

        Overwrites a real document with content of the SAME byte length but
        different bytes, then restores the file's original ``(atime, mtime)``
        with ``os.utime`` so the stat guard cannot see the edit.  Returns the
        edited path, the node name, and the flipped title text.
        """
        first = VaultGraph(vault_root)
        target_name = next(
            name
            for name, node in sorted(first.nodes.items())
            if not node.phantom and node.path is not None and node.title is not None
        )
        target_path = first.nodes[target_name].path
        assert target_path is not None
        original_stat = target_path.stat()
        original_text = target_path.read_text(encoding="utf-8")
        original_title = first.nodes[target_name].title
        assert original_title is not None

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
        os.utime(
            target_path,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
        )
        return target_path, target_name, f"{flipped}{original_title[1:]}"

    def test_same_size_racy_edit_caught_by_content_hash(self, vault_root: Path) -> None:
        # A same-size, same-mtime edit on a RACY file (file mtime not older
        # than the cache file's mtime) must be caught by the hash guard.
        # Age the cache file below the document's restored mtime so the
        # racily-clean rule classifies the document as racy.
        target_path, target_name, flipped_title = self._same_size_title_flip(vault_root)
        cache_file = cache_mod.cache_path(vault_root)
        doc_mtime_ns = target_path.stat().st_mtime_ns
        cache_stat = cache_file.stat()
        os.utime(cache_file, ns=(cache_stat.st_atime_ns, doc_mtime_ns))

        assert _validate_against_disk(vault_root) is False

        second = VaultGraph(vault_root)
        assert second.nodes[target_name].title == flipped_title

    def test_same_size_non_racy_edit_is_accepted_stale_until_deep(
        self, vault_root: Path
    ) -> None:
        # The ADR-accepted residual window: a same-size edit whose mtime is
        # restored below the cache write tick passes stat validation and is
        # served stale by design.  The explicit deep verification path must
        # still catch it.
        self._same_size_title_flip(vault_root)
        cache_file = cache_mod.cache_path(vault_root)
        assert cache_file.stat().st_mtime_ns > max(
            p.stat().st_mtime_ns for p in (vault_root / ".vault").rglob("*.md")
        )

        assert _validate_against_disk(vault_root) is True
        assert _validate_against_disk(vault_root, deep=True) is False


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


class TestMalformedPayloadRowsRejected:
    """A structurally valid JSON cache with a bad row is still a miss.

    ``load`` is the only gate between cache bytes and the restored corpus,
    so a row that cannot be read back as its declared type must reject the
    whole payload. Accepting the file and dropping the row would restore a
    corpus that quietly differs from the one the cache was built over.
    Every case writes a real cache file and reads it back through ``load``.
    """

    def _write(self, tmp_path: Path, payload: dict[str, object]) -> Path:
        cache_file = tmp_path / "graph.json"
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
        return cache_file

    def _payload(self) -> dict[str, object]:
        """Return a minimal payload that satisfies every documented shape."""
        return {
            "schema": cache_mod.CACHE_SCHEMA,
            "manifest": {".vault/research/a.md": [128, 1700000000123456789, "ab12"]},
            "graph": {"nodes": [], "edges": []},
            "dangling_links": [["a", "b"]],
            "encoding_issues": [
                [".vault/research/a.md", "decode", "invalid start byte", 41],
                [".vault/research/b.md", "read", "permission denied", None],
            ],
        }

    def test_well_formed_payload_round_trips(self, tmp_path: Path) -> None:
        loaded = cache_mod.load(self._write(tmp_path, self._payload()))

        assert loaded is not None
        assert loaded.manifest == {
            ".vault/research/a.md": (128, 1700000000123456789, "ab12")
        }
        assert loaded.dangling_links == [["a", "b"]]
        assert loaded.encoding_issues == [
            (".vault/research/a.md", "decode", "invalid start byte", 41),
            (".vault/research/b.md", "read", "permission denied", None),
        ]

    @pytest.mark.parametrize(
        "row",
        [
            [128, 1700000000123456789],
            [128, 1700000000123456789, "ab12", "extra"],
            [128, 1700000000.5, "ab12"],
            ["128", 1700000000123456789, "ab12"],
            [128, 1700000000123456789, None],
            {"size": 128},
            "128",
        ],
        ids=[
            "too-short",
            "too-long",
            "float-mtime",
            "string-size",
            "null-hash",
            "object-not-list",
            "scalar-not-list",
        ],
    )
    def test_malformed_manifest_row_rejects_payload(
        self, tmp_path: Path, row: object
    ) -> None:
        payload = self._payload()
        payload["manifest"] = {".vault/research/a.md": row}

        assert cache_mod.load(self._write(tmp_path, payload)) is None

    @pytest.mark.parametrize(
        "row",
        [
            [".vault/research/a.md", "decode", "invalid start byte"],
            [".vault/research/a.md", "decode", "invalid start byte", 41, "extra"],
            [None, "decode", "invalid start byte", 41],
            [".vault/research/a.md", 7, "invalid start byte", 41],
            [".vault/research/a.md", "decode", None, 41],
            [".vault/research/a.md", "decode", "invalid start byte", 41.5],
            [".vault/research/a.md", "decode", "invalid start byte", "41"],
            "decode",
        ],
        ids=[
            "too-short",
            "too-long",
            "null-path",
            "int-kind",
            "null-detail",
            "float-start",
            "string-start",
            "scalar-not-list",
        ],
    )
    def test_malformed_encoding_row_rejects_payload(
        self, tmp_path: Path, row: object
    ) -> None:
        payload = self._payload()
        payload["encoding_issues"] = [row]

        assert cache_mod.load(self._write(tmp_path, payload)) is None

    def test_null_start_is_accepted_on_every_encoding_row(self, tmp_path: Path) -> None:
        payload = self._payload()
        payload["encoding_issues"] = [[".vault/research/a.md", "read", "gone", None]]

        loaded = cache_mod.load(self._write(tmp_path, payload))

        assert loaded is not None
        assert loaded.encoding_issues == [
            (".vault/research/a.md", "read", "gone", None)
        ]


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
        # Unchanged corpus: validation must pass.
        assert _validate_against_disk(vault_root) is True


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
# (g) validate() racily-clean guards - real-file unit tests
# ---------------------------------------------------------------------------


class TestValidateRacilyClean:
    """Isolate each guard in :func:`~vaultspec_core.graph.cache.validate`.

    Every case runs against real files under ``tmp_path`` with real stat
    values; mtimes are steered with ``os.utime`` (a real filesystem
    operation) so the racy and non-racy branches are each exercised
    deliberately.
    """

    def _corpus(
        self, tmp_path: Path
    ) -> tuple[list[Path], dict[str, cache_mod.Fingerprint]]:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("alpha document body\n", encoding="utf-8")
        b.write_text("beta document body\n", encoding="utf-8")
        files = [a, b]
        return files, cache_mod.fingerprint_vault(files, tmp_path)

    @staticmethod
    def _max_mtime_ns(files: list[Path]) -> int:
        return max(p.stat().st_mtime_ns for p in files)

    def test_unchanged_corpus_validates_without_racy_files(
        self, tmp_path: Path
    ) -> None:
        files, manifest = self._corpus(tmp_path)
        newer = self._max_mtime_ns(files) + 1
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=newer) is True
        )

    def test_unknown_cache_mtime_degrades_to_full_hash_and_validates(
        self, tmp_path: Path
    ) -> None:
        files, manifest = self._corpus(tmp_path)
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=None) is True
        )

    def test_size_change_invalidates(self, tmp_path: Path) -> None:
        files, manifest = self._corpus(tmp_path)
        files[0].write_text("alpha document body grown\n", encoding="utf-8")
        newer = self._max_mtime_ns(files) + 1
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=newer) is False
        )

    def test_mtime_change_invalidates(self, tmp_path: Path) -> None:
        # Bump by a full second: below-filesystem-resolution deltas (e.g.
        # +1ns on NTFS's 100ns clock) are silently rounded away by utime.
        files, manifest = self._corpus(tmp_path)
        stat = files[0].stat()
        os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        newer = self._max_mtime_ns(files) + 1
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=newer) is False
        )

    def test_racy_same_size_edit_caught_by_hash(self, tmp_path: Path) -> None:
        # Same byte count, same restored mtime: only the hash differs.  With
        # the cache reference at or below the file's mtime the file is racy
        # and the hash guard must fire.
        files, manifest = self._corpus(tmp_path)
        stat = files[0].stat()
        files[0].write_text("ALPHA document body\n", encoding="utf-8")
        os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert (
            cache_mod.validate(
                manifest, files, tmp_path, cache_mtime_ns=stat.st_mtime_ns
            )
            is False
        )

    def test_non_racy_same_size_edit_is_accepted_until_deep(
        self, tmp_path: Path
    ) -> None:
        # The accepted residual window: with the cache reference newer than
        # the file's restored mtime, stat validation trusts the file; the
        # explicit deep path still catches the edit.
        files, manifest = self._corpus(tmp_path)
        stat = files[0].stat()
        files[0].write_text("ALPHA document body\n", encoding="utf-8")
        os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns))
        newer = self._max_mtime_ns(files) + 1
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=newer) is True
        )
        assert (
            cache_mod.validate(
                manifest, files, tmp_path, cache_mtime_ns=newer, deep=True
            )
            is False
        )

    def test_added_file_invalidates(self, tmp_path: Path) -> None:
        files, manifest = self._corpus(tmp_path)
        extra = tmp_path / "c.md"
        extra.write_text("gamma document body\n", encoding="utf-8")
        newer = self._max_mtime_ns([*files, extra]) + 1
        assert (
            cache_mod.validate(
                manifest, [*files, extra], tmp_path, cache_mtime_ns=newer
            )
            is False
        )

    def test_removed_file_invalidates(self, tmp_path: Path) -> None:
        files, manifest = self._corpus(tmp_path)
        newer = self._max_mtime_ns(files) + 1
        assert (
            cache_mod.validate(manifest, files[:1], tmp_path, cache_mtime_ns=newer)
            is False
        )

    def test_vanished_file_invalidates(self, tmp_path: Path) -> None:
        # The scanned list still names the file, but it is gone from disk:
        # the file-set equality check must report the divergence.
        files, manifest = self._corpus(tmp_path)
        files[0].unlink()
        newer = self._max_mtime_ns(files[1:]) + 1
        assert (
            cache_mod.validate(manifest, files, tmp_path, cache_mtime_ns=newer) is False
        )

    def test_empty_corpus_validates(self, tmp_path: Path) -> None:
        assert cache_mod.validate({}, [], tmp_path, cache_mtime_ns=None) is True


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
        cached_stem_index = stem_index_of(cached)
        for phantom_key in phantoms:
            bare_stem = (
                phantom_key.split("/", 1)[1] if "/" in phantom_key else phantom_key
            )
            # The bare stem must not appear as a key in _stem_index that
            # maps to the phantom key.  (It may still be present if a real
            # node shares the same bare stem, but that is not the phantom
            # contributing it.)
            if bare_stem in cached_stem_index:
                for mapped_key in cached_stem_index[bare_stem]:
                    assert not cached.nodes[mapped_key].phantom, (
                        f"_stem_index[{bare_stem!r}] contains phantom key "
                        f"{mapped_key!r} after cache load."
                    )

    def test_stem_index_matches_fresh_build(self, vault_root: Path) -> None:
        fresh = VaultGraph(vault_root, use_cache=False)
        fresh_stem_index = stem_index_of(fresh)

        # Prime cache and load from it.
        VaultGraph(vault_root)
        cached = VaultGraph(vault_root)
        cached_stem_index = stem_index_of(cached)

        assert cached_stem_index == fresh_stem_index, (
            f"_stem_index mismatch between cached and fresh build.\n"
            f"Keys only in fresh: {set(fresh_stem_index) - set(cached_stem_index)}\n"
            f"Keys only in cached: {set(cached_stem_index) - set(fresh_stem_index)}"
        )


class TestEncodingIssuesSurviveCache:
    """A cache hit must not lose the ingress read's decode failures.

    A document that fails to decode never becomes a usable node, so it is
    invisible in the serialised graph. Before these were persisted, a warm
    build restored a corpus that appeared to have read cleanly, which made
    the encoding check silently report nothing on every run after the first.
    """

    def _vault_with_undecodable_document(self, root: Path) -> Path:
        research = root / ".vault" / "research"
        research.mkdir(parents=True, exist_ok=True)
        (research / "2026-05-15-ok-research.md").write_text(
            "---\ntags:\n  - '#research'\n  - '#demo'\n"
            "date: '2026-05-15'\nrelated: []\n---\n\n# ok\n",
            encoding="utf-8",
        )
        broken = research / "2026-05-15-broken-research.md"
        broken.write_bytes(b"---\ntags:\n\xff\xfe not utf-8\n---\n\n# broken\n")
        return broken

    def test_cached_build_reports_same_encoding_issues_as_cold(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        broken = self._vault_with_undecodable_document(root)

        cold = VaultGraph(root, use_cache=False)
        VaultGraph(root)  # prime the cache
        warm = VaultGraph(root)

        assert [i.path for i in cold.encoding_issues] == [broken]
        assert [i.path for i in warm.encoding_issues] == [broken], (
            "the warm build lost the ingress read's decode failure"
        )
        assert [i.kind for i in warm.encoding_issues] == ["decode"]

    def test_encoding_check_agrees_across_cold_warm_and_standalone(
        self, tmp_path: Path
    ) -> None:
        from ...vaultcore.checks.encoding import check_encoding

        root = tmp_path / "repo"
        root.mkdir()
        self._vault_with_undecodable_document(root)

        cold_graph = VaultGraph(root, use_cache=False)
        cold = len(check_encoding(root, graph=cold_graph).diagnostics)
        VaultGraph(root)
        warm = len(check_encoding(root, graph=VaultGraph(root)).diagnostics)
        standalone = len(check_encoding(root).diagnostics)

        assert cold == standalone == 1
        assert warm == 1, "check_encoding went blind on a warm cache"


class TestUnreadableDocumentsExcludedFromGraphDerivedQueries:
    """The graph-backed query path must drop what the disk path drops.

    ``_scan_all`` skips a document it cannot decode. The graph still creates
    a node for such a file, with empty frontmatter and body, which is
    indistinguishable from a genuinely empty document by its fields alone.
    """

    def _vault(self, root: Path) -> None:
        for sub in ("research", "plan"):
            (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)
        (root / ".vault" / "research" / "2026-05-15-ok-research.md").write_text(
            "---\ntags:\n  - '#research'\n  - '#demo'\n"
            "date: '2026-05-15'\nrelated: []\n---\n\n# ok\n",
            encoding="utf-8",
        )
        (root / ".vault" / "research" / "2026-05-15-bad-research.md").write_bytes(
            b"---\ntags:\n\xff\xfe bad\n---\n\n# broken\n"
        )
        (root / ".vault" / "plan" / "2026-05-15-ok-plan.md").write_text(
            "---\ntags:\n  - '#plan'\n  - '#demo'\n"
            "date: '2026-05-15'\nrelated: []\n---\n\n# p\n",
            encoding="utf-8",
        )
        (root / ".vault" / "plan" / "2026-05-15-bad-plan.md").write_bytes(
            b"---\ntags:\n\xff\xfe bad\n---\n\n# broken\n"
        )

    def test_get_stats_totals_match_list_documents(self, tmp_path: Path) -> None:
        from ...vaultcore.query import get_stats, list_documents

        root = tmp_path / "repo"
        root.mkdir()
        self._vault(root)

        assert get_stats(root)["total_docs"] == len(list_documents(root))

    def test_collect_all_statuses_agrees_with_and_without_graph(
        self, tmp_path: Path
    ) -> None:
        from ...plan.status import collect_all_statuses

        root = tmp_path / "repo"
        root.mkdir()
        self._vault(root)

        without = collect_all_statuses(root)
        with_graph = collect_all_statuses(root, graph=VaultGraph(root))

        assert len(with_graph) == len(without)
        assert [e.document.name for e in with_graph] == [
            e.document.name for e in without
        ]
