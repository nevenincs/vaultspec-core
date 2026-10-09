"""Contracts on how a generated reference attributes its own surface.

The defect these hold against is not a missing sentence; it is a sentence that
was true when it was written. ``docs/CLI.md`` carried "not available in the
0.1.73 release" for two of the six commands that needed it, and nothing in the
repository knew the claim existed, which release it expired at, or that four
other commands had no claim at all.

``dev/guards/test_release_provenance.py`` records why that shape is dangerous
here specifically: a version-scoped claim comes due on the release-please
branch, which is regenerated and force-pushed, so the repair lands under release
pressure on the branch least able to hold it. That file holds the wording of
such claims in ``docs/channels.md``. This one holds the stronger property for
the generated references - that they make no such claim by hand at all, because
the claim is rendered from the recorded surface of the release and recomputed on
every generate.

Four properties are held.

*The attribution exists and is generator-owned.* Both CLI surfaces carry the
``unreleased-*`` markers - one per file, MCP-scoped in the MCP handbook - so
the region cannot be quietly dropped and leave a document that says nothing
about what it describes.

*Nothing outside a managed region names a release.* A hand-written version
caveat is the shape being retired; a new one must fail here rather than be
noticed by a reader who cannot install what they are reading.

*The empty state is written out.* When a release ships, the difference is empty,
and the region must still say so. A blank region is indistinguishable from an
unfilled one, and the whole point is that a reader can tell.

*The record is the release a user can install.* The committed snapshot must be
the surface the latest published GitHub release's own wheel reports - never a
draft's, never a prerelease's, never a source tree's. It was once stamped on
the release-please branch from the candidate's version, and main's references
named a draft as the latest published release for as long as that draft sat
unpublished.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest

from vaultspec_core.cli.reference_gen import (
    MANAGED_FILES,
    RenderContext,
    begin_marker,
    end_marker,
    render_unreleased_surface,
)
from vaultspec_core.cli.reference_surface import (
    Surface,
    deserialize_surface,
    load_published_surface,
    published_surface_path,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.repo, pytest.mark.integration]


#: Every managed file carries an attribution region; the CLI surfaces share one
#: and the MCP handbook has its own, MCP-scoped variant. Matched by prefix so
#: registering a third scoped surface is covered without editing this guard.
_ATTRIBUTION_PREFIX = "unreleased"

_VERSION = r"`?v?\d+\.\d+\.\d+`?"

#: Availability language: a claim that something is or is not in a named
#: release. Only this shape expires, and only this shape is forbidden.
_AVAILABILITY = (
    r"(?:un)?available|ships?|shipped|included|introduced|requires?|needs?"
    r"|only in|not in|new in|added in|landed in"
)

#: A version within availability language, in either order. Deliberately narrow.
#: These documents name versions in roles that do not expire - a minimum Python,
#: a dependency floor, the schema boundary that `vault exec fold` reads records
#: from before - and those are exactly the frozen-fact wording
#: ``test_release_provenance.py`` argues for. A guard that failed on them would
#: be turned off, and would take the claim that matters with it.
_AVAILABILITY_CLAIM = re.compile(
    rf"(?:{_AVAILABILITY})[^.]{{0,80}}?{_VERSION}"
    rf"|{_VERSION}[^.]{{0,80}}?(?:{_AVAILABILITY})",
    re.IGNORECASE,
)


def _attribution_regions() -> list[tuple[Path, str]]:
    """Pair each generator-owned file present here with its attribution region.

    Asserted non-empty per file: a managed file that carried no attribution
    region would otherwise drop out of every scan below and pass silently,
    which is the failure mode - a document that says nothing about the surface
    it describes - these contracts exist to catch.
    """
    pairs: list[tuple[Path, str]] = []
    for managed in MANAGED_FILES:
        path = managed.path_factory()
        if not path.is_file():
            continue
        regions = [
            region.region_id
            for region in managed.regions
            if region.region_id.startswith(_ATTRIBUTION_PREFIX)
        ]
        assert len(regions) == 1, (
            f"{path.name} declares {len(regions)} attribution regions; "
            "exactly one names the release its surface belongs to."
        )
        pairs.append((path, regions[0]))
    assert pairs, "the managed-file registry resolved to no file in this checkout"
    return pairs


def _managed_paths() -> list[Path]:
    """Every generator-owned file present in this checkout.

    Derived from the registry rather than listed here, so registering a new
    reference brings it under these contracts without a second edit - and
    asserted non-empty, because a registry that resolved to nothing would let
    every scan below pass vacuously.
    """
    paths = [
        managed.path_factory()
        for managed in MANAGED_FILES
        if managed.path_factory().is_file()
    ]
    assert paths, "the managed-file registry resolved to no file in this checkout"
    return paths


def _strip_managed_regions(text: str) -> str:
    """Return *text* with every generator-owned region's body removed.

    What remains is the hand-written prose, which is what the caveat contract
    below scans: generated attribution is expected to name a version, and a
    guard that failed on the generated text would forbid the mechanism it
    exists to protect.
    """
    stripped = text
    for region_id in _region_ids():
        begin, end = begin_marker(region_id), end_marker(region_id)
        while begin in stripped and end in stripped:
            head, _, rest = stripped.partition(begin)
            _, _, tail = rest.partition(end)
            stripped = head + tail
    return stripped


def _region_ids() -> list[str]:
    return sorted(
        {region.region_id for managed in MANAGED_FILES for region in managed.regions}
    )


def _region_body(text: str, region_id: str) -> str:
    return text.partition(begin_marker(region_id))[2].partition(end_marker(region_id))[
        0
    ]


def test_every_managed_reference_carries_the_attribution_region() -> None:
    """The region cannot be dropped, leaving a document that attributes nothing."""
    for path, region_id in _attribution_regions():
        text = path.read_text(encoding="utf-8")
        assert begin_marker(region_id) in text, (
            f"{path.name} carries no {region_id} region, so it describes a "
            "surface without saying which release that surface is."
        )
        assert end_marker(region_id) in text


def test_no_hand_written_prose_claims_availability_in_a_named_release() -> None:
    """A version caveat outside a managed region is the shape being retired.

    Not every version mention: a frozen historical fact (the schema boundary
    `vault exec fold` reads legacy records from) stays true forever and is the
    wording the provenance guards ask for. Only a claim about what a release
    contains can come due, and only that is forbidden here.
    """
    offenders: list[str] = []
    for path in _managed_paths():
        prose = _strip_managed_regions(path.read_text(encoding="utf-8"))
        flattened = re.sub(r"\s+", " ", prose)
        offenders.extend(
            f"{path.name}: {match.group(0).strip()}"
            for match in _AVAILABILITY_CLAIM.finditer(flattened)
        )
    assert not offenders, (
        "Hand-written release claims found in a generated reference. "
        "Attribution belongs in the generated "
        f"`{_ATTRIBUTION_PREFIX}-*` region, which is recomputed from "
        "`published-surface.json` and cannot go stale:\n  - " + "\n  - ".join(offenders)
    )


def test_the_committed_snapshot_backs_the_committed_region() -> None:
    """The rendered region names the release the committed snapshot records.

    The two artifacts are refreshed by different verbs, so nothing but this
    check stops a snapshot moving while the documents keep quoting the release
    it replaced.
    """
    published = load_published_surface()
    for path, region_id in _attribution_regions():
        body = _region_body(path.read_text(encoding="utf-8"), region_id)
        assert f"`{published.version}`" in body, (
            f"{path.name}'s {region_id} region does not name "
            f"{published.version}, the release {published_surface_path().name} "
            "records. Run `vaultspec-core spec reference generate`."
        )


def test_no_attribution_asserts_which_release_is_latest() -> None:
    """A frozen copy cannot keep a present-tense claim true.

    The rendered region ships inside the wheel and is deployed into consuming
    projects, where no generator reruns. "The latest published release is X"
    turned false in every such copy the day a later release published; the
    region names the release it was measured against instead.
    """
    for path, region_id in _attribution_regions():
        body = _region_body(path.read_text(encoding="utf-8"), region_id)
        assert "latest published release is" not in " ".join(body.split()), (
            f"{path.name}'s {region_id} region states which release is latest "
            "in the present tense, which every frozen copy of it will outlive"
        )


def test_the_empty_difference_still_states_the_release() -> None:
    """When a release ships, the region says so rather than going blank.

    This is the state every release lands in, and it is the one a blank region
    would be indistinguishable from an unfilled one in.
    """
    from vaultspec_core.cli import app

    surface = Surface(version="9.9.9", commands={"vault add": ()}, mcp_tools=("find",))
    rendered = render_unreleased_surface(
        RenderContext(typer_app=app, live=surface, published=surface, mcp_tools=())
    )

    assert rendered.strip()
    assert "`9.9.9`" in rendered


def test_a_difference_names_every_kind_of_addition() -> None:
    """Commands, flags on released commands, and MCP tools are each rendered.

    A renderer that dropped one of the three would silently under-report, and
    two of the six surfaces this contract was written for are flags rather than
    commands.
    """
    from vaultspec_core.cli import app

    published = Surface(
        version="1.0.0", commands={"migrations run": ("--json",)}, mcp_tools=()
    )
    live = Surface(
        version="1.1.0",
        commands={"migrations run": ("--dry-run", "--json"), "spec hooks trust": ()},
        mcp_tools=("log",),
    )

    rendered = render_unreleased_surface(
        RenderContext(typer_app=app, live=live, published=published, mcp_tools=())
    )

    assert "spec hooks trust" in rendered
    assert "--dry-run" in rendered
    assert "log" in rendered


def test_the_committed_snapshot_is_the_latest_published_release(
    tmp_path: Path,
) -> None:
    """The record the references cite is the surface of the release users install.

    Asked the way the recording lane asks it: which release GitHub reports as
    latest, and what that release's own wheel reports when installed in
    isolation. Red from a publication until its recording pull request merges -
    the window in which main's references are measured against an earlier
    release, which is what this exists to make visible. An unreachable GitHub
    raises rather than failing, so an outage never reads as a stale record.
    """
    from dev.packaging.products import VAULTSPEC_CORE
    from dev.packaging.published_surface import read_published_surface

    release, document = read_published_surface(VAULTSPEC_CORE, tmp_path)
    committed = load_published_surface()

    assert committed.version == release.version, (
        f"{published_surface_path().name} records {committed.version}, but the "
        f"latest published release is {release.tag}. Merge the open "
        "'chore: record the published surface' pull request, or run "
        "`just release-record-surface`."
    )
    assert committed == deserialize_surface(document), (
        f"{published_surface_path().name} names {release.tag} but does not hold "
        "the surface that release's wheel reports, so it was not recorded from "
        "it. Run `just release-record-surface`."
    )


# ---------------------------------------------------------------------------
# The release lane
#
# The contract has halves in three workflows, and each is one step that
# nothing else depends on - a shape that can be deleted without anything
# turning red until the release it was supposed to guard. So the steps
# themselves are the assertion here.
# ---------------------------------------------------------------------------


def _workflow(path: str) -> dict[object, object]:
    """A workflow document. Keyed by ``object``: PyYAML reads ``on:`` as True."""
    import yaml

    return cast(
        "dict[object, object]",
        yaml.safe_load(
            (_repo_root() / ".github" / "workflows" / path).read_text(encoding="utf-8")
        ),
    )


def _jobs(path: str) -> dict[str, dict[str, object]]:
    return cast("dict[str, dict[str, object]]", _workflow(path)["jobs"])


def _steps(path: str, job_id: str) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", _jobs(path)[job_id].get("steps", []))


def _workflow_runs(path: str) -> list[str]:
    """Every ``run:`` script in a workflow, flattened to one string each."""
    return [
        " ".join(str(step["run"]).split())
        for job_id in _jobs(path)
        for step in _steps(path, job_id)
        if step.get("run")
    ]


def _job_runs(path: str, job_id: str) -> list[str]:
    """One job's ``run:`` scripts in step order, flattened; empty for ``uses:``."""
    return [" ".join(str(step.get("run", "")).split()) for step in _steps(path, job_id)]


