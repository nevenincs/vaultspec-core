"""Guard that the dev-only ``dev/statistics`` package can never ship in the wheel.

The package derives from personal transcript data and is a one-purpose
development instrument, so it must stay outside the distributed artifact.
Shipping exclusion is structural rather than procedural: the hatchling wheel
target packages ``src/vaultspec_core`` exclusively, so anything under ``dev/``
sits outside it by construction. These tests pin that configuration so a future
edit that widened the wheel target - or that added this tree to it - fails
loudly here rather than leaking the module into a release.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def _wheel_packages(pyproject: dict[str, Any]) -> list[str]:
    """Return the configured hatchling wheel package list."""
    return pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def test_wheel_packages_only_vaultspec_core(pyproject: dict[str, Any]) -> None:
    """The wheel target packages exactly ``src/vaultspec_core`` and nothing else."""
    assert _wheel_packages(pyproject) == ["src/vaultspec_core"]


def test_wheel_target_excludes_the_development_tree(pyproject: dict[str, Any]) -> None:
    """No configured wheel package reaches into the ``dev/`` tree."""
    packages = _wheel_packages(pyproject)
    assert all("statistic" not in package for package in packages)
    assert all(not package.startswith("dev") for package in packages)


def test_analytics_package_lives_under_dev_outside_the_wheel_target(
    repo_root: Path,
) -> None:
    """The committed analytics package sits under ``dev/``, outside ``src``."""
    assert (repo_root / "dev" / "statistics" / "__init__.py").is_file()
    assert not (repo_root / "src" / "vaultspec_core" / "statistics").exists()
