"""Guards for the PyApp release-binary builder.

The build itself needs ``cargo``, a Rust target toolchain, and a published
PyPI release, so it is not reproducible in a test. What *is* reproducible - and
what actually breaks releases - is the wiring around it: the tag the release
workflow passes, the entry points the two binaries claim, and the checksum
format the release notes advertise. Each of those is pinned here against the
real file that owns the other half of the contract.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from dev.binaries.build_pyapp import (
    BINARIES,
    PROJECT_NAME,
    PYTHON_VERSION,
    Binary,
    asset_name,
    version_from_tag,
    write_checksum,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

#: Published SHA-256 test vectors, used as an oracle independent of the
#: hashing the function under test performs.
EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC_DIGEST = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("vaultspec-core-v0.1.48", "0.1.48"),
        ("v0.1.48", "0.1.48"),
        ("0.1.48", "0.1.48"),
        ("vaultspec-core-v1.0.0rc1", "1.0.0rc1"),
    ],
)
def test_version_from_tag_strips_the_release_prefix(tag: str, expected: str) -> None:
    """Every tag shape the release pipeline can emit yields the PyPI version."""
    assert version_from_tag(tag) == expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("x86_64-pc-windows-msvc", "vaultspec-core-x86_64-pc-windows-msvc.exe"),
        ("aarch64-pc-windows-msvc", "vaultspec-core-aarch64-pc-windows-msvc.exe"),
        ("x86_64-unknown-linux-gnu", "vaultspec-core-x86_64-unknown-linux-gnu"),
        ("aarch64-apple-darwin", "vaultspec-core-aarch64-apple-darwin"),
        ("x86_64-apple-darwin", "vaultspec-core-x86_64-apple-darwin"),
    ],
)
def test_asset_name_pins_the_published_download_filenames(
    target: str, expected: str
) -> None:
    """These strings are the release download URLs; a change breaks every link."""
    core = next(binary for binary in BINARIES if binary.name == "vaultspec-core")
    assert asset_name(core, target) == expected


def test_asset_names_are_unique_across_binaries_on_one_target() -> None:
    """Two binaries must not collide in ``--outdir`` when built for one triple."""
    target = "x86_64-unknown-linux-gnu"
    names = [asset_name(binary, target) for binary in BINARIES]
    assert len(names) == len(set(names)), names


def test_write_checksum_emits_sha256sum_format(tmp_path: Path) -> None:
    """The sidecar is a real ``sha256sum`` line naming the asset, not the path.

    Asserted over raw bytes on purpose. ``read_text`` applies universal-newline
    translation, so a CRLF sidecar written by a Windows builder reads back as LF
    and the assertion passes over a file that is wrong on disk. Reverting
    ``write_checksum`` to ``write_text`` must fail this test on Windows.
    """
    asset = tmp_path / "vaultspec-core-x86_64-unknown-linux-gnu"
    asset.write_bytes(b"abc")

    checksum = write_checksum(asset)

    assert checksum == asset.with_name(f"{asset.name}.sha256")
    assert checksum.read_bytes() == f"{ABC_DIGEST}  {asset.name}\n".encode()


def test_write_checksum_is_lf_terminated_on_every_build_host(tmp_path: Path) -> None:
    """The sidecar bytes are LF, so the aggregated SHA256SUMS is not mixed.

    Asserted on raw bytes deliberately. The sibling assertion above reads the
    file in text mode, which translates CRLF back to LF on Windows and so
    reports a passing contract for a file that carries the host's endings -
    the exact reason the CRLF defect behind vaultspec-core-v0.1.60's empty
    Scoop hashes shipped under a green suite.
    """
    asset = tmp_path / "vaultspec-core-x86_64-pc-windows-msvc.exe"
    asset.write_bytes(b"abc")

    raw = write_checksum(asset).read_bytes()

    assert b"\r" not in raw
    assert raw == f"{ABC_DIGEST}  {asset.name}\n".encode()


def test_write_checksum_hashes_the_asset_bytes(tmp_path: Path) -> None:
    """Distinct payloads produce their published digests, not a cached one."""
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    filled = tmp_path / "filled.bin"
    filled.write_bytes(b"abc")

    assert write_checksum(empty).read_text(encoding="utf-8").split()[0] == EMPTY_DIGEST
    assert write_checksum(filled).read_text(encoding="utf-8").split()[0] == ABC_DIGEST


@pytest.mark.parametrize("binary", BINARIES, ids=lambda binary: binary.name)
def test_each_binary_declares_exactly_one_execution_mode(binary: Binary) -> None:
    """PyApp's execution modes are mutually exclusive; declaring both is a bug."""
    declared = [value for value in (binary.exec_module, binary.exec_spec) if value]
    assert len(declared) == 1, f"{binary.name} declares {len(declared)} exec modes"

    env = binary.pyapp_exec_env()
    assert list(env) in (["PYAPP_EXEC_MODULE"], ["PYAPP_EXEC_SPEC"])
    assert list(env.values()) == declared


