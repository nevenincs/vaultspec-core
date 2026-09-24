"""Guards for the README walkthrough stills.

A still is a terminal session a reader may copy from, so its commands must wrap
the way a shell accepts them and fit the window, and its output must be the
command's own with only blank lines tidied. The README embeds a fixed set of
stills; the set it embeds and the set the renderer draws must be the same, or
one of them is showing something stale.

Imports happen inside the test bodies: the renderer's modules delete
``NO_COLOR`` at import time.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from docs._render.tests.conftest import FeatureBuild

pytestmark = [pytest.mark.usefixtures("preserved_no_color")]

#: A walkthrough still embedded in the README.
STILL_LINK = re.compile(r"\(docs/assets/walkthrough/([\w-]+)\.svg\)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.mark.unit
def test_a_long_command_wraps_between_options_within_the_window() -> None:
    from docs._render.render_readme_walkthrough import wrap_command
    from docs._render.walkthrough import Command

    args = (
        "vault",
        "exec",
        "log",
        "--feature",
        "search-api",
        "--related",
        "2026-09-24-search-api-plan",
        "--step",
        "S01",
        "--row",
        "M:src/db/schema.sql",
        "--verify",
        "pytest tests/search=pass",
    )
    command = Command(args, "")
    lines = wrap_command(command, width=60)

    assert len(lines) > 1
    for line in lines[:-1]:
        assert line.endswith(" \\"), line
    for index, line in enumerate(lines):
        lead = 2 if index == 0 else 4
        assert lead + len(line) <= 60, line
    rejoined = " ".join(line.removesuffix(" \\") for line in lines)
    assert rejoined == command.shown


@pytest.mark.unit
def test_a_short_command_stays_on_one_line() -> None:
    from docs._render.render_readme_walkthrough import wrap_command
    from docs._render.walkthrough import Command

    assert wrap_command(Command(("status", "search-api"), "")) == [
        "vaultspec-core status search-api"
    ]


@pytest.mark.unit
def test_output_keeps_its_lines_and_tidies_only_the_blank_ones() -> None:
    from docs._render.render_readme_walkthrough import output_lines

    assert output_lines("\n\nfirst\n\n\n\nsecond\n  \n") == ["first", "", "second"]


@pytest.mark.integration
def test_a_still_opens_with_its_caption_and_types_every_command(
    feature_build: FeatureBuild,
) -> None:
    from docs._render.render_readme_walkthrough import STAND_IN_NOTE, compose

    for stage in feature_build.stages:
        plain = ANSI.sub("", compose(stage))
        assert plain.startswith(f"# {stage.caption}\n")
        for command in stage.commands:
            assert command.groups()[0] in plain
        assert (STAND_IN_NOTE[0] in plain) is stage.stand_in, stage.slug


@pytest.mark.integration
def test_every_still_the_renderer_draws_is_a_stage_of_the_build(
    feature_build: FeatureBuild,
) -> None:
    from docs._render.render_readme_walkthrough import STILLS

    slugs = {stage.slug for stage in feature_build.stages}
    assert set(STILLS) <= slugs, sorted(set(STILLS) - slugs)


@pytest.mark.repo
def test_the_readme_embeds_exactly_the_stills_the_renderer_draws(
    repo_root: Path,
) -> None:
    """A still the README shows but the renderer no longer draws goes stale."""
    from docs._render.render_readme_walkthrough import STILLS

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    embedded = STILL_LINK.findall(readme)

    assert embedded, "the README embeds no walkthrough still"
    assert embedded == list(STILLS)
    for slug in STILLS:
        still = repo_root / "docs" / "assets" / "walkthrough" / f"{slug}.svg"
        assert still.is_file(), f"{still} has not been rendered"
