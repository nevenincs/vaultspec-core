"""Tests for vault scanning and document type classification.

Covers :func:`~vaultspec_core.vaultcore.scanner.scan_vault` (file discovery,
``.obsidian`` exclusion) and :func:`~vaultspec_core.vaultcore.scanner.get_doc_type`
(directory-based classification) against a synthetic vault fixture.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from ...config import reset_config
from ...testing.synthetic import CorpusManifest, build_synthetic_vault
from .. import DocType, get_doc_type, scan_vault

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def vault_project(tmp_path: Path) -> CorpusManifest:
    return build_synthetic_vault(
        tmp_path,
        n_docs=24,
        seed=42,
        named_docs={
            "editor_demo_adr": "2026-02-05-editor-demo-architecture-adr",
            "editor_demo_plan": "2026-02-05-editor-demo-phase1-plan",
            "editor_demo_research": "2026-02-05-editor-demo-research",
            "editor_demo_reference": "2026-02-05-editor-demo-core-reference",
        },
    )


class TestScanVault:
    def test_yields_many_markdown_files(self, vault_project: CorpusManifest):
        paths = list(scan_vault(vault_project.root))
        # Anchor the lower bound to the generated corpus size: at least
        # one doc per requested doc count, so a regression that emits
        # only a handful of files would still trip this assertion.
        assert len(paths) >= len(vault_project.docs)

    def test_all_files_are_markdown(self, vault_project: CorpusManifest):
        for p in scan_vault(vault_project.root):
            assert p.suffix == ".md"

    def test_skips_obsidian(self, vault_project: CorpusManifest):
        # Create a .obsidian directory to verify it is excluded
        obsidian_dir = vault_project.root / ".vault" / ".obsidian"
        obsidian_dir.mkdir(parents=True)
        (obsidian_dir / "config.md").write_text("obsidian config", encoding="utf-8")
        for p in scan_vault(vault_project.root):
            assert ".obsidian" not in p.parts

    def test_includes_known_adr(self, vault_project: CorpusManifest):
        names = {p.name for p in scan_vault(vault_project.root)}
        assert "2026-02-05-editor-demo-architecture-adr.md" in names

    def test_includes_known_plan(self, vault_project: CorpusManifest):
        names = {p.name for p in scan_vault(vault_project.root)}
        assert "2026-02-05-editor-demo-phase1-plan.md" in names


class TestGetDocType:
    def test_adr_dir(self, vault_project: CorpusManifest):
        path = vault_project.named_docs["editor_demo_adr"].path
        assert get_doc_type(path, vault_project.root) == DocType.ADR

    def test_plan_dir(self, vault_project: CorpusManifest):
        path = vault_project.named_docs["editor_demo_plan"].path
        assert get_doc_type(path, vault_project.root) == DocType.PLAN

    def test_research_dir(self, vault_project: CorpusManifest):
        path = vault_project.named_docs["editor_demo_research"].path
        assert get_doc_type(path, vault_project.root) == DocType.RESEARCH

    def test_reference_dir(self, vault_project: CorpusManifest):
        path = vault_project.named_docs["editor_demo_reference"].path
        assert get_doc_type(path, vault_project.root) == DocType.REFERENCE

    def test_audit_dir_returns_audit(self, vault_project: CorpusManifest):
        audit_files = list((vault_project.root / ".vault" / "audit").glob("*.md"))
        assert audit_files, "Synthetic vault must produce at least one audit doc"
        assert get_doc_type(audit_files[0], vault_project.root) == DocType.AUDIT

    def test_index_subfolder_returns_index(self, vault_project: CorpusManifest):
        index_dir = vault_project.root / ".vault" / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        index_path = index_dir / "alpha-engine.index.md"
        index_path.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha-engine'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha-engine index\n",
            encoding="utf-8",
        )
        assert get_doc_type(index_path, vault_project.root) == DocType.INDEX

    def test_legacy_root_index_returns_index(self, vault_project: CorpusManifest):
        legacy_path = vault_project.root / ".vault" / "alpha-engine.index.md"
        legacy_path.write_text(
            "---\ngenerated: true\ntags:\n  - '#alpha-engine'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha-engine index\n",
            encoding="utf-8",
        )
        assert get_doc_type(legacy_path, vault_project.root) == DocType.INDEX


class TestDocTypeResolver:
    """The memoizing resolver must answer exactly what ``get_doc_type`` does.

    A document's type is decided by its first path component under the docs
    directory, so the answer can be reused for every file in a directory.
    Whole-snapshot loops called ``get_doc_type`` per document instead - 4,739
    calls per check pass, each a ``relative_to`` and a tuple walk.

    The case the directory does *not* decide is a legacy root-level
    ``<feature>.index.md`` sitting directly in the docs directory, where the
    filename classifies it and its neighbours may not be index files at all.
    Caching by directory there would misclassify them, so those are resolved
    individually. These tests pin both halves of that.
    """

    @staticmethod
    def _docs_dir(root: Path) -> Path:
        from ...config import get_config

        return root / get_config().docs_dir

    def test_it_agrees_with_get_doc_type_for_every_scanned_file(
        self, vault_project: CorpusManifest
    ) -> None:
        from ..scanner import doc_type_resolver

        root = vault_project.root
        resolve = doc_type_resolver(root)
        paths = list(scan_vault(root))

        assert paths, "the fixture produced no documents"
        for path in paths:
            assert resolve(path) == get_doc_type(path, root), (
                f"resolver disagreed with get_doc_type for {path}"
            )

    def test_a_root_level_legacy_index_is_not_cached_by_its_directory(
        self, vault_project: CorpusManifest
    ) -> None:
        """Two files in the docs directory, only one an index, must differ.

        Caching the docs directory itself would give whichever file was seen
        first the other's classification.
        """
        from ..scanner import doc_type_resolver

        root = vault_project.root
        docs_dir = self._docs_dir(root)

        legacy_index = docs_dir / "legacy-feature.index.md"
        legacy_index.write_text("# legacy index" + chr(10), encoding="utf-8")
        stray = docs_dir / "README.md"
        stray.write_text("# not an index" + chr(10), encoding="utf-8")

        # Resolve the non-index first, so a directory-keyed cache would have
        # stored None before the index file is ever asked about.
        resolve = doc_type_resolver(root)
        assert resolve(stray) == get_doc_type(stray, root)
        assert resolve(legacy_index) == DocType.INDEX

        # And in the other order, on a fresh resolver.
        resolve_again = doc_type_resolver(root)
        assert resolve_again(legacy_index) == DocType.INDEX
        assert resolve_again(stray) == get_doc_type(stray, root)

    def test_repeated_calls_in_one_directory_stay_correct(
        self, vault_project: CorpusManifest
    ) -> None:
        """The cached answer must be the answer, not merely the first one."""
        from ..scanner import doc_type_resolver

        root = vault_project.root
        adr_dir = self._docs_dir(root) / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        made: list[Path] = []
        for n in range(3):
            path = adr_dir / f"2026-05-0{n + 1}-cached-{n}-adr.md"
            path.write_text("# adr" + chr(10), encoding="utf-8")
            made.append(path)

        resolve = doc_type_resolver(root)

        assert [resolve(path) for path in made] == [DocType.ADR] * 3


class TestScanVaultWalk:
    """The scan prunes non-corpus subtrees and reports a defined order.

    ``Path.rglob`` walked every excluded subtree and then filtered its
    results, and pathlib's per-entry generator machinery cost 0.66 s of pure
    Python on a 4,739-document vault. ``os.walk`` prunes the excluded
    directories before descending, which also means the 504 archived
    documents are never looked at. Measured 0.227 s -> 0.102 s.
    """

    @staticmethod
    def _docs_dir(root: Path) -> Path:
        from ...config import get_config

        return root / get_config().docs_dir

    def test_every_excluded_subtree_is_pruned(
        self, vault_project: CorpusManifest
    ) -> None:
        from ..exclusions import EXCLUDED_VAULT_DIR_NAMES

        root = vault_project.root
        docs_dir = self._docs_dir(root)

        planted: list[Path] = []
        for name in sorted(EXCLUDED_VAULT_DIR_NAMES):
            subtree = docs_dir / name / "nested"
            subtree.mkdir(parents=True, exist_ok=True)
            decoy = subtree / "2026-08-01-decoy-research.md"
            decoy.write_text("# decoy", encoding="utf-8")
            planted.append(decoy)

        found = set(scan_vault(root))

        assert planted, "no excluded directories were exercised"
        for decoy in planted:
            assert decoy not in found, f"{decoy} leaked into the corpus"

    def test_the_order_is_sorted_and_repeatable(
        self, vault_project: CorpusManifest
    ) -> None:
        root = vault_project.root

        first = list(scan_vault(root))
        second = list(scan_vault(root))

        assert first == second
        assert first == sorted(first)

    def test_a_missing_docs_directory_yields_nothing(self, tmp_path: Path) -> None:
        empty = tmp_path / "no-vault"
        empty.mkdir()

        assert list(scan_vault(empty)) == []

    def test_only_markdown_is_reported(self, vault_project: CorpusManifest) -> None:
        root = vault_project.root
        stray = self._docs_dir(root) / "adr" / "notes.txt"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("not markdown", encoding="utf-8")

        found = list(scan_vault(root))

        assert stray not in found
        assert all(p.suffix == ".md" for p in found)
