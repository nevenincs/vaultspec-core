"""Guards for the committed README terminal-render generator.

The renderer's two testable halves are the synthetic demo corpus it authors -
which must be a valid vault, since the published screenshots are genuine
command output over it - and the SVG export, which patches a literal out of
rich's own output and therefore breaks silently on a rich upgrade.

The renderer deletes ``NO_COLOR`` from the process environment at import time,
so every test here takes the ``preserved_no_color`` fixture and imports inside
the test body rather than at module scope. Importing at module scope would run
that side effect during collection, where it would outlive these tests and
change what the CLI suite sees.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("preserved_no_color")]

#: The directory tag every document carries, keyed by its `.vault/` subfolder.
DIRECTORY_TAGS = frozenset({"research", "reference", "adr", "plan", "exec"})

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
TAG_LINE = re.compile(r'^\s*-\s*"#([^"]+)"\s*$', re.MULTILINE)
STEP_ROW = re.compile(r"^- \[(x| )\] `(P\d+)\.(S\d+)`", re.MULTILINE)
DATE_STAMP = re.compile(r"^(date|modified): '([\d-]+)'$", re.MULTILINE)


def frontmatter_of(path: Path) -> str:
    """Return the YAML frontmatter block of a vault document."""
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match is not None, f"{path} has no YAML frontmatter"
    return match.group(1)


def feature_of(plan: Path) -> str:
    """Return the feature name encoded in a ``yyyy-mm-dd-<feature>-plan`` stem."""
    return plan.stem.split("-", 3)[3].rsplit("-", 1)[0]


def svg_source(path: Path) -> str:
    """Return an exported SVG with its literal spaces restored.

    rich emits every space inside a ``<text>`` element as the ``&#160;``
    non-breaking-space entity so the terminal grid keeps its columns, which
    means a rendered phrase never appears verbatim in the file.
    """
    return path.read_text(encoding="utf-8").replace("&#160;", " ")


@pytest.fixture
def demo_vault(tmp_path: Path) -> Path:
    """Author the synthetic demo corpus into a throwaway directory."""
    from docs._render.render_readme_assets import build_demo_vault

    build_demo_vault(tmp_path)
    return tmp_path / ".vault"


def test_build_demo_vault_authors_every_pipeline_document(
    demo_vault: Path, tmp_path: Path
) -> None:
    """Each demo feature contributes the research/reference/adr/plan quartet."""
    assert (tmp_path / ".vaultspec").is_dir()

    plans = sorted(demo_vault.glob("plan/*.md"))
    assert plans, "build_demo_vault authored no plans"
    for plan in plans:
        prefix = plan.stem.removesuffix("-plan")
        for doc_type in ("research", "reference", "adr"):
            document = demo_vault / doc_type / f"{prefix}-{doc_type}.md"
            assert document.is_file(), f"missing {document}"


def test_demo_documents_carry_exactly_the_required_tag_pair(
    demo_vault: Path,
) -> None:
    """Published screenshots must not show a corpus that fails ``vault check``."""
    documents = sorted(demo_vault.rglob("*.md"))
    assert documents, "build_demo_vault wrote no documents"
    for document in documents:
        directory = document.relative_to(demo_vault).parts[0]
        tags = TAG_LINE.findall(frontmatter_of(document))
        assert len(tags) == 2, f"{document} carries {tags}"
        directory_tag, feature_tag = tags
        assert directory_tag == directory, f"{document} is tagged #{directory_tag}"
        assert feature_tag not in DIRECTORY_TAGS, f"{document} has tag #{feature_tag}"


def test_demo_documents_carry_matching_date_and_modified_stamps(
    demo_vault: Path,
) -> None:
    """Scaffolded documents stamp ``modified`` equal to ``date``."""
    for document in sorted(demo_vault.rglob("*.md")):
        stamps = DATE_STAMP.findall(frontmatter_of(document))
        assert len(stamps) == 2, f"{document} frontmatter: {stamps}"
        assert stamps[0][1] == stamps[1][1], f"{document} stamps disagree: {stamps}"


def test_every_checked_step_gets_an_execution_record(demo_vault: Path) -> None:
    """The status render reads as tracked work only if the records exist."""
    checked_total = 0
    open_total = 0
    for plan in sorted(demo_vault.glob("plan/*.md")):
        prefix = plan.stem.removesuffix("-plan")
        exec_dir = demo_vault / "exec" / prefix
        rows = STEP_ROW.findall(plan.read_text(encoding="utf-8"))
        assert rows, f"{plan} declares no Step rows"
        for box, phase_id, step_id in rows:
            record = exec_dir / f"{prefix}-{phase_id}-{step_id}.md"
            if box == "x":
                checked_total += 1
                assert record.is_file(), f"checked Step has no record: {record}"
            else:
                open_total += 1
                assert not record.exists(), f"open Step has a record: {record}"
    assert checked_total, "the demo corpus checks no Steps at all"
    assert open_total, "the demo corpus has no open Steps, so status shows no work"


def test_demo_corpus_names_no_feature_of_this_project(
    demo_vault: Path, repo_root: Path
) -> None:
    """Published renders must carry invented features, not real development records.

    The screenshots ship in the README, so a demo corpus that reused one of this
    checkout's own feature names would publish an internal development record.
    """
    demo_features = {feature_of(plan) for plan in demo_vault.glob("plan/*.md")}
    assert demo_features, "build_demo_vault authored no plans"

    real_features = {
        index.name.removesuffix(".index.md")
        for index in (repo_root / ".vault" / "index").glob("*.index.md")
    }
    assert real_features, "this checkout has no feature indexes to compare against"
    assert not demo_features & real_features


def test_render_svg_writes_a_themed_terminal_window(tmp_path: Path) -> None:
    """The export lands on disk with the brand border swapped in."""
    from docs._render.render_readme_assets import LIGHT_STROKE, RICH_STROKE, render_svg

    out = tmp_path / "term.svg"
    render_svg("first line\nsecond line\n", str(out), "vaultspec-core status", 40)

    svg = svg_source(out)
    assert svg.lstrip().startswith("<svg")
    assert "vaultspec-core status" in svg
    assert "first line" in svg
    assert "second line" in svg
    assert LIGHT_STROKE in svg
    assert RICH_STROKE not in svg


def test_render_svg_truncates_to_max_lines_and_marks_the_cut(tmp_path: Path) -> None:
    """A long capture is trimmed with a visible ellipsis rather than silently."""
    from docs._render.render_readme_assets import render_svg

    out = tmp_path / "trimmed.svg"
    body = "\n".join(f"row{index:02d}" for index in range(20))
    render_svg(body, str(out), "trimmed", 40, max_lines=3)

    svg = svg_source(out)
    assert "row00" in svg
    assert "row02" in svg
    assert "row03" not in svg
    assert "…" in svg


def test_render_svg_honours_start_match(tmp_path: Path) -> None:
    """Preamble above the interesting section is dropped, not rendered."""
    from docs._render.render_readme_assets import render_svg

    out = tmp_path / "started.svg"
    render_svg(
        "preamble noise\nVault Check\nfindings\n",
        str(out),
        "started",
        40,
        start_match="Vault Check",
    )

    svg = svg_source(out)
    assert "preamble" not in svg
    assert "Vault Check" in svg
    assert "findings" in svg