def test_binary_names_are_unique() -> None:
    """Two binaries sharing a name would overwrite each other in ``--outdir``."""
    names = [binary.name for binary in BINARIES]
    assert len(names) == len(set(names)), names


def test_project_name_matches_the_distribution_pyapp_installs(
    pyproject: dict[str, Any],
) -> None:
    """PyApp resolves ``PROJECT_NAME`` from PyPI, so a rename must reach here."""
    assert pyproject["project"]["name"] == PROJECT_NAME


def test_binary_names_match_the_console_scripts_they_stand_in_for(
    pyproject: dict[str, Any],
) -> None:
    """Each binary is the standalone form of a declared console script."""
    console_scripts = set(pyproject["project"]["scripts"])
    assert {binary.name for binary in BINARIES} <= console_scripts


def test_exec_spec_binaries_match_their_console_script_entry_point(
    pyproject: dict[str, Any],
) -> None:
    """An object-reference binary runs exactly what the console script runs."""
    console_scripts: dict[str, str] = pyproject["project"]["scripts"]
    specs = {b.name: b.exec_spec for b in BINARIES if b.exec_spec is not None}
    assert specs, "no binary uses PYAPP_EXEC_SPEC; the guard below is vacuous"
    for name, spec in specs.items():
        assert spec == console_scripts[name]


def test_exec_module_binaries_run_the_package_main_the_console_script_calls(
    pyproject: dict[str, Any],
) -> None:
    """``python -m <module>`` must land on the console script's own entry module."""
    console_scripts: dict[str, str] = pyproject["project"]["scripts"]
    modules = {b.name: b.exec_module for b in BINARIES if b.exec_module is not None}
    assert modules, "no binary uses PYAPP_EXEC_MODULE; the guard below is vacuous"
    for name, module in modules.items():
        entry_module, _, _ = console_scripts[name].partition(":")
        assert entry_module == f"{module}.__main__"


def test_embedded_python_series_satisfies_requires_python(
    pyproject: dict[str, Any],
) -> None:
    """The CPython baked into the binary must be one the package supports."""
    requires: str = pyproject["project"]["requires-python"]
    bounds = dict(re.findall(r"(>=|<)\s*([0-9.]+)", requires))
    assert bounds[">="] == PYTHON_VERSION
    embedded = tuple(int(part) for part in PYTHON_VERSION.split("."))
    upper = tuple(int(part) for part in bounds["<"].split("."))
    assert embedded < upper


def test_the_release_workflow_invokes_this_builder(repo_root: Path) -> None:
    """The script is not orphaned: the binaries workflow is its automated caller."""
    workflow = repo_root / ".github" / "workflows" / "binaries.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "dev/binaries/build_pyapp.py" in text
    assert "--tag" in text
    assert "--outdir" in text


def test_the_justfile_exposes_a_local_build_recipe(repo_root: Path) -> None:
    """A maintainer can reproduce a release build without copying CI's command."""
    text = (repo_root / "justfile").read_text(encoding="utf-8")
    assert "dev/binaries/build_pyapp.py" in text
