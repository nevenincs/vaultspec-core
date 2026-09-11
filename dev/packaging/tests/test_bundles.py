"""Release-bundle contract tests."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from typing import TYPE_CHECKING

import pytest

from dev.packaging.bundles import BundleError, build_bundle, verify_bundle
from dev.packaging.products import VAULTSPEC_CORE

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

TARGETS = ("x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu")


def _raw_outputs(root: Path, target: str) -> Path:
    raw = root / "raw"
    raw.mkdir()
    for index, executable in enumerate(VAULTSPEC_CORE.executables, start=1):
        path = raw / VAULTSPEC_CORE.asset_name(executable, target)
        path.write_bytes(f"executable-{index}".encode())
    return raw


def _tampered_manifest(archive: Path, root: Path, field: str, value: object) -> Path:
    """Return a same-named ZIP bundle with one manifest field changed."""
    with zipfile.ZipFile(archive) as source:
        contents = {name: source.read(name) for name in source.namelist()}
    manifest = json.loads(contents["manifest.json"])
    manifest[field] = value
    contents["manifest.json"] = json.dumps(manifest).encode()

    destination = root / archive.name
    root.mkdir()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, payload in contents.items():
            target.writestr(name, payload)
    return destination


@pytest.mark.parametrize("target", TARGETS)
def test_build_bundle_has_stable_contents_and_manifest(
    tmp_path: Path, target: str
) -> None:
    """Each target archive contains stable names and hashes its members."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "LICENSE").write_text("license\n", encoding="utf-8")
    raw = _raw_outputs(tmp_path, target)

    archive = build_bundle(
        VAULTSPEC_CORE,
        "0.2.1",
        target,
        raw,
        tmp_path / "bundles",
        repo,
        "revision-1",
    )

    if target.endswith("windows-msvc"):
        with zipfile.ZipFile(archive) as handle:
            names = handle.namelist()
            contents = {name: handle.read(name) for name in names}
    else:
        with tarfile.open(archive, "r:gz") as handle:
            members = handle.getmembers()
            names = [member.name for member in members]
            contents = {}
            for member in members:
                if not member.isfile():
                    continue
                payload = handle.extractfile(member)
                assert payload is not None
                contents[member.name] = payload.read()

    expected = {
        "LICENSE",
        "README.txt",
        "manifest.json",
        *(
            VAULTSPEC_CORE.executable_name(executable, target)
            for executable in VAULTSPEC_CORE.executables
        ),
    }
    assert set(names) == expected
    manifest = json.loads(contents["manifest.json"])
    assert manifest["archive"]["name"] == archive.name
    assert manifest["display_name"] == "Vaultspec Core"
    assert manifest["publisher"] == "Gergely Wootsch"
    assert manifest["legal_copyright"] == "Copyright (c) Gergely Wootsch"
    assert manifest["target"] == target
    assert manifest["runtime"]["python"]
    assert manifest["platform"]["glibc_floor"] == (
        "2.28" if target.endswith("linux-gnu") else None
    )
    assert manifest["source_revision"] == "revision-1"
    assert {entry["name"] for entry in manifest["files"]} == expected - {
        "manifest.json"
    }
    for entry in manifest["files"]:
        assert entry["sha256"] == hashlib.sha256(contents[entry["name"]]).hexdigest()
    verify_bundle(archive, VAULTSPEC_CORE, "0.2.1", target)


@pytest.mark.parametrize("target", TARGETS)
def test_build_bundle_is_deterministic(tmp_path: Path, target: str) -> None:
    """Host mtimes do not alter the public archive bytes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "LICENSE").write_text("license\n", encoding="utf-8")
    raw = _raw_outputs(tmp_path, target)
    output = tmp_path / "bundles"

    archive = build_bundle(
        VAULTSPEC_CORE, "0.2.1", target, raw, output, repo, "revision-1"
    )
    first = archive.read_bytes()
    archive = build_bundle(
        VAULTSPEC_CORE, "0.2.1", target, raw, output, repo, "revision-1"
    )

    assert archive.read_bytes() == first


def test_build_bundle_rejects_a_missing_executable(tmp_path: Path) -> None:
    """A bundle cannot silently omit one of the product's commands."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "LICENSE").write_text("license\n", encoding="utf-8")

    with pytest.raises(BundleError, match="missing finalized executable"):
        build_bundle(
            VAULTSPEC_CORE,
            "0.2.1",
            "x86_64-pc-windows-msvc",
            tmp_path / "raw",
            tmp_path / "bundles",
            repo,
            "revision-1",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_revision", "", "source revision"),
        ("runtime", {}, "runtime metadata"),
        ("platform", {}, "platform metadata"),
    ],
)
def test_verify_bundle_rejects_missing_contract_metadata(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    """All generated metadata sections are required at the release edge."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "LICENSE").write_text("license\n", encoding="utf-8")
    raw = _raw_outputs(tmp_path, "x86_64-pc-windows-msvc")
    archive = build_bundle(
        VAULTSPEC_CORE,
        "0.2.1",
        "x86_64-pc-windows-msvc",
        raw,
        tmp_path / "bundles",
        repo,
        "revision-1",
    )
    tampered = _tampered_manifest(archive, tmp_path / "tampered", field, value)

    with pytest.raises(BundleError, match=message):
        verify_bundle(
            tampered,
            VAULTSPEC_CORE,
            "0.2.1",
            "x86_64-pc-windows-msvc",
        )
