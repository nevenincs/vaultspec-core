"""Tests for feature-list recency: latest activity and stale filtering.

``vault feature list`` surfaces each feature's latest activity and can
filter to features that have gone stale, so a lead can sweep for dormant
work without cross-referencing the rollup by hand. The workspace-discovery
hint is also covered: a directory without ``.vaultspec/`` whose sibling
carries one points the operator at the right ``--target``.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


def _doc(doc_type: str, feature: str, *, date: str) -> str:
    return (
        "---\n"
        "tags:\n"
        f"  - '#{doc_type}'\n"
        f"  - '#{feature}'\n"
        f"date: '{date}'\n"
        f"modified: '{date}'\n"
        "---\n"
        "\n"
        f"# {feature} {doc_type}\n"
    )


def _build(root: Path) -> None:
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    vault = root / ".vault"
    # A fresh feature (recent) and a stale one (old).
    fresh_date = _dt.date.today().isoformat()
    (vault / "research").mkdir(parents=True, exist_ok=True)
    (vault / "research" / f"{fresh_date}-fresh-feature-research.md").write_text(
        _doc("research", "fresh-feature", date=fresh_date), encoding="utf-8"
    )
    (vault / "research" / "2024-01-01-stale-feature-research.md").write_text(
        _doc("research", "stale-feature", date="2024-01-01"), encoding="utf-8"
    )


def _run(root: Path, *args: str):
    runner = CliRunner(env={"NO_COLOR": "1"})
    return runner.invoke(app, ["-t", str(root), "vault", "feature", "list", *args])


def test_latest_activity_present_in_json(tmp_path: Path) -> None:
    _build(tmp_path)

    result = _run(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    features = {f["name"]: f for f in json.loads(result.output)["data"]["features"]}
    assert features["stale-feature"]["latest_activity"] == "2024-01-01"
    assert features["fresh-feature"]["latest_activity"] is not None


def test_latest_activity_in_human_output(tmp_path: Path) -> None:
    _build(tmp_path)

    result = _run(tmp_path)

    assert result.exit_code == 0, result.output
    assert "2024-01-01" in result.output


def test_stale_days_filters_to_dormant_features(tmp_path: Path) -> None:
    _build(tmp_path)

    result = _run(tmp_path, "--stale-days", "30", "--json")

    assert result.exit_code == 0, result.output
    names = {f["name"] for f in json.loads(result.output)["data"]["features"]}
    assert "stale-feature" in names
    assert "fresh-feature" not in names


def test_workspace_discovery_hint_points_at_sibling(tmp_path: Path) -> None:
    # A bare directory with no .vaultspec/, beside a sibling that has one.
    workspace = tmp_path / "main"
    (workspace / ".vaultspec").mkdir(parents=True, exist_ok=True)
    (workspace / ".vault").mkdir(parents=True, exist_ok=True)
    bare = tmp_path / "feature-branch"
    bare.mkdir()

    runner = CliRunner(env={"NO_COLOR": "1"})
    result = runner.invoke(app, ["-t", str(bare), "status"])

    assert result.exit_code != 0
    assert "Hint:" in result.output
    assert "--target" in result.output
    assert "main" in result.output
