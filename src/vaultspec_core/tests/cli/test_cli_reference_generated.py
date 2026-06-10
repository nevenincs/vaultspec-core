"""Cover the bundled CLI-reference generator and its ``--check`` gate.

The generator (:mod:`vaultspec_core.cli.reference_gen`) introspects the live
Typer command tree and rewrites the generator-owned regions of the bundled
reference at ``src/vaultspec_core/builtins/reference/cli.md``. These tests
exercise the real generator and the real ``vaultspec-core spec reference
generate`` verb against the live CLI surface and against temp-copied fixtures -
no mocks, no skips.

The companion drift guard in :mod:`test_cli_reference_drift` asserts coverage
(every command and flag is mentioned somewhere); this module asserts
byte-fidelity of the managed regions (the committed reference equals fresh
output) and that hand-written prose outside the markers survives a regenerate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli.reference_gen import (
    MANAGED_REGIONS,
    ReferenceMarkerError,
    begin_marker,
    bundled_reference_path,
    collect_leaf_signatures,
    end_marker,
    generate,
    render_reference,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


_RUNNER = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def test_committed_reference_is_in_sync_with_live_surface() -> None:
    """The committed reference equals fresh generator output (byte-identical)."""
    result = generate(check=True)
    assert result.in_sync, (
        "The bundled reference's managed regions diverged from the live CLI "
        "surface. Run `vaultspec-core spec reference generate` to refresh it.\n"
        f"{result.diff}"
    )
    assert result.diff == ""


def test_check_mode_via_cli_exits_zero_when_in_sync() -> None:
    """`spec reference generate --check` exits 0 against the committed file."""
    invocation = _RUNNER.invoke(app, ["spec", "reference", "generate", "--check"])
    assert invocation.exit_code == 0, invocation.output
    assert "in sync" in invocation.output


def test_collected_signatures_cover_the_live_tree() -> None:
    """Every collected signature is a real `vaultspec-core` leaf usage line."""
    signatures = collect_leaf_signatures(app)
    assert signatures, "Typer tree produced no leaf signatures"
    assert all(s.startswith("vaultspec-core ") for s in signatures)
    assert all("[OPTIONS]" in s for s in signatures)
    # Spot-check a known leaf with a required positional argument and one with
    # an optional positional, derived purely from the live surface.
    assert "vaultspec-core vault add [OPTIONS] DOC_TYPE" in signatures
    assert "vaultspec-core install [OPTIONS] [PROVIDER]" in signatures


def test_managed_inventory_reflects_full_live_surface() -> None:
    """Commands the prior hand-authored inventory omitted are now present.

    The hand-authored inventory predating the generator was missing several
    leaf commands (`doctor`, `vault graph`, `config get`/`list`). The generated
    inventory is sourced from the live tree, so these must now appear.
    """
    signatures = set(collect_leaf_signatures(app))
    for expected in (
        "vaultspec-core doctor [OPTIONS]",
        "vaultspec-core vault graph [OPTIONS]",
        "vaultspec-core config get [OPTIONS] KEY",
        "vaultspec-core config list [OPTIONS]",
    ):
        assert expected in signatures, expected


def test_reference_verb_documents_itself_in_inventory() -> None:
    """The visible generator verb appears in its own generated inventory.

    The ``spec reference`` group is a visible spec sub-group, so the generator
    that produces the inventory includes its own ``generate`` leaf - and the
    drift guard and language-contract test require a documented command to
    exist in the live tree.
    """
    signatures = collect_leaf_signatures(app)
    assert "vaultspec-core spec reference generate [OPTIONS]" in signatures


def test_generate_preserves_unmanaged_prose_verbatim(tmp_path: Path) -> None:
    """Prose outside the managed markers survives a regenerate byte-for-byte."""
    region = MANAGED_REGIONS[0]
    sentinel = "SENTINEL-PROSE-d3adb33f curated by hand and must survive."
    fixture = (
        "# heading\n\n"
        f"{sentinel}\n\n"
        f"{begin_marker(region.region_id)}\n\n"
        "```text\nstale content\n```\n\n"
        f"{end_marker(region.region_id)}\n\n"
        "## trailing prose section that the generator must not touch\n"
    )
    ref = tmp_path / "cli.md"
    ref.write_text(fixture, encoding="utf-8")

    result = generate(check=False, reference_path=ref, typer_app=app)
    assert result.changed
    rewritten = ref.read_text(encoding="utf-8")

    assert sentinel in rewritten
    assert "## trailing prose section that the generator must not touch" in rewritten
    # The stale managed body is gone; the live inventory replaced it.
    assert "stale content" not in rewritten
    assert "vaultspec-core install [OPTIONS] [PROVIDER]" in rewritten


def test_render_reference_is_idempotent(tmp_path: Path) -> None:
    """Rendering an already-generated reference is a no-op (stable output)."""
    once = render_reference(bundled_reference_path().read_text(encoding="utf-8"), app)
    twice = render_reference(once, app)
    assert once == twice


def test_check_detects_corrupted_managed_region(tmp_path: Path) -> None:
    """A hand-edit inside a managed region is caught by check with a diff."""
    committed = bundled_reference_path().read_text(encoding="utf-8")

    # Corrupt one signature line inside the managed zone only.
    corrupted = committed.replace(
        "vaultspec-core install [OPTIONS] [PROVIDER]",
        "vaultspec-core install [OPTIONS] [TAMPERED]",
        1,
    )
    assert corrupted != committed, "fixture corruption did not apply"
    ref = tmp_path / "cli.md"
    ref.write_text(corrupted, encoding="utf-8")

    result = generate(check=True, reference_path=ref, typer_app=app)
    assert not result.in_sync
    assert result.diff
    assert "[TAMPERED]" in result.diff
    # Check mode must not rewrite the file.
    assert ref.read_text(encoding="utf-8") == corrupted


def test_missing_marker_raises(tmp_path: Path) -> None:
    """A reference lacking the managed markers fails loudly, not silently."""
    ref = tmp_path / "cli.md"
    ref.write_text("# heading\n\nno markers here\n", encoding="utf-8")
    with pytest.raises(ReferenceMarkerError):
        generate(check=True, reference_path=ref, typer_app=app)


def test_reversed_markers_raise_distinct_message(tmp_path: Path) -> None:
    """End-before-begin reports the misordering, not a missing end marker.

    With the end marker present but preceding the begin marker, the anchored
    end search fails while an unanchored search succeeds. The error must name
    the misordering rather than claim the end marker is absent.
    """
    region = MANAGED_REGIONS[0]
    reversed_text = (
        "# heading\n\n"
        f"{end_marker(region.region_id)}\n\n"
        "```text\nstale content\n```\n\n"
        f"{begin_marker(region.region_id)}\n"
    )
    ref = tmp_path / "cli.md"
    ref.write_text(reversed_text, encoding="utf-8")

    with pytest.raises(ReferenceMarkerError) as excinfo:
        generate(check=True, reference_path=ref, typer_app=app)

    message = str(excinfo.value)
    assert "precedes begin marker" in message
    assert region.region_id in message
    assert "Missing end marker" not in message


def test_write_mode_reconciles_drift_and_reports_unchanged_on_second_run(
    tmp_path: Path,
) -> None:
    """Write mode fixes drift, and a second run is a clean no-op."""
    region = MANAGED_REGIONS[0]
    drifted = (
        f"# heading\n\n{begin_marker(region.region_id)}\n\n"
        "```text\nvaultspec-core bogus [OPTIONS]\n```\n\n"
        f"{end_marker(region.region_id)}\n"
    )
    ref = tmp_path / "cli.md"
    ref.write_text(drifted, encoding="utf-8")

    first = generate(check=False, reference_path=ref, typer_app=app)
    assert first.changed
    assert "bogus" not in ref.read_text(encoding="utf-8")

    second = generate(check=False, reference_path=ref, typer_app=app)
    assert not second.changed
    assert second.in_sync
