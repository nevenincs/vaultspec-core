"""Real-filesystem tests for the ``rename_feature`` backend.

Exercises ``vaultspec_core.vaultcore.query.rename_feature`` against real
on-disk vaults built with schema-valid documents: every guard, the dry-run
preview, the happy-path multi-surface rewrite, exec folder and record
renames, cross-feature incoming-link rewrites, the reverse-journal rollback
on an induced mid-apply failure, force-merge and per-file collision refusal,
and flow-style tag normalization with index regeneration.

No test doubles are used. Failures are induced through the real filesystem
(a directory planted at a computed destination), and every assertion reads
real bytes, real parsed frontmatter, or the real regenerated index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...core.exceptions import VaultSpecError
from ...graph import VaultGraph
from ..index import generate_feature_index
from ..parser import parse_frontmatter
from ..query import list_documents, rename_feature

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-06-26"


@pytest.fixture(autouse=True)
def _reset_cfg():
    """Reset the process-global config to defaults around every test."""
    reset_config()
    yield
    reset_config()


# ---------------------------------------------------------------------------
# Document builders (schema-valid, annotation-free, placeholder-free).
# ---------------------------------------------------------------------------


def _frontmatter(
    tags: list[str],
    date: str,
    related: list[str],
    *,
    flow_tags: bool,
    extra_fm: str,
) -> str:
    if flow_tags:
        joined = ", ".join(f"'{t}'" for t in tags)
        tags_block = f"tags: [{joined}]\n"
    else:
        tags_block = "tags:\n" + "".join(f"  - '{t}'\n" for t in tags)
    if related:
        rel_block = "related:\n" + "".join(f"  - '[[{r}]]'\n" for r in related)
    else:
        rel_block = "related: []\n"
    return (
        f"---\n{tags_block}date: '{date}'\nmodified: '{date}'\n"
        f"{extra_fm}{rel_block}---\n"
    )


def _authored_doc(
    root: Path,
    doc_type: str,
    feature: str,
    *,
    date: str = DATE,
    related: list[str] | None = None,
    body: str | None = None,
    flow_tags: bool = False,
    extra_fm: str = "",
    topic: str | None = None,
) -> Path:
    """Write one authored vault document and return its path."""
    infix = f"-{topic}" if topic else ""
    name = f"{date}-{feature}{infix}-{doc_type}.md"
    path = root / ".vault" / doc_type / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = _frontmatter(
        [f"#{doc_type}", f"#{feature}"],
        date,
        related or [],
        flow_tags=flow_tags,
        extra_fm=extra_fm,
    )
    if body is None:
        body = f"# {feature} {doc_type}\n\nDocument body for {feature}.\n"
    path.write_text(f"{fm}\n{body}", encoding="utf-8")
    return path


def _exec_record(
    root: Path,
    feature: str,
    *,
    plan_date: str,
    suffix: str,
    related: list[str] | None = None,
    extra_fm: str = "",
) -> Path:
    """Write one exec record inside ``.vault/exec/{plan_date}-{feature}/``."""
    folder = root / ".vault" / "exec" / f"{plan_date}-{feature}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{plan_date}-{feature}-{suffix}.md"
    fm = _frontmatter(
        ["#exec", f"#{feature}"],
        plan_date,
        related or [],
        flow_tags=False,
        extra_fm=extra_fm,
    )
    body = f"# {feature} exec {suffix}\n\nExecution record body.\n"
    path.write_text(f"{fm}\n{body}", encoding="utf-8")
    return path


def _build_index(root: Path, feature: str) -> Path:
    """Generate a real feature index from a freshly-built graph."""
    graph = VaultGraph(root, use_cache=False)
    nodes = graph.get_feature_nodes(feature)
    return generate_feature_index(root, feature, nodes=nodes)


def _snapshot_md(root: Path) -> dict[Path, bytes]:
    """Snapshot the bytes of every ``.md`` document under ``.vault``.

    The auxiliary graph cache under ``.vault/data/`` is not a document and
    is excluded from the document scan, so it never appears here.
    """
    vault = root / ".vault"
    return {p: p.read_bytes() for p in vault.rglob("*.md") if p.is_file()}


# ---------------------------------------------------------------------------
# S13 - validation guards
# ---------------------------------------------------------------------------


class TestValidationGuards:
    def test_empty_source_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "real-feature")
        with pytest.raises(VaultSpecError, match="source feature tag is required"):
            rename_feature(tmp_path, "", "new-feature")

    def test_empty_target_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "real-feature")
        with pytest.raises(VaultSpecError, match="target feature tag is required"):
            rename_feature(tmp_path, "real-feature", "  #  ")

    def test_identical_source_target_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "same-feature")
        with pytest.raises(VaultSpecError, match="identical"):
            rename_feature(tmp_path, "same-feature", "same-feature")

    def test_non_kebab_target_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "old-feature")
        with pytest.raises(VaultSpecError, match="not a valid feature tag"):
            rename_feature(tmp_path, "old-feature", "Bad_Name")

    def test_reserved_doctype_target_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "old-feature")
        with pytest.raises(VaultSpecError, match="reserved document-type name"):
            rename_feature(tmp_path, "old-feature", "adr")

    def test_missing_source_refuses(self, tmp_path: Path):
        # A vault with a different feature; the source matches nothing.
        _authored_doc(tmp_path, "research", "present-feature")
        with pytest.raises(VaultSpecError, match="matches zero documents"):
            rename_feature(tmp_path, "ghost-feature", "new-feature")

    def test_collision_without_force_refuses(self, tmp_path: Path):
        _authored_doc(tmp_path, "research", "source-feature")
        _authored_doc(tmp_path, "adr", "target-feature")
        with pytest.raises(VaultSpecError, match="already has 1 document"):
            rename_feature(tmp_path, "source-feature", "target-feature")


# ---------------------------------------------------------------------------
# S14 - dry-run
# ---------------------------------------------------------------------------


class TestDryRun:
    def _build(self, root: Path) -> None:
        _authored_doc(root, "research", "widget-engine")
        _authored_doc(
            root, "adr", "widget-engine", related=[f"{DATE}-widget-engine-research"]
        )
        _authored_doc(
            root,
            "plan",
            "widget-engine",
            related=[f"{DATE}-widget-engine-adr"],
            extra_fm="tier: L2\n",
        )
        _build_index(root, "widget-engine")

    def test_dry_run_returns_full_plan(self, tmp_path: Path):
        self._build(tmp_path)
        plan = rename_feature(tmp_path, "widget-engine", "gadget-engine", dry_run=True)

        assert plan["dry_run"] is True
        assert plan["status"] == "unchanged"
        assert plan["old"] == "widget-engine"
        assert plan["new"] == "gadget-engine"
        # Three authored docs (research, adr, plan); the index is tracked
        # separately under the index key, not in renamed_count.
        assert plan["renamed_count"] == 3
        assert len(plan["paths"]) == 3
        for entry in plan["paths"]:
            assert "widget-engine" in entry["old"]
            assert "gadget-engine" in entry["new"]
        # Predicted tag rewrites: one per renamed authored doc.
        assert plan["tag_rewrites"] == 3
        # related: links from adr->research and plan->adr are predicted.
        assert plan["related_rewrites"] >= 2
        assert plan["index"]["old"].endswith("widget-engine.index.md")
        assert plan["index"]["new"].endswith("gadget-engine.index.md")
        assert plan["collisions"] == []
        # The full set of structural keys is present.
        assert set(plan) >= {
            "old",
            "new",
            "renamed_count",
            "paths",
            "exec_folders",
            "tag_rewrites",
            "related_rewrites",
            "link_renames",
            "index",
            "cross_links",
            "collisions",
            "dry_run",
            "status",
        }

    def test_dry_run_mutates_nothing(self, tmp_path: Path):
        self._build(tmp_path)
        before = _snapshot_md(tmp_path)

        rename_feature(tmp_path, "widget-engine", "gadget-engine", dry_run=True)

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before), "dry-run must not add or remove any document"
        for path, original in before.items():
            assert after[path] == original, f"dry-run mutated {path.name}"


# ---------------------------------------------------------------------------
# S15 - happy-path multi-surface rewrite
# ---------------------------------------------------------------------------


class TestHappyPath:
    OLD = "widget-engine"
    NEW = "gadget-engine"
    BODY_MENTION = "The widget-engine subsystem coordinates downstream work."

    def _build(self, root: Path) -> None:
        _authored_doc(
            root,
            "research",
            self.OLD,
            body=f"# research\n\n{self.BODY_MENTION}\n",
        )
        _authored_doc(
            root,
            "adr",
            self.OLD,
            related=[f"{DATE}-{self.OLD}-research"],
            body=f"# adr\n\n{self.BODY_MENTION}\n",
        )
        _authored_doc(
            root,
            "plan",
            self.OLD,
            related=[f"{DATE}-{self.OLD}-adr", f"{DATE}-{self.OLD}-research"],
            extra_fm="tier: L2\n",
        )
        # Audit with a narrative topic infix.
        _authored_doc(
            root,
            "audit",
            self.OLD,
            topic="perf",
            related=[f"{DATE}-{self.OLD}-plan"],
        )

    def test_happy_path_filenames_swapped(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        vault = tmp_path / ".vault"
        old_names = {
            f"{DATE}-{self.OLD}-research.md",
            f"{DATE}-{self.OLD}-adr.md",
            f"{DATE}-{self.OLD}-plan.md",
            f"{DATE}-{self.OLD}-perf-audit.md",
        }
        new_names = {
            f"{DATE}-{self.NEW}-research.md",
            f"{DATE}-{self.NEW}-adr.md",
            f"{DATE}-{self.NEW}-plan.md",
            f"{DATE}-{self.NEW}-perf-audit.md",
        }
        on_disk = {p.name for p in vault.rglob("*.md") if p.is_file()}
        assert old_names.isdisjoint(on_disk), "old filenames must be gone"
        assert new_names <= on_disk, "every new filename must exist"

    def test_happy_path_feature_tag_rewritten(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        for doc in list_documents(tmp_path, feature=self.NEW):
            meta, _ = parse_frontmatter(doc.path.read_text(encoding="utf-8"))
            tags = meta.get("tags", [])
            assert f"#{self.NEW}" in tags, f"{doc.path.name} missing #{self.NEW}"
            assert f"#{self.OLD}" not in tags, f"{doc.path.name} still has #{self.OLD}"
        # And the old feature now matches zero documents.
        assert list_documents(tmp_path, feature=self.OLD) == []

    def test_happy_path_related_links_repointed(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        adr_path = tmp_path / ".vault" / "adr" / f"{DATE}-{self.NEW}-adr.md"
        meta, _ = parse_frontmatter(adr_path.read_text(encoding="utf-8"))
        related = meta.get("related", [])
        assert f"[[{DATE}-{self.NEW}-research]]" in related
        assert all(self.OLD not in str(r) for r in related)

    def test_happy_path_body_prose_unchanged(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        # The body mention of the old feature name must survive verbatim:
        # rename touches frontmatter and filenames only, never free prose.
        research_path = (
            tmp_path / ".vault" / "research" / f"{DATE}-{self.NEW}-research.md"
        )
        text = research_path.read_text(encoding="utf-8")
        _frontmatter_part, _, body_part = text.partition("\n---\n")
        assert self.BODY_MENTION in body_part
        assert "widget-engine" in body_part


# ---------------------------------------------------------------------------
# S16 - exec folder and exec records
# ---------------------------------------------------------------------------


class TestExecRename:
    OLD = "widget-engine"
    NEW = "gadget-engine"
    # The exec folder's plan-date is intentionally distinct from the
    # authored documents' date so the test proves the prefix is preserved
    # verbatim rather than recomputed.
    PLAN_DATE = "2026-05-01"

    def _build(self, root: Path) -> None:
        _authored_doc(
            root, "plan", self.OLD, date=self.PLAN_DATE, extra_fm="tier: L2\n"
        )
        _exec_record(
            root,
            self.OLD,
            plan_date=self.PLAN_DATE,
            suffix="P01-S01",
            related=[f"{self.PLAN_DATE}-{self.OLD}-plan"],
            extra_fm="step_id: 'S01'\n",
        )
        _exec_record(
            root,
            self.OLD,
            plan_date=self.PLAN_DATE,
            suffix="P01-summary",
            related=[f"{self.PLAN_DATE}-{self.OLD}-plan"],
        )

    def test_exec_folder_renamed_preserves_plan_date(self, tmp_path: Path):
        self._build(tmp_path)
        result = rename_feature(tmp_path, self.OLD, self.NEW)

        old_folder = tmp_path / ".vault" / "exec" / f"{self.PLAN_DATE}-{self.OLD}"
        new_folder = tmp_path / ".vault" / "exec" / f"{self.PLAN_DATE}-{self.NEW}"
        assert not old_folder.exists(), "old exec folder must be gone"
        assert new_folder.is_dir(), "new exec folder must exist with preserved date"
        assert result["exec_folders"] == [
            {
                "old": str(old_folder.relative_to(tmp_path)),
                "new": str(new_folder.relative_to(tmp_path)),
            }
        ]

    def test_exec_records_renamed(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        new_folder = tmp_path / ".vault" / "exec" / f"{self.PLAN_DATE}-{self.NEW}"
        step = new_folder / f"{self.PLAN_DATE}-{self.NEW}-P01-S01.md"
        summary = new_folder / f"{self.PLAN_DATE}-{self.NEW}-P01-summary.md"
        assert step.is_file()
        assert summary.is_file()
        # Old record names must not survive.
        survivors = {p.name for p in new_folder.glob("*.md")}
        assert f"{self.PLAN_DATE}-{self.OLD}-P01-S01.md" not in survivors
        # The step record's feature tag was rewritten too.
        meta, _ = parse_frontmatter(step.read_text(encoding="utf-8"))
        assert f"#{self.NEW}" in meta.get("tags", [])


# ---------------------------------------------------------------------------
# S17 - cross-feature incoming links
# ---------------------------------------------------------------------------


class TestCrossFeatureLinks:
    OLD = "widget-engine"
    NEW = "gadget-engine"
    OTHER = "neighbour-feature"

    def _build(self, root: Path) -> None:
        _authored_doc(root, "research", self.OLD)
        # A document in a DIFFERENT feature that links into the renamed one.
        _authored_doc(
            root,
            "adr",
            self.OTHER,
            related=[f"{DATE}-{self.OLD}-research"],
        )

    def test_cross_feature_incoming_link_rewritten(self, tmp_path: Path):
        self._build(tmp_path)
        rename_feature(tmp_path, self.OLD, self.NEW)

        other_path = tmp_path / ".vault" / "adr" / f"{DATE}-{self.OTHER}-adr.md"
        meta, _ = parse_frontmatter(other_path.read_text(encoding="utf-8"))
        related = meta.get("related", [])
        assert f"[[{DATE}-{self.NEW}-research]]" in related
        assert f"[[{DATE}-{self.OLD}-research]]" not in related
        # The neighbour's own feature tag is untouched.
        assert f"#{self.OTHER}" in meta.get("tags", [])

    def test_cross_links_reported_in_result(self, tmp_path: Path):
        self._build(tmp_path)
        result = rename_feature(tmp_path, self.OLD, self.NEW)

        sources = {cl["source"] for cl in result["cross_links"]}
        assert any(self.OTHER in src for src in sources), result["cross_links"]


# ---------------------------------------------------------------------------
# Archived documents are out of scope and must never be mutated by a rename.
# ---------------------------------------------------------------------------


class TestArchivedDocsUntouched:
    OLD = "widget-engine"
    NEW = "gadget-engine"

    def _archived_doc(self, root: Path) -> Path:
        """Write an archived doc whose related: points into the renamed feature."""
        folder = root / ".vault" / "_archive" / "research"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "2026-01-01-bygone-research.md"
        fm = _frontmatter(
            ["#research", "#bygone"],
            "2026-01-01",
            [f"{DATE}-{self.OLD}-adr"],
            flow_tags=False,
            extra_fm="",
        )
        path.write_text(f"{fm}\n# bygone\n\nArchived body.\n", encoding="utf-8")
        return path

    def test_archived_doc_bytes_unchanged_by_rename(self, tmp_path: Path):
        _authored_doc(tmp_path, "adr", self.OLD)
        archived = self._archived_doc(tmp_path)
        before = archived.read_bytes()

        result = rename_feature(tmp_path, self.OLD, self.NEW)
        assert result["status"] == "updated"

        # The archived back-reference and its modified stamp are left intact:
        # archived documents are out of rename scope, so neither the related:
        # cascade nor the stamp refresh may touch them.
        assert archived.read_bytes() == before


# ---------------------------------------------------------------------------
# S18 - reverse-journal rollback on an induced mid-apply failure
# ---------------------------------------------------------------------------


class TestRollback:
    OLD = "widget-engine"
    NEW = "gadget-engine"

    def _build(self, root: Path) -> None:
        _authored_doc(root, "research", self.OLD)
        _authored_doc(root, "adr", self.OLD, related=[f"{DATE}-{self.OLD}-research"])
        _authored_doc(
            root,
            "plan",
            self.OLD,
            related=[f"{DATE}-{self.OLD}-adr"],
            extra_fm="tier: L2\n",
        )
        _authored_doc(
            root, "audit", self.OLD, topic="perf", related=[f"{DATE}-{self.OLD}-plan"]
        )

    def test_reverse_journal_rollback_restores_state(self, tmp_path: Path):
        self._build(tmp_path)
        before = _snapshot_md(tmp_path)

        # Discover the deterministic apply order via the dry-run plan, then
        # plant a real directory at the SECOND destination filename. The OS
        # rename of that document fails only after the first rename has
        # already landed, forcing the reverse journal to undo real work.
        dry = rename_feature(tmp_path, self.OLD, self.NEW, dry_run=True)
        assert len(dry["paths"]) >= 2
        obstacle = tmp_path / dry["paths"][1]["new"]
        obstacle.mkdir(parents=False, exist_ok=False)

        with pytest.raises(VaultSpecError, match="rolled back"):
            rename_feature(tmp_path, self.OLD, self.NEW)

        # Remove the planted obstacle before inspecting for strays.
        obstacle.rmdir()

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before), (
            "rollback must leave no stray or missing documents; "
            f"added={set(after) - set(before)} removed={set(before) - set(after)}"
        )
        for path, original in before.items():
            assert after[path] == original, f"rollback did not restore {path.name}"


# ---------------------------------------------------------------------------
# S19 - force-merge and per-file collision refusal
# ---------------------------------------------------------------------------


class TestForceMergeAndCollision:
    def test_force_merge_into_existing_feature(self, tmp_path: Path):
        # Source has a research doc; target already owns an adr.
        _authored_doc(tmp_path, "research", "source-feature")
        _authored_doc(tmp_path, "adr", "target-feature")

        result = rename_feature(
            tmp_path, "source-feature", "target-feature", force=True
        )
        assert result["status"] == "updated"

        merged = list_documents(tmp_path, feature="target-feature")
        types = {d.doc_type for d in merged}
        # Both the pre-existing target adr and the migrated source research
        # now live under the target feature (plus the regenerated index).
        assert {"adr", "research"} <= types, types
        assert list_documents(tmp_path, feature="source-feature") == []

        # The migrated research doc carries the new filename and tag.
        research = (
            tmp_path / ".vault" / "research" / f"{DATE}-target-feature-research.md"
        )
        assert research.is_file()
        meta, _ = parse_frontmatter(research.read_text(encoding="utf-8"))
        assert "#target-feature" in meta.get("tags", [])
        assert "#source-feature" not in meta.get("tags", [])

    def test_per_file_collision_refused_and_no_mutation(self, tmp_path: Path):
        # Both features own an adr of the same date+type; after the segment
        # swap the source adr would land on the existing target adr.
        _authored_doc(tmp_path, "adr", "source-feature")
        _authored_doc(tmp_path, "adr", "target-feature")
        before = _snapshot_md(tmp_path)

        with pytest.raises(VaultSpecError, match="collision"):
            rename_feature(tmp_path, "source-feature", "target-feature", force=True)

        after = _snapshot_md(tmp_path)
        assert set(after) == set(before)
        for path, original in before.items():
            assert after[path] == original, f"collision refusal mutated {path.name}"


# ---------------------------------------------------------------------------
# S20 - flow-style tags normalization and index regeneration
# ---------------------------------------------------------------------------


class TestFlowTagsAndIndex:
    OLD = "widget-engine"
    NEW = "gadget-engine"

    def _build(self, root: Path) -> None:
        # research uses YAML flow-style tags: ['#widget-engine', '#research'].
        _authored_doc(root, "research", self.OLD, flow_tags=True)
        _authored_doc(root, "adr", self.OLD, related=[f"{DATE}-{self.OLD}-research"])
        _build_index(root, self.OLD)

    def test_flow_style_tags_normalized_to_new(self, tmp_path: Path):
        self._build(tmp_path)
        # Sanity: the flow-style doc is discoverable by feature.
        assert any(
            d.doc_type == "research" for d in list_documents(tmp_path, feature=self.OLD)
        )

        rename_feature(tmp_path, self.OLD, self.NEW)

        research = tmp_path / ".vault" / "research" / f"{DATE}-{self.NEW}-research.md"
        meta, _ = parse_frontmatter(research.read_text(encoding="utf-8"))
        tags = meta.get("tags", [])
        assert isinstance(tags, list)
        assert f"#{self.NEW}" in tags
        assert "#research" in tags
        assert f"#{self.OLD}" not in tags

    def test_old_index_removed_and_new_index_regenerated(self, tmp_path: Path):
        self._build(tmp_path)
        old_index = tmp_path / ".vault" / "index" / f"{self.OLD}.index.md"
        assert old_index.is_file()

        rename_feature(tmp_path, self.OLD, self.NEW)

        new_index = tmp_path / ".vault" / "index" / f"{self.NEW}.index.md"
        assert not old_index.exists(), "stale index must be removed"
        assert new_index.is_file(), "fresh index must be regenerated"

        meta, _ = parse_frontmatter(new_index.read_text(encoding="utf-8"))
        assert "#index" in meta.get("tags", [])
        assert f"#{self.NEW}" in meta.get("tags", [])
        related = meta.get("related", [])
        assert f"[[{DATE}-{self.NEW}-research]]" in related
        assert f"[[{DATE}-{self.NEW}-adr]]" in related
        assert all(self.OLD not in str(r) for r in related)
