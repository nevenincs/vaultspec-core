"""Guards for the feature-cycle video's storyboard.

Capturing frames needs Chromium and encoding needs ffmpeg, but everything the
player shows is decided in pure Python before either runs: the timeline, the
terminal's HTML, and each stage's card. A timeline that overruns the video
cuts a stage off, and a card that drops the stand-in disclosure misstates where
the cross-reference judgments came from, so both are pinned here.

Imports happen inside the test bodies: the renderer's modules delete
``NO_COLOR`` at import time.
"""

from __future__ import annotations

import itertools
import json
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from docs._render.tests.conftest import FeatureBuild

pytestmark = [pytest.mark.usefixtures("preserved_no_color")]


def _stages(story: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", story["stages"])


@pytest.mark.unit
def test_terminal_output_becomes_one_escaped_html_line_per_line() -> None:
    from docs._render.render_readme_video import ansi_html

    lines = ansi_html(["\x1b[1mbold\x1b[0m", "<tag> & more", ""])

    assert len(lines) == 3
    assert "bold" in lines[0] and "font-weight: bold" in lines[0]
    assert "&lt;tag&gt; &amp; more" in lines[1]


@pytest.mark.unit
def test_a_record_renders_without_its_template_comments() -> None:
    from docs._render.render_readme_video import markdown_html

    rendered = markdown_html(
        "<!-- scaffold hint -->\n## Steps\n\n- [x] `S01` - done.\n- [ ] `S02` - next.\n"
    )

    assert "scaffold hint" not in rendered
    assert rendered.count('class="box on"') == 1
    assert rendered.count('class="box"') == 1
    assert "<h2>Steps</h2>" in rendered


@pytest.mark.integration
def test_the_stages_fill_the_video_between_its_title_cards(
    feature_build: FeatureBuild,
) -> None:
    from docs._render.render_readme_video import DURATION, INTRO, OUTRO

    story = feature_build.story
    stages = _stages(story)

    assert stages[0]["start"] == INTRO
    for before, after in itertools.pairwise(stages):
        assert before["end"] == after["start"]
    assert stages[-1]["end"] == pytest.approx(DURATION - OUTRO, abs=0.01)
    assert cast("dict[str, float]", story["outro"])["start"] == stages[-1]["end"]


@pytest.mark.integration
def test_every_command_types_then_prints_inside_its_stage(
    feature_build: FeatureBuild,
) -> None:
    for stage in _stages(feature_build.story):
        start, end = cast("float", stage["start"]), cast("float", stage["end"])
        card = cast("dict[str, object]", stage["card"])
        last = start
        for command in cast("list[dict[str, float]]", stage["commands"]):
            assert last <= command["typeStart"] < command["typeEnd"]
            assert command["typeEnd"] <= command["outAt"] < end
            last = command["outAt"]
        assert last <= cast("float", card["at"]) < end, stage["slug"]


@pytest.mark.integration
def test_the_cross_reference_card_says_its_judgments_came_from_a_stand_in(
    feature_build: FeatureBuild,
) -> None:
    from docs._render.render_readme_video import STAND_IN_NOTE

    (stage,) = [s for s in _stages(feature_build.story) if s["slug"] == "04-crossref"]
    card = cast("dict[str, str]", stage["card"])

    assert STAND_IN_NOTE in card["html"].replace("&#x27;", "'")
    assert "api-pagination-adr" in card["html"]


@pytest.mark.integration
def test_the_graph_card_draws_the_decisions_the_feature_now_links(
    feature_build: FeatureBuild,
) -> None:
    (stage,) = [s for s in _stages(feature_build.story) if s["slug"] == "09-graph"]
    html = cast("dict[str, str]", stage["card"])["html"]

    for label in ("search-api-adr", "storage-layer-adr", "api-pagination-adr"):
        assert f">{label}</text>" in html


@pytest.mark.integration
def test_the_player_embeds_the_storyboard_as_data(feature_build: FeatureBuild) -> None:
    """Record text must not be able to close the player's script element."""
    from docs._render.render_readme_video import player_html

    page = player_html(feature_build.story)
    start = page.index("const STORY = ") + len("const STORY = ")
    end = page.index(";\n", start)

    assert "/*STORYBOARD*/" not in page
    assert json.loads(page[start:end].replace("<\\/", "</")) == json.loads(
        json.dumps(feature_build.story)
    )
    assert page.count("</script>") == 1
