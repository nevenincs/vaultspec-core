"""Shared fixtures for graph tests.

Resets configuration state and provides a synthetic vault corpus for
relationship analysis.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from ...config import reset_config
from ...testing.synthetic import CorpusManifest, build_synthetic_vault
from ..api import VaultGraph


def stem_index_of(graph: VaultGraph) -> dict[str, list[str]]:
    """Rebuild ``VaultGraph``'s internal stem index from public node data.

    ``_stem_index`` maps each document's bare stem to the sorted list of
    non-phantom node keys sharing it (a single-entry list for a unique stem,
    several qualified ``type/stem`` keys for a collision). Both build paths
    (:meth:`VaultGraph._assemble_from_by_stem` and
    :meth:`VaultGraph._load_from_cache`) derive this purely from each
    non-phantom node's key, so grouping :attr:`VaultGraph.nodes` by bare stem
    here reproduces the same mapping without reaching into the private
    attribute.
    """
    by_stem: dict[str, list[str]] = {}
    for key, node in graph.nodes.items():
        if node.phantom:
            continue
        bare_stem = key.split("/", 1)[1] if "/" in key else key
        by_stem.setdefault(bare_stem, []).append(key)
    return {stem: sorted(keys) for stem, keys in by_stem.items()}


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture(scope="session")
def graph_manifest(tmp_path_factory: pytest.TempPathFactory) -> CorpusManifest:
    """Session-scoped synthetic vault for graph tests.

    Built with four feature names so literal feature assertions pass,
    two named docs so stem-based node lookups resolve, and four
    pathology presets to cover stem-collision and phantom-link tests.

    seed=9 ensures named docs have non-zero in/out edges so
    ``test_out_links_populated`` and ``test_in_links_populated`` pass.
    """
    root = tmp_path_factory.mktemp("graph_vault")
    return build_synthetic_vault(
        root,
        n_docs=120,
        seed=9,
        feature_names=[
            "editor-demo",
            "displaymap-integration",
            "alpha-engine",
            "beta-pipeline",
        ],
        named_docs={
            "editor_demo_adr": "2026-02-05-editor-demo-architecture-adr",
            "editor_demo_research": "2026-02-05-editor-demo-research",
        },
        pathologies=["cycle", "orphan", "stem_collision", "phantom_only_links"],
        edge_probability=0.3,
    )


@pytest.fixture(scope="session")
def vault_root(graph_manifest: CorpusManifest) -> Path:
    """Return the synthetic vault project root for graph testing."""
    return graph_manifest.root