def _repo_root() -> Path:
    from pathlib import Path as _Path

    return _Path(__file__).resolve().parents[2]


def _workflow_names() -> list[str]:
    """Every workflow file, asserted present so a moved directory fails loudly."""
    names = sorted(
        path.name for path in (_repo_root() / ".github" / "workflows").glob("*.yml")
    )
    assert "publish.yml" in names, "the workflow corpus resolved to nothing"
    return names


def test_only_the_recording_lane_records_the_surface() -> None:
    """Nothing before publication, and nothing but the published wheel, writes it.

    The release-please branch is where the candidate's version was stamped as
    published. Any workflow other than the recording lane that writes the
    snapshot is that shape returning.
    """
    writers = ("release-record-surface", "snapshot --record", "framework-surface")
    offenders = [
        f"{name}: {writer}"
        for name in _workflow_names()
        if name != "surface.yml"
        for script in _workflow_runs(name)
        for writer in writers
        if writer in script
    ]
    assert not offenders, (
        "a workflow other than surface.yml writes the published-surface "
        "record:\n  " + "\n  ".join(offenders)
    )


def test_the_recording_lane_reads_the_latest_release_and_lands_by_pull_request() -> (
    None
):
    """It takes no tag, so the only release it can record is the latest one.

    main is ruleset-protected; a recording that is not proposed as a pull
    request is a recording main never receives.
    """
    triggers = cast(
        "dict[str, dict[str, object] | None]", _workflow("surface.yml")[True]
    )
    dispatch = triggers["workflow_dispatch"] or {}
    assert not dispatch.get("inputs"), (
        "surface.yml takes an input; a tag chosen by the caller can name a "
        "release other than the latest one"
    )

    runs = _job_runs("surface.yml", "record")
    recording = next(
        (
            i
            for i, run in enumerate(runs)
            if "published_surface record --from-file" in run
        ),
        None,
    )
    assert recording is not None, "surface.yml no longer records the surface"
    proposing = next((i for i, run in enumerate(runs) if "gh pr create" in run), None)
    assert proposing is not None and proposing > recording, (
        "surface.yml records the surface but never proposes it to main"
    )


