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
``unreleased-surface`` markers, so the region cannot be quietly dropped and
leave a document that says nothing about what it describes.

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


_REGION = "unreleased-surface"

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
    for path in _managed_paths():
        text = path.read_text(encoding="utf-8")
        assert begin_marker(_REGION) in text, (
            f"{path.name} carries no {_REGION} region, so it describes a "
            "surface without saying which release that surface is."
        )
        assert end_marker(_REGION) in text


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
        f"`{_REGION}` region, which is recomputed from "
        "`published-surface.json` and cannot go stale:\n  - " + "\n  - ".join(offenders)
    )


def test_the_committed_snapshot_backs_the_committed_region() -> None:
    """The rendered region names the release the committed snapshot records.

    The two artifacts are refreshed by different verbs, so nothing but this
    check stops a snapshot moving while the documents keep quoting the release
    it replaced.
    """
    published = load_published_surface()
    for path in _managed_paths():
        text = path.read_text(encoding="utf-8")
        _, _, rest = text.partition(begin_marker(_REGION))
        body, _, _ = rest.partition(end_marker(_REGION))
        assert f"`{published.version}`" in body, (
            f"{path.name}'s {_REGION} region does not name "
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
        RenderContext(typer_app=app, live=surface, published=surface)
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
        RenderContext(typer_app=app, live=live, published=published)
    )

    assert "spec hooks trust" in rendered
    assert "--dry-run" in rendered
    assert "log" in rendered
