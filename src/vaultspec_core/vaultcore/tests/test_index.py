"""Tests for the feature index generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...graph.api import DocNode
from ..index import generate_feature_index
from ..models import DocType

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


def _node(
    root: Path,
    name: str,
    dtype: str,
    feat: str,
    date: str,
    title: str,
) -> DocNode:
    return DocNode(
        path=root / ".vault" / dtype / f"{name}.md",
        name=name,
        doc_type=DocType(dtype),
        feature=feat,
        date=date,
        title=title,
        tags={f"#{dtype}", f"#{feat}"},
    )


def _gen(tmp_path, feat, nodes):
    return generate_feature_index(tmp_path, feat, nodes=nodes, date_str="2026-03-23")


class TestGenerateFeatureIndex:
    def test_creates_index_file(self, tmp_path):
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
            _node(tmp_path, "d2", "adr", "f", "2026-03-02", "A"),
        ]
        path = _gen(tmp_path, "f", nodes)
        assert path.exists()
        assert path.name == "f.index.md"

    def test_index_lives_in_index_subfolder(self, tmp_path):
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
        ]
        path = _gen(tmp_path, "f", nodes)
        assert path.parent == tmp_path / ".vault" / "index"
        assert path.parent.is_dir()

    def test_index_has_correct_frontmatter(self, tmp_path):
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
        ]
        path = _gen(tmp_path, "f", nodes)
        content = path.read_text(encoding="utf-8")
        assert "generated: true" in content
        assert "'#f'" in content
        assert "2026-03-23" in content

    def test_index_carries_index_directory_tag(self, tmp_path):
        nodes = [
            _node(tmp_path, "x", "adr", "my-feat", "2026-03-01", "X"),
        ]
        path = _gen(tmp_path, "my-feat", nodes)
        content = path.read_text(encoding="utf-8")
        assert "'#index'" in content
        assert "'#my-feat'" in content
        # Frontmatter contains exactly two #-prefixed tag lines: #index and #<feature>
        assert content.count("  - '#") == 2

    def test_related_contains_all_feature_docs(self, tmp_path):
        nodes = [
            _node(tmp_path, "a", "research", "f", "2026-03-01", "A"),
            _node(tmp_path, "b", "adr", "f", "2026-03-02", "B"),
            _node(tmp_path, "c", "plan", "f", "2026-03-03", "C"),
        ]
        path = _gen(tmp_path, "f", nodes)
        content = path.read_text(encoding="utf-8")
        assert "[[a]]" in content
        assert "[[b]]" in content
        assert "[[c]]" in content

    def test_body_groups_by_type(self, tmp_path):
        nodes = [
            _node(tmp_path, "a", "research", "f", "2026-03-01", "RA"),
            _node(tmp_path, "b", "adr", "f", "2026-03-02", "AB"),
        ]
        path = _gen(tmp_path, "f", nodes)
        content = path.read_text(encoding="utf-8")
        assert "### adr" in content
        assert "### research" in content
        assert "`a`" in content
        assert "`b`" in content

    def test_idempotent_update(self, tmp_path):
        nodes = [
            _node(tmp_path, "a", "research", "f", "2026-03-01", "A"),
        ]
        p1 = _gen(tmp_path, "f", nodes)
        c1 = p1.read_text(encoding="utf-8")

        p2 = _gen(tmp_path, "f", nodes)
        c2 = p2.read_text(encoding="utf-8")

        assert p1 == p2
        assert c1 == c2

    def test_update_reflects_new_docs(self, tmp_path):
        v1 = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        _gen(tmp_path, "f", v1)

        v2 = [
            *v1,
            _node(tmp_path, "b", "adr", "f", "2026-03-02", "B"),
        ]
        path = _gen(tmp_path, "f", v2)
        content = path.read_text(encoding="utf-8")
        assert "[[b]]" in content
        assert "### adr" in content

    def test_excludes_self_from_related(self, tmp_path):
        nodes = [
            _node(tmp_path, "a", "research", "f", "2026-03-01", "A"),
            DocNode(
                path=tmp_path / ".vault" / "f.index.md",
                name="f.index",
                feature="f",
            ),
        ]
        path = _gen(tmp_path, "f", nodes)
        content = path.read_text(encoding="utf-8")
        assert "[[f.index]]" not in content
        assert "[[a]]" in content