def test_the_surface_is_recorded_only_after_publication() -> None:
    """Before the flip, the latest release is still the previous one."""
    runs = _job_runs("publish.yml", "publish-pypi")

    published = next(i for i, run in enumerate(runs) if "--draft=false" in run)
    recording = next(
        (i for i, run in enumerate(runs) if "gh workflow run surface.yml" in run),
        None,
    )
    assert recording is not None, (
        "publish.yml no longer asks for the published surface to be recorded, "
        "so main's references stay measured against the release before it"
    )
    assert recording > published, (
        "the recording is dispatched before the release is published, when "
        "the latest release is still the previous one"
    )


def test_release_execution_is_separated_from_surface_write_permissions() -> None:
    """Release code gets no credential and no home; its job can write nothing."""
    jobs = cast("dict[str, dict[str, object]]", _workflow("surface.yml")["jobs"])
    collect = jobs["collect"]
    record = jobs["record"]
    assert collect["runs-on"] == ["self-hosted", "Linux", "X64", "build"]
    permissions = cast("dict[str, str]", collect["permissions"])
    assert all(value == "read" for value in permissions.values())
    checkout = next(
        step
        for step in _steps("surface.yml", "collect")
        if "actions/checkout@" in str(step.get("uses", ""))
    )
    assert cast("dict[str, object]", checkout["with"])["persist-credentials"] is False
    collected = [
        run
        for run in _job_runs("surface.yml", "collect")
        if "published_surface emit" in run
    ]
    assert collected, "the collect job no longer asks the release for its surface"
    assert all("--namespace" in run for run in collected), (
        "release code must run behind an empty home, in namespaces of its own: "
        "without them it runs as the runner's user, beside that user's credentials"
    )
    assert not any("--container" in run for run in collected), (
        "no fleet host exposes a container runtime to a job, so a collection "
        "that needs one records nothing; release code is isolated by the "
        "environment `emit` starts it with"
    )
    assert record["needs"] == "collect"
    runs = _job_runs("surface.yml", "record")
    assert any("published_surface record --from-file" in run for run in runs)
    assert not any(
        "release-record-surface" in run or "published_surface emit" in run
        for run in runs
    )


