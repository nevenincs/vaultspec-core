"""Tests for vault query engine."""

import pytest

from ...config import reset_config
from ...testing.synthetic import CorpusManifest, build_synthetic_vault
from ..query import (
    VaultDocument,
    _docs_from_graph,
    get_stats,
    list_documents,
    list_feature_details,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


@pytest.fixture
def vault_project(tmp_path) -> CorpusManifest:
    return build_synthetic_vault(
        tmp_path,
        n_docs=24,
        seed=42,
        pathologies=["dangling", "orphan"],
    )


class TestListDocuments:
    def test_list_all(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        assert len(docs) > 0
        assert all(isinstance(d, VaultDocument) for d in docs)

    def test_filter_by_type(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root, doc_type="adr")
        assert len(docs) > 0
        assert all(d.doc_type == "adr" for d in docs)

    def test_filter_by_feature(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        features = {d.feature for d in docs if d.feature}
        assert features, "Synthetic vault must produce docs with features"
        feature = next(iter(features))
        filtered = list_documents(vault_project.root, feature=feature)
        assert len(filtered) > 0
        assert all(d.feature == feature for d in filtered)

    def test_filter_by_date(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        dates = {d.date for d in docs if d.date}
        assert dates, "Synthetic vault must produce docs with dates"
        date = next(iter(dates))
        filtered = list_documents(vault_project.root, date=date)
        assert len(filtered) > 0
        assert all(d.date == date for d in filtered)

    def test_list_orphaned(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root, doc_type="orphaned")
        assert isinstance(docs, list)

    def test_list_invalid(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root, doc_type="invalid")
        assert isinstance(docs, list)

    def test_document_has_all_fields(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        assert docs, "Synthetic vault must produce at least one document"
        d = docs[0]
        assert hasattr(d, "path")
        assert hasattr(d, "name")
        assert hasattr(d, "doc_type")
        assert hasattr(d, "feature")
        assert hasattr(d, "date")
        assert hasattr(d, "tags")


class TestGetStats:
    def test_basic_stats(self, vault_project: CorpusManifest):
        stats = get_stats(vault_project.root)
        assert "total_docs" in stats
        assert "total_features" in stats
        assert "counts_by_type" in stats

    def test_stats_with_feature_filter(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        features = {d.feature for d in docs if d.feature}
        assert features, "Synthetic vault must produce docs with features"
        feature = next(iter(features))
        stats = get_stats(vault_project.root, feature=feature)
        assert "total_docs" in stats

    def test_stats_includes_orphan_count(self, vault_project: CorpusManifest):
        stats = get_stats(vault_project.root)
        assert "orphaned_count" in stats

    def test_stats_includes_dangling_count(self, vault_project: CorpusManifest):
        stats = get_stats(vault_project.root)
        assert "dangling_link_count" in stats


class TestListFeatureDetails:
    def test_returns_feature_info(self, vault_project: CorpusManifest):
        features = list_feature_details(vault_project.root)
        assert isinstance(features, list)
        if features:
            f = features[0]
            assert "name" in f
            assert "doc_count" in f
            assert "types" in f


class TestArchiveFeature:
    def test_archive_moves_docs(self, tmp_path):
        """Archiving moves all docs for a feature into .vault/_archive/."""
        from ..query import archive_feature

        # Set up a mini vault with a doc
        vault_dir = tmp_path / ".vault" / "adr"
        vault_dir.mkdir(parents=True)
        doc = vault_dir / "2026-03-16-test-feature-adr.md"
        doc.write_text(
            "---\ntags:\n  - adr\n  - test-feature\ndate: 2026-03-16\n---\nContent.\n",
            encoding="utf-8",
        )

        result = archive_feature(tmp_path, "test-feature")
        assert result["archived_count"] == 1
        assert not doc.exists()  # Original moved
        archive_dir = tmp_path / ".vault" / "_archive"
        assert archive_dir.exists()
        # File should be under _archive/adr/
        assert (archive_dir / "adr" / doc.name).exists()

    def test_archive_nonexistent_feature(self, tmp_path):
        """Archiving a feature with no docs raises VaultSpecError."""
        from ...core.exceptions import VaultSpecError
        from ..query import archive_feature

        # Set up an empty vault
        vault_dir = tmp_path / ".vault" / "adr"
        vault_dir.mkdir(parents=True)

        with pytest.raises(VaultSpecError, match="matches zero documents"):
            archive_feature(tmp_path, "nonexistent-feature-xyz")

    @pytest.mark.parametrize("empty_tag", ["", "   ", "#", " # "])
    def test_archive_empty_tag_refuses(self, tmp_path, empty_tag):
        """An empty/whitespace feature tag must be rejected, never treated
        as a wildcard that archives every document in the vault."""
        from ...core.exceptions import VaultSpecError
        from ..query import archive_feature

        (tmp_path / ".vault" / "adr").mkdir(parents=True)

        with pytest.raises(VaultSpecError, match="feature tag is required"):
            archive_feature(tmp_path, empty_tag)

    def test_archive_preserves_subdir_structure(self, tmp_path):
        """Archived docs maintain their type subdirectory."""
        from ..query import archive_feature

        # Create docs in different type dirs
        for dtype in ("adr", "plan"):
            d = tmp_path / ".vault" / dtype
            d.mkdir(parents=True)
            f = d / f"2026-03-16-my-feat-{dtype}.md"
            content = (
                f"---\ntags:\n  - {dtype}\n  - my-feat\n"
                f"date: 2026-03-16\n---\nContent.\n"
            )
            f.write_text(content, encoding="utf-8")

        result = archive_feature(tmp_path, "my-feat")
        assert result["archived_count"] == 2
        archive = tmp_path / ".vault" / "_archive"
        assert (archive / "adr" / "2026-03-16-my-feat-adr.md").exists()
        assert (archive / "plan" / "2026-03-16-my-feat-plan.md").exists()


class TestDocsFromGraph:
    """``_docs_from_graph`` must be byte-for-byte equivalent to the
    ``list_documents``/``_scan_all`` disk-scanning path it replaces inside
    ``get_stats``/``collect_all_statuses``."""

    def _graph(self, root):
        from ...graph import VaultGraph

        return VaultGraph(root)

    def test_matches_list_documents_unfiltered(self, vault_project: CorpusManifest):
        via_scan = list_documents(vault_project.root)
        via_graph = _docs_from_graph(self._graph(vault_project.root))

        def key(d: VaultDocument) -> str:
            return str(d.path)

        via_scan_sorted = sorted(via_scan, key=key)
        via_graph_sorted = sorted(via_graph, key=key)
        assert len(via_scan_sorted) == len(via_graph_sorted)
        for a, b in zip(via_scan_sorted, via_graph_sorted, strict=True):
            assert a.path == b.path
            assert a.name == b.name
            assert a.doc_type == b.doc_type
            assert a.feature == b.feature
            assert a.date == b.date
            assert a.tags == b.tags

    def test_matches_list_documents_with_doc_type_filter(
        self, vault_project: CorpusManifest
    ):
        via_scan = list_documents(vault_project.root, doc_type="adr")
        via_graph = _docs_from_graph(self._graph(vault_project.root), doc_type="adr")

        assert {str(d.path) for d in via_scan} == {str(d.path) for d in via_graph}
        assert via_graph
        assert all(d.doc_type == "adr" for d in via_graph)

    def test_matches_list_documents_with_feature_filter(
        self, vault_project: CorpusManifest
    ):
        docs = list_documents(vault_project.root)
        feature = next(d.feature for d in docs if d.feature)

        via_scan = list_documents(vault_project.root, feature=feature)
        via_graph = _docs_from_graph(self._graph(vault_project.root), feature=feature)

        assert {str(d.path) for d in via_scan} == {str(d.path) for d in via_graph}
        assert via_graph
        assert all(d.feature == feature for d in via_graph)

    def test_matches_list_documents_with_date_filter(
        self, vault_project: CorpusManifest
    ):
        docs = list_documents(vault_project.root)
        date = next(d.date for d in docs if d.date)

        via_scan = list_documents(vault_project.root, date=date)
        via_graph = _docs_from_graph(self._graph(vault_project.root), date=date)

        assert {str(d.path) for d in via_scan} == {str(d.path) for d in via_graph}
        assert via_graph
        assert all(d.date == date for d in via_graph)

    def test_skips_phantom_nodes_from_dangling_links(self, tmp_path):
        """A dangling wiki-link creates a phantom node (``path=None``); the
        adapter must never crash on it or count it as a real document."""
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "2026-04-01-broken-link-adr.md").write_text(
            "---\ntags:\n  - '#adr'\n  - '#broken-link'\ndate: '2026-04-01'\n"
            "related:\n  - '[[nonexistent-target-xyz]]'\n---\n\nBody.\n",
            encoding="utf-8",
        )

        graph = self._graph(tmp_path)
        assert any(n.phantom for n in graph.nodes.values()), (
            "fixture must actually produce a phantom node"
        )

        docs = _docs_from_graph(graph)
        assert len(docs) == 1
        assert docs[0].name == "2026-04-01-broken-link-adr"

    def test_stem_collision_name_uses_bare_stem(self, tmp_path):
        """A stem collision re-keys the graph node's ``name`` as
        ``doctype/stem``; the adapter must derive the document ``name``
        from ``node.path.stem`` instead, matching ``VaultDocument.name``."""
        stem = "2026-04-02-collide-x"
        for dtype in ("adr", "plan"):
            d = tmp_path / ".vault" / dtype
            d.mkdir(parents=True)
            (d / f"{stem}.md").write_text(
                f"---\ntags:\n  - '#{dtype}'\n  - '#collide-feat'\n"
                "date: '2026-04-02'\n---\n\nBody.\n",
                encoding="utf-8",
            )

        graph = self._graph(tmp_path)
        assert any(len(v) > 1 for v in graph._stem_index.values()), (
            "fixture must actually produce a stem collision"
        )

        docs = _docs_from_graph(graph)
        names = {d.name for d in docs}
        assert names == {stem}, (
            f"expected the bare stem {stem!r} for both documents, got {names}"
        )
        assert len(docs) == 2

    def test_bare_feature_field_fallback(self, tmp_path):
        """A document with no non-directory tag but a bare top-level
        ``feature:`` key must resolve the same feature via both paths."""
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "2026-04-03-bare-feature-adr.md").write_text(
            "---\ntags:\n  - '#adr'\nfeature: 'legacy-widget'\n"
            "date: '2026-04-03'\n---\n\nBody.\n",
            encoding="utf-8",
        )

        via_scan = list_documents(tmp_path)
        via_graph = _docs_from_graph(self._graph(tmp_path))

        assert len(via_scan) == 1
        assert len(via_graph) == 1
        assert via_scan[0].feature == "legacy-widget"
        assert via_graph[0].feature == "legacy-widget"

    def test_filename_date_fallback(self, tmp_path):
        """A document with no frontmatter ``date:`` key still resolves its
        date from the dated filename prefix, identically via both paths."""
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "2026-04-04-no-date-field-adr.md").write_text(
            "---\ntags:\n  - '#adr'\n  - '#no-date-field'\n---\n\nBody.\n",
            encoding="utf-8",
        )

        via_scan = list_documents(tmp_path)
        via_graph = _docs_from_graph(self._graph(tmp_path))

        assert len(via_scan) == 1
        assert len(via_graph) == 1
        assert via_scan[0].date == "2026-04-04"
        assert via_graph[0].date == "2026-04-04"


class TestGetStatsGraphPath:
    """``get_stats`` now reads the graph by default; its totals must still
    match an independent ``list_documents``-based computation."""

    def test_totals_match_list_documents(self, vault_project: CorpusManifest):
        docs = list_documents(vault_project.root)
        stats = get_stats(vault_project.root)

        counts: dict[str, int] = {}
        features: set[str] = set()
        for d in docs:
            counts[d.doc_type] = counts.get(d.doc_type, 0) + 1
            if d.feature:
                features.add(d.feature)

        assert stats["total_docs"] == len(docs)
        assert stats["counts_by_type"] == counts
        assert stats["total_features"] == len(features)

    def test_explicit_graph_matches_implicit_build(self, vault_project: CorpusManifest):
        from ...graph import VaultGraph

        graph = VaultGraph(vault_project.root)
        assert get_stats(vault_project.root, graph=graph) == get_stats(
            vault_project.root
        )

    def test_orphaned_pseudo_type_still_works_with_graph_present(
        self, vault_project: CorpusManifest
    ):
        from ...graph import VaultGraph

        graph = VaultGraph(vault_project.root)
        stats = get_stats(vault_project.root, doc_type="orphaned", graph=graph)
        assert "total_docs" in stats


class TestListDocumentsGraphParity:
    """``list_documents`` reads from the graph but must answer identically.

    The graph-backed listing reuses frontmatter the ingress read already
    parsed instead of reading and parsing every document a second time. It
    is only a safe substitution if it returns exactly what the disk scan
    returns, for every filter shape.
    """

    @staticmethod
    def _key(docs: list[VaultDocument]) -> list[tuple]:
        return sorted((d.name, d.doc_type, d.feature, d.date) for d in docs)

    @pytest.mark.parametrize(
        "doc_type", [None, "adr", "plan", "exec", "research", "reference"]
    )
    def test_graph_listing_matches_disk_scan(
        self, vault_project: CorpusManifest, doc_type: str | None
    ) -> None:
        from ..query import _scan_all

        via_graph = list_documents(vault_project.root, doc_type=doc_type)
        via_disk = _scan_all(vault_project.root, doc_type=doc_type)

        assert self._key(via_graph) == self._key(via_disk)

    def test_feature_and_date_filters_match_disk_scan(
        self, vault_project: CorpusManifest
    ) -> None:
        from ..query import _scan_all

        all_disk = _scan_all(vault_project.root)
        feature = next((d.feature for d in all_disk if d.feature), None)
        date = next((d.date for d in all_disk if d.date), None)
        assert feature is not None and date is not None

        by_feature = list_documents(vault_project.root, feature=feature)
        by_date = list_documents(vault_project.root, date=date)

        assert self._key(by_feature) == self._key(
            [d for d in all_disk if d.feature == feature]
        )
        assert self._key(by_date) == self._key([d for d in all_disk if d.date == date])

    def test_supplied_graph_matches_internally_built_one(
        self, vault_project: CorpusManifest
    ) -> None:
        from ...graph import VaultGraph

        graph = VaultGraph(vault_project.root)

        assert self._key(list_documents(vault_project.root, graph=graph)) == self._key(
            list_documents(vault_project.root)
        )

    def test_listing_reads_from_the_graph_not_the_corpus(
        self, vault_project: CorpusManifest
    ) -> None:
        """Proven by deleting the corpus: only a graph-backed read survives.

        No patching - the documents are removed from disk after the graph is
        built, so any fallback to a disk rescan returns nothing and fails.
        """
        import shutil

        from ...graph import VaultGraph

        graph = VaultGraph(vault_project.root)
        expected = self._key(list_documents(vault_project.root, graph=graph))
        assert expected, "fixture produced no documents to assert on"

        shutil.rmtree(vault_project.root / ".vault")

        assert self._key(list_documents(vault_project.root, graph=graph)) == expected
