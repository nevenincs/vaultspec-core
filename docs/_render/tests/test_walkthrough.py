"""Guards for the scripted feature build the README renders draw from.

The walkthrough's outputs are published: the README embeds its stills and its
video. A command that failed, a stage that lost its output, or a stand-in
provider left installed after the build would each publish something false, so
the build itself is pinned here, alongside the rule the stand-in judges by.

Like the other renderer suites, this module imports inside the test bodies:
:mod:`docs._render.walkthrough` deletes ``NO_COLOR`` at import time.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from docs._render.tests.conftest import FeatureBuild

pytestmark = [pytest.mark.usefixtures("preserved_no_color")]

TICK = "\N{LEFT SINGLE QUOTATION MARK}"


def _state(text: str) -> dict[str, object]:
    return {"title": "t", "text": text}


@pytest.mark.unit
def test_a_command_is_shown_with_its_spaced_arguments_quoted() -> None:
    from docs._render.walkthrough import Command

    command = Command(("vault", "add", "research", "--title", "search options"), "")

    assert command.shown == 'vaultspec-core vault add research --title "search options"'


@pytest.mark.unit
def test_a_command_breaks_only_between_an_option_and_the_next() -> None:
    """A wrapped line must never part an option from the value it sets."""
    from docs._render.walkthrough import Command

    args = ("vault", "exec", "log", "--step", "S01", "--verify", "pytest x=pass")
    groups = Command(args, "").groups()

    assert groups == [
        "vaultspec-core vault exec log",
        "--step S01",
        '--verify "pytest x=pass"',
    ]


@pytest.mark.unit
def test_the_stand_in_links_a_pair_that_shares_code_artifacts() -> None:
    from docs._render.walkthrough import judge

    payload: dict[str, object] = {
        "state": {
            "source": _state(f"Use {TICK}src/a.py{TICK} and {TICK}src/b.py{TICK}."),
            "candidate": _state(f"Owns {TICK}src/a.py{TICK} and {TICK}src/b.py{TICK}."),
        },
        "questions": {},
    }
    answers = judge(payload, ["depends_on", "shared_artifact", "unrelated"], "none")

    need, artifact, useless = (answers[key] for key in ("need", "artifact", "useless"))
    assert need == {"type": "noul", "noul": 0.9}
    assert isinstance(artifact, dict) and artifact["noul"] > 0.5
    assert useless == {"type": "noul", "noul": 0.08}
    relation = answers["relation"]
    assert isinstance(relation, dict) and relation["choice"] == "depends_on"


@pytest.mark.unit
def test_the_stand_in_does_not_link_a_pair_with_nothing_in_common() -> None:
    from docs._render.walkthrough import judge

    payload: dict[str, object] = {
        "state": {
            "source": _state(f"Use {TICK}src/a.py{TICK}."),
            "candidate": _state(f"Owns {TICK}src/z.py{TICK}."),
        },
        "questions": {},
    }
    answers = judge(payload, ["depends_on", "shared_artifact", "unrelated"], "none")

    relation = answers["relation"]
    assert isinstance(relation, dict) and relation["choice"] == "unrelated"
    assert answers["useless"] == {"type": "noul", "noul": 0.88}


@pytest.mark.unit
def test_the_stand_in_chooses_the_option_that_shares_the_most_code() -> None:
    from docs._render.walkthrough import judge

    payload: dict[str, object] = {
        "state": {"source": _state(f"Use {TICK}src/a.py{TICK}.")},
        "questions": {
            "q1": {"criteria": {"o1": "Nothing here.", "o2": f"{TICK}src/a.py{TICK}"}},
            "q2": {"criteria": {"o3": "Nothing here either."}},
        },
    }
    answers = judge(payload, [], "none")

    first, second = answers["q1"], answers["q2"]
    assert isinstance(first, dict) and first["choice"] == "o2"
    assert isinstance(second, dict) and second["choice"] == "none"


@pytest.mark.integration
def test_every_stage_of_the_build_ran_and_printed(feature_build: FeatureBuild) -> None:
    """Every command succeeded (the build raises otherwise) and printed something."""
    from docs._render.walkthrough import TEMP_PREFIX

    slugs = [stage.slug for stage in feature_build.stages]

    assert slugs == sorted(slugs), "stages must be numbered in the order they run"
    assert len(slugs) == len(set(slugs))
    for stage in feature_build.stages:
        assert stage.commands, f"{stage.slug} ran no command on screen"
        for command in stage.commands:
            assert command.output.strip(), f"{command.shown} printed nothing"
            assert TEMP_PREFIX not in command.output, f"{command.shown} leaks a path"


@pytest.mark.integration
def test_the_cross_reference_links_the_decisions_that_share_code(
    feature_build: FeatureBuild,
) -> None:
    from rich.text import Text

    (crossref,) = [s for s in feature_build.stages if s.slug == "04-crossref"]
    output = Text.from_ansi(crossref.commands[0].output).plain

    assert crossref.stand_in
    assert "2 links" in output
    assert "api-pagination-adr (written)" in output
    assert "storage-layer-adr (written)" in output
    assert "request-auth" not in output, "an ADR sharing no code must not be linked"
    assert crossref.markdown is not None
    assert "api-pagination-adr]]" in crossref.markdown


@pytest.mark.integration
def test_the_finished_feature_checks_clean(feature_build: FeatureBuild) -> None:
    from rich.text import Text

    (check,) = [s for s in feature_build.stages if s.slug == "07-check"]
    lines = Text.from_ansi(check.commands[0].output).plain.splitlines()

    findings = [line for line in lines if line.strip().startswith(("x ", "! "))]
    assert not findings, findings
    assert any(line.strip().startswith("ok ") for line in lines)


@pytest.mark.integration
@pytest.mark.usefixtures("feature_build")
def test_the_stand_in_leaves_nothing_behind() -> None:
    """After the build the client's endpoint and the key are what they were."""
    import vaultspec_core.search._transport as transport
    from docs._render.walkthrough import STAND_IN_KEY
    from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY

    defaults = transport.JevClient.__init__.__kwdefaults__
    assert defaults is not None
    assert defaults["endpoint"] == transport.ENDPOINT
    assert os.environ.get(VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name) != STAND_IN_KEY
