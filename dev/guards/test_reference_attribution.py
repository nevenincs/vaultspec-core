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

Three properties are held.

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
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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
        text = path.read_text(encoding="utf-8")
        _, _, rest = text.partition(begin_marker(region_id))
        body, _, _ = rest.partition(end_marker(region_id))
        assert f"`{published.version}`" in body, (
            f"{path.name}'s {region_id} region does not name "
            f"{published.version}, the release {published_surface_path().name} "
            "records. Run `vaultspec-core spec reference generate`."
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


# ---------------------------------------------------------------------------
# The release lane
#
# The contract has two halves in two workflows, and each is one step that
# nothing else depends on - a shape that can be deleted without anything
# turning red until the release it was supposed to guard. So the steps
# themselves are the assertion here.
# ---------------------------------------------------------------------------


def _workflow_runs(path: str) -> list[str]:
    """Every ``run:`` script in a workflow, flattened to one string each."""
    import yaml

    document = yaml.safe_load(
        (_repo_root() / ".github" / "workflows" / path).read_text(encoding="utf-8")
    )
    scripts: list[str] = []
    for job in document["jobs"].values():
        for step in job.get("steps", []):
            script = step.get("run")
            if script:
                scripts.append(" ".join(str(script).split()))
    return scripts


def _repo_root() -> Path:
    from pathlib import Path as _Path

    return _Path(__file__).resolve().parents[2]


def test_the_candidate_branch_refreshes_the_surface_snapshot() -> None:
    """The one place the snapshot may move is the one place that moves it.

    On main the versions match and the refresh verb refuses to write, so if
    this step is not on the candidate branch the snapshot never advances - and
    the references keep attributing every later release against the surface of
    whichever release last had this step.
    """
    scripts = _workflow_runs("release-please.yml")

    assert any("just framework-surface" in script for script in scripts), (
        "release-please.yml no longer refreshes the published surface on the "
        "candidate branch, which is the only branch where it may be refreshed."
    )


def test_the_refresh_commits_what_it_regenerates() -> None:
    """A refresh that is not pushed is a refresh the tag will not carry."""
    refresh = next(
        script
        for script in _workflow_runs("release-please.yml")
        if "just framework-surface" in script
    )

    assert "git commit" in refresh and "git push" in refresh, (
        "the surface refresh runs but is never pushed, so the tag would be cut "
        "from a tree that still carries the previous release's snapshot"
    )


def test_the_publish_lane_verifies_the_surface_before_it_publishes() -> None:
    """The gate that can still stop a release runs before the upload.

    `publish-pypi` is the one step in this repository that cannot be undone.
    A surface check after it can only report; this one refuses.
    """
    import yaml

    document = yaml.safe_load(
        (_repo_root() / ".github" / "workflows" / "publish.yml").read_text(
            encoding="utf-8"
        )
    )
    smoke_steps = [
        " ".join(str(step.get("run", "")).split())
        for step in document["jobs"]["smoke-test"]["steps"]
    ]

    assert any("just release-verify-surface" in step for step in smoke_steps), (
        "the smoke-test job no longer verifies the built distribution against "
        "the reference it ships, so a mismatch would reach PyPI"
    )
    assert "smoke-test" in document["jobs"]["publish-pypi"]["needs"], (
        "publish-pypi no longer depends on smoke-test, so the surface gate "
        "cannot stop the upload it exists to stop"
    )


def test_the_publish_lane_verifies_what_it_actually_published() -> None:
    """The attached artifact is read back, not assumed to be what was built."""
    scripts = _workflow_runs("publish.yml")
    published_check = [
        script
        for script in scripts
        if "gh release download" in script and "just release-verify-surface" in script
    ]

    assert published_check, (
        "publish.yml no longer downloads the attached wheel and verifies its "
        "surface, so nothing checks what a user actually installs"
    )