def test_the_publish_lane_verifies_the_surface_before_it_publishes() -> None:
    """The gate that can still stop a release runs before the upload.

    `publish-pypi` is the one step in this repository that cannot be undone.
    A surface check after it can only report; this one refuses.
    """
    assert any(
        "just release-verify-surface" in run
        for run in _job_runs("publish.yml", "smoke-test")
    ), (
        "the smoke-test job no longer compares the built distribution's "
        "surface with its tree's, so a build that dropped a command would "
        "reach PyPI"
    )
    needs = cast("list[str]", _jobs("publish.yml")["publish-pypi"]["needs"])
    assert "smoke-test" in needs, (
        "publish-pypi no longer depends on smoke-test, so the surface gate "
        "cannot stop the upload it exists to stop"
    )


def test_the_publish_lane_reads_back_what_it_attached_without_project_code() -> None:
    """The attached wheel is compared with the built one, byte for byte.

    The job holds `id-token: write` and checks nothing out, so a recipe there
    runs whatever project code the runner's workspace happens to hold.
    """
    runs = _job_runs("publish.yml", "publish-pypi")

    assert any("gh release download" in run and "cmp " in run for run in runs), (
        "publish.yml no longer compares the attached wheel with the one it "
        "built, so nothing checks what a user actually downloads"
    )
    recipes = [
        line.strip()
        for step in _steps("publish.yml", "publish-pypi")
        for line in str(step.get("run", "")).splitlines()
        if line.strip().startswith("just ")
    ]
    assert not recipes, (
        "the publishing job runs a recipe, which is project code in a job "
        f"that can mint an OIDC token: {recipes}"
    )
