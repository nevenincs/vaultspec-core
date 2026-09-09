"""Cover the published-surface snapshot: capture, comparison, and refresh policy.

The snapshot (:mod:`vaultspec_core.cli.reference_surface`) is what the generated
references attribute against. These tests exercise the real capture against the
live Typer tree and the live MCP registry, the real serialization round-trip,
and the real ``vaultspec-core spec reference snapshot`` verb - no mocks, no
skips.

The refresh policy carries most of the weight here. The snapshot records the
surface of a *release*, so it may be rewritten only where the tree is a
different release from the one recorded. Rewriting it on main between releases
would stamp the previous release's version onto commands that release does not
contain, which is the exact falsehood the contract removes; the tests below
pin that asymmetry in both directions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli.reference_surface import (
    SNAPSHOT_SCHEMA,
    Surface,
    SurfaceSnapshotError,
    capture_surface,
    deserialize_surface,
    load_published_surface,
    published_surface_path,
    refresh_reason,
    serialize_surface,
    unreleased_surface,
    write_published_surface,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


_RUNNER = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def _surface(
    version: str = "1.0.0",
    commands: dict[str, tuple[str, ...]] | None = None,
    mcp_tools: tuple[str, ...] = (),
) -> Surface:
    return Surface(
        version=version,
        commands={} if commands is None else commands,
        mcp_tools=mcp_tools,
    )


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def test_capture_reads_the_live_cli_and_mcp_surface() -> None:
    """Capture returns real verbs and real tool names, not an empty shell."""
    surface = capture_surface()

    assert "spec reference snapshot" in surface.commands
    assert "vault add" in surface.commands
    assert "status" in surface.mcp_tools
    assert "find" in surface.mcp_tools


def test_capture_records_long_flags_and_drops_the_synthesised_help() -> None:
    """Flags are captured per verb; Click's universal ``--help`` is not surface."""
    surface = capture_surface()

    assert "--check" in surface.commands["spec reference generate"]
    assert all("--help" not in flags for flags in surface.commands.values())


def test_capture_is_sorted_so_registration_order_cannot_churn_the_artifact() -> None:
    """Every collection is sorted: the snapshot is set membership, not layout."""
    surface = capture_surface()

    assert list(surface.commands) == sorted(surface.commands)
    assert surface.mcp_tools == tuple(sorted(surface.mcp_tools))
    for flags in surface.commands.values():
        assert flags == tuple(sorted(flags))


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_serialization_round_trips_a_captured_surface() -> None:
    """A captured surface survives serialize/deserialize unchanged."""
    original = capture_surface()

    assert deserialize_surface(serialize_surface(original)) == original


def test_serialization_is_stable_across_runs() -> None:
    """Serializing twice yields identical bytes, so the artifact has no churn."""
    surface = capture_surface()

    assert serialize_surface(surface) == serialize_surface(surface)


def test_the_committed_snapshot_is_readable_and_names_a_version() -> None:
    """The shipped snapshot parses and carries the release it describes."""
    published = load_published_surface()

    assert published.version
    assert published.commands
    assert published.mcp_tools


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("{not json", "not valid JSON"),
        ("[]", "not a JSON object"),
        ('{"schema": 999}', "schema"),
        (f'{{"schema": {SNAPSHOT_SCHEMA}}}', "no version"),
        (f'{{"schema": {SNAPSHOT_SCHEMA}, "version": "1.0.0"}}', "no command map"),
        (
            f'{{"schema": {SNAPSHOT_SCHEMA}, "version": "1.0.0", "commands": {{}}}}',
            "no MCP tool list",
        ),
    ],
)
def test_a_malformed_snapshot_is_refused_by_name(document: str, expected: str) -> None:
    """Each malformation raises, naming which part of the document is wrong."""
    with pytest.raises(SurfaceSnapshotError, match=expected):
        deserialize_surface(document)


def test_an_absent_snapshot_raises_rather_than_reading_as_empty(
    tmp_path: Path,
) -> None:
    """Absence is loud: an empty surface would call every command unreleased."""
    with pytest.raises(SurfaceSnapshotError, match="no published-surface snapshot"):
        load_published_surface(tmp_path / "missing.json")


def test_writing_an_unchanged_surface_reports_no_change(tmp_path: Path) -> None:
    """The writer is idempotent, so a re-run leaves no diff to review."""
    snapshot = tmp_path / "published-surface.json"
    surface = _surface(commands={"vault add": ("--feature",)}, mcp_tools=("find",))

    assert write_published_surface(surface, snapshot) is True
    assert write_published_surface(surface, snapshot) is False


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def test_a_new_verb_is_reported_as_unreleased() -> None:
    """A command absent from the release is named."""
    published = _surface(commands={"vault add": ()})
    live = _surface(commands={"vault add": (), "spec hooks trust": ()})

    diff = unreleased_surface(live, published)

    assert diff.commands == ("spec hooks trust",)
    assert diff.flags == {}


def test_a_new_flag_on_an_existing_verb_is_reported_against_that_verb() -> None:
    """A flag added to a released command is attributed as precisely as a verb."""
    published = _surface(commands={"migrations run": ("--json",)})
    live = _surface(commands={"migrations run": ("--dry-run", "--json")})

    diff = unreleased_surface(live, published)

    assert diff.commands == ()
    assert diff.flags == {"migrations run": ("--dry-run",)}


