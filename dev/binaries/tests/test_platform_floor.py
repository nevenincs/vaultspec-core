"""Guards for the declared platform floor of the release binaries.

A Linux artifact's minimum glibc is not chosen by anything in this repository
unless something asserts it: the linker records whatever the build machine's
libc offers, the loader refuses the binary on anything older, and no test the
project runs on its own source can see it. The floor is therefore a property of
the artifact, and these guards read it out of the artifact.

The two ELF fixtures are real binaries, not synthesised byte strings, so the
parser is exercised against output a linker actually produced. Their expected
version sets were read with ``readelf -V`` at the time they were built - an
independent reader, so the assertions below are not the parser agreeing with
itself:

- ``low-floor.elf``  built in ``quay.io/pypa/manylinux_2_28_x86_64`` (glibc 2.28)
- ``high-floor.elf`` built on a glibc 2.43 host, which is what an unpinned
  build looks like; its ``GLIBC_2.38`` requirements are the ``__isoc23_*``
  symbols a modern libc substitutes for ``strtol`` and ``sscanf``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dev.binaries.build_pyapp import (
    GLIBC_FLOOR,
    PlatformFloorError,
    check_platform_floor,
    glibc_version,
    required_symbol_versions,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"

#: Read with ``readelf -V`` when the fixtures were built.
LOW_FLOOR_VERSIONS = {"GLIBC_2.2.5", "GLIBC_2.7"}
HIGH_FLOOR_VERSIONS = {
    "GLIBC_2.2.5",
    "GLIBC_2.3.4",
    "GLIBC_2.4",
    "GLIBC_2.34",
    "GLIBC_2.38",
}

#: RHEL 9 and its rebuilds ship glibc 2.34 and are the oldest platform the
#: install documentation names, so a floor above this silently drops them.
OLDEST_SUPPORTED_GLIBC = (2, 34)

LINUX_TARGET = "x86_64-unknown-linux-gnu"


def _glibc_only(asset: Path) -> set[str]:
    return {
        requirement
        for requirement in required_symbol_versions(asset)
        if requirement.startswith("GLIBC_")
    }


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("low-floor.elf", LOW_FLOOR_VERSIONS),
        ("high-floor.elf", HIGH_FLOOR_VERSIONS),
    ],
)
def test_symbol_versions_match_an_independent_reader(
    fixture: str, expected: set[str]
) -> None:
    """The parser reproduces what ``readelf -V`` reported for the same file."""
    assert _glibc_only(FIXTURES / fixture) == expected


def test_a_binary_above_the_floor_is_rejected() -> None:
    """This is the shipped failure: an artifact that cannot load where promised.

    ``high-floor.elf`` requires ``GLIBC_2.38``. Raising ``GLIBC_FLOOR`` for the
    Linux target above that - or dropping the target from the table - makes this
    pass while the artifact stays unloadable, so neither is a valid repair.
    """
    with pytest.raises(PlatformFloorError) as excinfo:
        check_platform_floor(FIXTURES / "high-floor.elf", LINUX_TARGET)

    message = str(excinfo.value)
    assert "GLIBC_2.38" in message
    assert LINUX_TARGET in message


def test_a_binary_within_the_floor_is_accepted() -> None:
    """A build against the declared baseline passes; the guard is not blanket."""
    check_platform_floor(FIXTURES / "low-floor.elf", LINUX_TARGET)


def test_a_target_declaring_no_floor_is_not_inspected() -> None:
    """macOS and Windows pin their floor elsewhere; ELF parsing is meaningless."""
    check_platform_floor(FIXTURES / "high-floor.elf", "aarch64-apple-darwin")
    check_platform_floor(FIXTURES / "high-floor.elf", "x86_64-pc-windows-msvc")


def test_a_non_elf_input_is_rejected_rather_than_silently_passing(
    tmp_path: Path,
) -> None:
    """A parser that returns nothing on garbage would pass every artifact."""
    impostor = tmp_path / "vaultspec-core-x86_64-unknown-linux-gnu"
    impostor.write_bytes(b"MZ not an elf at all")

    with pytest.raises(PlatformFloorError, match="not an ELF binary"):
        check_platform_floor(impostor, LINUX_TARGET)


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("GLIBC_2.39", (2, 39)),
        ("GLIBC_2.2.5", (2, 2, 5)),
        ("GLIBC_2.4", (2, 4)),
        ("GCC_3.0", None),
        ("GLIBC_PRIVATE", None),
    ],
)
def test_glibc_version_parses_only_numeric_glibc_requirements(
    requirement: str, expected: tuple[int, ...] | None
) -> None:
    """``GLIBC_PRIVATE`` sits beside the numbered versions and is not one."""
    assert glibc_version(requirement) == expected


def test_versions_are_ordered_numerically_and_not_lexically() -> None:
    """Compared as strings, ``GLIBC_2.9`` outranks ``GLIBC_2.28``. It must not.

    ``low-floor.elf`` requires ``GLIBC_2.7`` and is accepted against a 2.28
    floor, so a lexical comparison is already excluded by that fixture. This
    pins the parse the comparison rests on, and spells out the trap.
    """
    assert glibc_version("GLIBC_2.28") == (2, 28)
    assert glibc_version("GLIBC_2.9") == (2, 9)
    assert glibc_version("GLIBC_2.3.4") == (2, 3, 4)
    assert sorted(["GLIBC_2.28", "GLIBC_2.9"])[-1] == "GLIBC_2.9"


def test_the_declared_floor_reaches_the_oldest_documented_platform() -> None:
    """A floor above RHEL 9's glibc drops a platform the docs still name."""
    assert GLIBC_FLOOR, "no target declares a floor; the check would be vacuous"
    for target, floor in GLIBC_FLOOR.items():
        assert floor <= OLDEST_SUPPORTED_GLIBC, target


def test_every_linux_gnu_target_built_by_ci_declares_a_floor(
    repo_root: Path,
) -> None:
    """A new Linux leg must not escape the check by omission from the table."""
    workflow = yaml.safe_load(
        (repo_root / ".github" / "workflows" / "binaries.yml").read_text(
            encoding="utf-8"
        )
    )
    legs: list[dict[str, str]] = workflow["jobs"]["build"]["strategy"]["matrix"][
        "include"
    ]
    targets = [leg["target"] for leg in legs if leg["target"].endswith("linux-gnu")]
    assert targets, "no Linux target in the matrix; this guard is vacuous"
    for target in targets:
        assert target in GLIBC_FLOOR, f"{target} is built but declares no floor"
