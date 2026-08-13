"""Tests for the feature index generator."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...graph.api import DocNode
from ..index import feature_index_lock_target, generate_feature_index_result
from ..models import DocType

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
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


def _gen(tmp_path: Path, feat: str, nodes: list[DocNode]) -> Path:
    return generate_feature_index_result(
        tmp_path, feat, nodes=nodes, date_str="2026-03-23"
    ).path


class TestGenerateFeatureIndex:
    def test_creates_index_file(self, tmp_path: Path) -> None:
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
            _node(tmp_path, "d2", "adr", "f", "2026-03-02", "A"),
        ]
        path = _gen(tmp_path, "f", nodes)
        assert path.exists()
        assert path.name == "f.index.md"

    def test_index_lives_in_index_subfolder(self, tmp_path: Path) -> None:
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
        ]
        path = _gen(tmp_path, "f", nodes)
        assert path.parent == tmp_path / ".vault" / "index"
        assert path.parent.is_dir()

    def test_index_has_correct_frontmatter(self, tmp_path: Path) -> None:
        nodes = [
            _node(tmp_path, "d1", "research", "f", "2026-03-01", "R"),
        ]
        path = _gen(tmp_path, "f", nodes)
        content = path.read_text(encoding="utf-8")
        assert "generated: true" in content
        assert "'#f'" in content
        assert "2026-03-23" in content

    def test_index_carries_index_directory_tag(self, tmp_path: Path) -> None:
        nodes = [
            _node(tmp_path, "x", "adr", "my-feat", "2026-03-01", "X"),
        ]
        path = _gen(tmp_path, "my-feat", nodes)
        content = path.read_text(encoding="utf-8")
        assert "'#index'" in content
        assert "'#my-feat'" in content
        # Frontmatter contains exactly two #-prefixed tag lines: #index and #<feature>
        assert content.count("  - '#") == 2

    def test_related_contains_all_feature_docs(self, tmp_path: Path) -> None:
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

    def test_body_groups_by_type(self, tmp_path: Path) -> None:
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

    def test_idempotent_update(self, tmp_path: Path) -> None:
        nodes = [
            _node(tmp_path, "a", "research", "f", "2026-03-01", "A"),
        ]
        p1 = _gen(tmp_path, "f", nodes)
        c1 = p1.read_text(encoding="utf-8")

        p2 = _gen(tmp_path, "f", nodes)
        c2 = p2.read_text(encoding="utf-8")

        assert p1 == p2
        assert c1 == c2

    def test_unchanged_body_preserves_creation_and_modified_dates(
        self, tmp_path: Path
    ) -> None:
        """A date rollover does not dirty an index whose body is unchanged."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-23"
        ).path
        before = path.read_bytes()

        result = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-24"
        )

        assert result.changed is False
        assert path.read_bytes() == before
        assert b"date: '2026-03-23'" in before
        assert b"modified: '2026-03-23'" in before

    def test_unchanged_body_repairs_a_stale_attestation(self, tmp_path: Path) -> None:
        """A no-op is allowed only when the existing body hash is truthful."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-23"
        ).path
        stale = path.read_text(encoding="utf-8").replace(
            "body_hash: 'sha256:", "body_hash: 'sha256:stale-"
        )
        path.write_text(stale, encoding="utf-8")

        generate_feature_index_result(tmp_path, "f", nodes=nodes, date_str="2026-03-24")

        repaired = path.read_text(encoding="utf-8")
        assert "sha256:stale-" not in repaired
        assert "date: '2026-03-23'" in repaired
        assert "modified: '2026-03-24'" in repaired

    def test_read_error_propagates_without_replacement(self, tmp_path: Path) -> None:
        """An unreadable existing target is not treated as a missing index."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        target = tmp_path / ".vault" / "index" / "f.index.md"
        target.mkdir(parents=True)

        with pytest.raises(OSError):
            generate_feature_index_result(
                tmp_path, "f", nodes=nodes, date_str="2026-03-24"
            )

        assert target.is_dir()

    def test_changed_body_preserves_creation_date_and_refreshes_modified(
        self, tmp_path: Path
    ) -> None:
        """Membership changes advance modified without rewriting creation date."""
        first = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = generate_feature_index_result(
            tmp_path, "f", nodes=first, date_str="2026-03-23"
        ).path
        second = [*first, _node(tmp_path, "b", "adr", "f", "2026-03-02", "B")]

        result = generate_feature_index_result(
            tmp_path, "f", nodes=second, date_str="2026-03-24"
        )

        content = path.read_text(encoding="utf-8")
        assert result.changed is True
        assert "date: '2026-03-23'" in content
        assert "modified: '2026-03-24'" in content
        assert "[[b]]" in content

    @pytest.mark.parametrize(
        "mutation",
        [
            ("generated: true", "generated: false"),
            ("  - '#index'", "  - '#audit'"),
            ("related:\n  - '[[a]]'", "related: []"),
            ("body_hash:", "body_hash: 'sha256:forged'\nbody_hash:"),
        ],
    )
    def test_metadata_drift_forces_canonical_rewrite(
        self, tmp_path: Path, mutation: tuple[str, str]
    ) -> None:
        """A truthful body hash never blesses noncanonical generated metadata."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = _gen(tmp_path, "f", nodes)
        before, after = mutation
        path.write_text(
            path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8"
        )

        result = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-24"
        )

        content = path.read_text(encoding="utf-8")
        assert result.changed is True
        assert "generated: true" in content
        assert "  - '#index'" in content
        assert "related:\n  - '[[a]]'" in content
        assert content.count("body_hash:") == 1

    @pytest.mark.parametrize("frontmatter", ["- one\n- two", "hello"])
    def test_non_mapping_frontmatter_is_repaired(
        self, tmp_path: Path, frontmatter: str
    ) -> None:
        """Valid YAML scalars and lists do not crash index regeneration."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = _gen(tmp_path, "f", nodes)
        _, body = path.read_text(encoding="utf-8").split("---\n", 2)[1:]
        path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")

        result = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-24"
        )

        assert result.changed is True
        assert "generated: true" in path.read_text(encoding="utf-8")

    def test_dry_run_reports_change_without_writing(self, tmp_path: Path) -> None:
        """Dry-run computes the physical outcome and leaves bytes untouched."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]
        path = _gen(tmp_path, "f", nodes)
        before = path.read_bytes()
        changed = [*nodes, _node(tmp_path, "b", "adr", "f", "2026-03-02", "B")]

        result = generate_feature_index_result(
            tmp_path, "f", nodes=changed, date_str="2026-03-24", dry_run=True
        )

        assert result.changed is True
        assert path.read_bytes() == before

    def test_fresh_dry_run_creates_no_files_or_directories(
        self, tmp_path: Path
    ) -> None:
        """Previewing an absent index is filesystem-pure."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]

        result = generate_feature_index_result(
            tmp_path, "f", nodes=nodes, date_str="2026-03-24", dry_run=True
        )

        assert result.changed is True
        assert not (tmp_path / ".vault").exists()

    def test_generation_uses_only_gitignored_lock_storage(self, tmp_path: Path) -> None:
        """Generation never leaves a sibling lock beside the tracked index."""
        nodes = [_node(tmp_path, "a", "research", "f", "2026-03-01", "A")]

        path = _gen(tmp_path, "f", nodes)

        assert not path.with_suffix(path.suffix + ".lock").exists()
        assert (tmp_path / ".vault" / "data" / "index" / "f.lock").exists()

    def test_membership_is_refreshed_after_acquiring_the_index_lock(
        self, tmp_path: Path
    ) -> None:
        """A waiting writer sees documents created before its lock is granted."""
        from vaultspec_core.core.helpers import advisory_lock

        def write_doc(name: str) -> None:
            path = tmp_path / ".vault" / "research" / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "---\n"
                "tags:\n"
                "  - '#research'\n"
                "  - '#f'\n"
                "date: '2026-03-23'\n"
                "related: []\n"
                "---\n\n"
                f"# {name}\n",
                encoding="utf-8",
            )

        write_doc("a")
        target = generate_feature_index_result(
            tmp_path, "f", date_str="2026-03-23"
        ).path
        errors: list[BaseException] = []

        def regenerate() -> None:
            try:
                generate_feature_index_result(tmp_path, "f", date_str="2026-03-24")
            except BaseException as exc:
                errors.append(exc)

        lock_target = feature_index_lock_target(tmp_path / ".vault", "f")
        with advisory_lock(lock_target):
            worker = threading.Thread(target=regenerate)
            worker.start()
            worker.join(timeout=0.1)
            assert worker.is_alive(), "writer did not block on the production lock"
            write_doc("b")
        worker.join(timeout=10)

        assert not worker.is_alive()
        assert errors == []
        content = target.read_text(encoding="utf-8")
        assert "[[a]]" in content
        assert "[[b]]" in content

    def test_update_reflects_new_docs(self, tmp_path: Path) -> None:
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

    def test_excludes_self_from_related(self, tmp_path: Path) -> None:
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
