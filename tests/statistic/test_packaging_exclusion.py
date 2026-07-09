"""Guard that the dev-only ``statistic/`` package can never ship in the wheel.

The ``statistic/`` package derives from personal transcript data and is a
one-purpose development instrument, so it must stay outside the distributed
artifact. Shipping exclusion is structural rather than procedural: the
hatchling wheel target packages ``src/vaultspec_core`` exclusively, so any
repo-root package sits outside it by construction. These tests pin that
configuration so a future edit that widened the wheel target - or that added
``statistic`` to it - fails loudly here rather than leaking the module into a
release.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_pyproject() -> dict[str, Any]:
    """Load and parse the repository ``pyproject.toml``."""
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _wheel_packages() -> list[str]:
    """Return the configured hatchling wheel package list."""
    config = _load_pyproject()
    return config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def test_wheel_packages_only_vaultspec_core() -> None:
    """The wheel target packages exactly ``src/vaultspec_core`` and nothing else."""
    assert _wheel_packages() == ["src/vaultspec_core"]


def test_wheel_target_excludes_statistic() -> None:
    """No configured wheel package references the ``statistic`` module."""
    assert all("statistic" not in package for package in _wheel_packages())


def test_statistic_package_lives_at_repo_root_outside_wheel_target() -> None:
    """The committed ``statistic`` package sits at the repo root, outside ``src``."""
    statistic_init = _REPO_ROOT / "statistic" / "__init__.py"
    assert statistic_init.is_file()
    assert not (_REPO_ROOT / "src" / "vaultspec_core" / "statistic").exists()