def test_a_new_mcp_tool_is_reported_as_unreleased() -> None:
    """The MCP surface is compared on the same terms as the CLI surface."""
    published = _surface(mcp_tools=("find",))
    live = _surface(mcp_tools=("find", "log"))

    diff = unreleased_surface(live, published)

    assert diff.mcp_tools == ("log",)


def test_flags_of_an_unreleased_verb_are_not_reported_twice() -> None:
    """A wholly new verb is named once, not once per flag it carries."""
    published = _surface(commands={})
    live = _surface(commands={"spec hooks trust": ("--json", "--target")})

    diff = unreleased_surface(live, published)

    assert diff.commands == ("spec hooks trust",)
    assert diff.flags == {}


def test_a_matching_surface_reports_empty() -> None:
    """Identical surfaces produce nothing to attribute."""
    published = _surface(commands={"vault add": ("--feature",)}, mcp_tools=("find",))
    live = _surface(commands={"vault add": ("--feature",)}, mcp_tools=("find",))

    assert unreleased_surface(live, published).is_empty()


def test_a_removed_verb_is_not_reported_as_unreleased() -> None:
    """Retirements belong to the changelog, not to the installability question."""
    published = _surface(commands={"vault add": (), "vault retired": ()})
    live = _surface(commands={"vault add": ()})

    diff = unreleased_surface(live, published)

    assert diff.is_empty()


def test_the_difference_carries_the_version_it_was_taken_against() -> None:
    """The rendered region names a release, so the diff must carry which one."""
    published = _surface(version="0.1.73")
    live = _surface(version="0.1.73", commands={"spec hooks trust": ()})

    assert unreleased_surface(live, published).published_version == "0.1.73"


# ---------------------------------------------------------------------------
# Refresh policy
# ---------------------------------------------------------------------------


def test_a_matching_version_forbids_refresh() -> None:
    """On main between releases the snapshot is frozen, whatever the surface."""
    published = _surface(version="0.1.73", commands={"vault add": ()})
    live = _surface(version="0.1.73", commands={"vault add": (), "new verb": ()})

    assert refresh_reason(live, published) is None


def test_a_bumped_version_permits_refresh() -> None:
    """On the candidate branch the version differs and the snapshot may move."""
    published = _surface(version="0.1.73")
    live = _surface(version="0.2.0")

    reason = refresh_reason(live, published)

    assert reason is not None
    assert "0.2.0" in reason
    assert "0.1.73" in reason


# ---------------------------------------------------------------------------
# The verb
# ---------------------------------------------------------------------------


def test_snapshot_check_passes_on_a_tree_whose_version_matches() -> None:
    """`--check` is green while the recorded release is the declared one."""
    result = _RUNNER.invoke(app, ["spec", "reference", "snapshot", "--check"])

    assert result.exit_code == 0, result.output


def test_snapshot_write_is_a_no_op_when_the_version_matches() -> None:
    """The default mode leaves the committed snapshot untouched on main."""
    before = published_surface_path().read_bytes()

    result = _RUNNER.invoke(app, ["spec", "reference", "snapshot"])

    assert result.exit_code == 0, result.output
    assert published_surface_path().read_bytes() == before


def test_snapshot_emit_prints_this_build_s_own_surface() -> None:
    """`--emit` is how a published distribution is read back in isolation."""
    result = _RUNNER.invoke(app, ["spec", "reference", "snapshot", "--emit"])

    assert result.exit_code == 0, result.output
    emitted = deserialize_surface(result.stdout)
    assert emitted == capture_surface()


def test_snapshot_verify_accepts_a_document_matching_the_committed_snapshot(
    tmp_path: Path,
) -> None:
    """The publish-lane gate passes when the distribution matches its snapshot."""
    document = tmp_path / "surface.json"
    document.write_text(
        published_surface_path().read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = _RUNNER.invoke(
        app, ["spec", "reference", "snapshot", "--verify", str(document)]
    )

    assert result.exit_code == 0, result.output


def test_snapshot_verify_rejects_a_document_with_a_different_surface(
    tmp_path: Path,
) -> None:
    """A distribution whose surface differs from its snapshot fails the lane."""
    published = load_published_surface()
    document = tmp_path / "surface.json"
    document.write_text(
        serialize_surface(
            Surface(
                version=published.version,
                commands={**published.commands, "invented verb": ()},
                mcp_tools=published.mcp_tools,
            )
        ),
        encoding="utf-8",
    )

    result = _RUNNER.invoke(
        app, ["spec", "reference", "snapshot", "--verify", str(document)]
    )

    assert result.exit_code == 1
    assert "invented verb" in result.output


def test_snapshot_verify_rejects_a_document_declaring_another_version(
    tmp_path: Path,
) -> None:
    """A surface that matches but claims another release is still a mismatch."""
    published = load_published_surface()
    document = tmp_path / "surface.json"
    document.write_text(
        serialize_surface(
            Surface(
                version="99.0.0",
                commands=published.commands,
                mcp_tools=published.mcp_tools,
            )
        ),
        encoding="utf-8",
    )

    result = _RUNNER.invoke(
        app, ["spec", "reference", "snapshot", "--verify", str(document)]
    )

    assert result.exit_code == 1
    assert "99.0.0" in result.output
