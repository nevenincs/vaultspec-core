"""Tests for shipped package metadata and console script names."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.repo]


def test_project_scripts_ship_vaultspec_core_and_mcp(pyproject: dict[str, Any]) -> None:
    scripts: dict[str, str] = pyproject["project"]["scripts"]

    assert "vaultspec-core" in scripts
    assert scripts["vaultspec-core"] == "vaultspec_core.__main__:main"
    assert "vaultspec-mcp" in scripts
    assert scripts["vaultspec-mcp"] == "vaultspec_core.mcp_server.app:run"
    assert "vaultspec" not in scripts
