"""Guards for reading the latest release's payload before anything is downloaded.

Each case is a payload that must not become a recorded surface: a release that
is not this product's, one GitHub should never have called latest, and a wheel
set that does not name exactly one distribution. Recording any of them would
put a version in the references that no user installed.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import urllib.request
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from dev.packaging import published_surface as reader
from dev.packaging.products import VAULTSPEC_CORE, Product
from dev.packaging.published_surface import (
    PublishedRelease,
    PublishedSurfaceError,
    parse_latest_release,
    repository,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

WHEEL = "vaultspec_core-0.2.6-py3-none-any.whl"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tag_name": "vaultspec-core-v0.2.6",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": WHEEL},
            {"name": "vaultspec_core-0.2.6.tar.gz"},
            {"name": "SHA256SUMS"},
        ],
    }
    payload.update(overrides)
    return payload


def test_a_published_release_names_its_version_and_its_one_wheel() -> None:
    """The tag's version and the wheel asset are what the recording reads."""
    release = parse_latest_release(_payload(), VAULTSPEC_CORE)

    assert release.tag == "vaultspec-core-v0.2.6"
    assert release.version == "0.2.6"
    assert release.wheel == WHEEL


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_a_draft_or_prerelease_is_refused(flag: str) -> None:
    """Neither is published, whatever endpoint returned it."""
    with pytest.raises(PublishedSurfaceError, match="draft or a prerelease"):
        parse_latest_release(_payload(**{flag: True}), VAULTSPEC_CORE)


def test_another_product_s_tag_is_refused() -> None:
    """A tag outside the product's scheme is not this product's release."""
    with pytest.raises(PublishedSurfaceError, match="not a vaultspec-core release"):
        parse_latest_release(_payload(tag_name="vaultspec-rag-v0.4.11"), VAULTSPEC_CORE)


@pytest.mark.parametrize(
    "assets",
    [
        [{"name": "vaultspec_core-0.2.6.tar.gz"}],
        [{"name": WHEEL}, {"name": "vaultspec_core-0.2.6-py3-none-win_amd64.whl"}],
    ],
    ids=["no-wheel", "two-wheels"],
)
def test_a_release_without_exactly_one_wheel_is_refused(
    assets: list[dict[str, str]],
) -> None:
    """The surface is read from one distribution; none or two is ambiguous."""
    with pytest.raises(PublishedSurfaceError, match="exactly one"):
        parse_latest_release(_payload(assets=assets), VAULTSPEC_CORE)


@pytest.mark.parametrize("name", [f"../{WHEEL}", f"dist\\{WHEEL}"])
def test_a_wheel_name_carrying_a_path_is_refused(name: str) -> None:
    """The asset name becomes a URL segment and a file name, never a path."""
    with pytest.raises(PublishedSurfaceError, match="with a path"):
        parse_latest_release(_payload(assets=[{"name": name}]), VAULTSPEC_CORE)


def test_the_repository_is_derived_from_the_product_homepage() -> None:
    """One declaration of where the product is released, reused here."""
    assert repository(VAULTSPEC_CORE) == "nevenincs/vaultspec-core"


@pytest.mark.parametrize("name", [f"x,{WHEEL}", f"x%2f{WHEEL}", f"x\n{WHEEL}"])
def test_asset_names_cannot_change_url_or_container_mount_syntax(name: str) -> None:
    with pytest.raises(PublishedSurfaceError, match="unsafe wheel name"):
        parse_latest_release(_payload(assets=[{"name": name}]), VAULTSPEC_CORE)


def _verified(*signed: object) -> str:
    """Return verifier output for attestations signed from the given commits."""
    return json.dumps(
        [
            {
                "verificationResult": {
                    "signature": {"certificate": {"sourceRepositoryDigest": commit}}
                }
            }
            for commit in signed
        ]
    )


@pytest.fixture
def release_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    wheel = tmp_path / WHEEL
    wheel.write_bytes(b"release wheel bytes")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(
        f"{digest}  {WHEEL}\n", encoding="utf-8", newline="\n"
    )

    def downloaded(r: PublishedRelease, p: Product, into: Path, name: str) -> Path:
        return into / name

    monkeypatch.setattr(reader, "_download_asset", Mock(side_effect=downloaded))
    monkeypatch.setattr(reader, "_release_commit", Mock(return_value="a" * 40))
    monkeypatch.setattr(
        reader,
        "fetch_latest_release",
        Mock(return_value=parse_latest_release(_payload(), VAULTSPEC_CORE)),
    )
    return tmp_path


@pytest.mark.parametrize(
    "checksums",
    [f"{'0' * 64}  {WHEEL}\n", f"{'0' * 64}  other.whl\n", "malformed\n"],
    ids=["replaced-bytes", "missing-wheel", "malformed-manifest"],
)
def test_bad_checksums_never_reach_verifier_or_execution(
    monkeypatch: pytest.MonkeyPatch, release_files: Path, checksums: str
) -> None:
    (release_files / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PublishedSurfaceError):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    run.assert_not_called()


@pytest.mark.parametrize("failure", ["wrong-workflow", "wrong-ref", "wrong-commit"])
def test_rejected_provenance_never_executes_the_wheel(
    monkeypatch: pytest.MonkeyPatch, release_files: Path, failure: str
) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 1, "", failure))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PublishedSurfaceError, match="provenance did not verify"):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert run.call_count == 1
    assert run.call_args.args[0][:3] == ["gh", "attestation", "verify"]


def test_unavailable_verifier_never_executes_the_wheel(
    monkeypatch: pytest.MonkeyPatch, release_files: Path
) -> None:
    run = Mock(side_effect=FileNotFoundError("gh"))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PublishedSurfaceError, match="could not run gh"):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert run.call_count == 1


@pytest.mark.parametrize("prefix", ["", "./"])
def test_verified_bytes_execute_only_after_full_identity_verification(
    monkeypatch: pytest.MonkeyPatch, release_files: Path, prefix: str
) -> None:
    wheel = release_files / WHEEL
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (release_files / "SHA256SUMS").write_text(
        f"{digest}  {prefix}{WHEEL}\n", encoding="utf-8", newline="\n"
    )
    document = json.dumps({"version": "0.2.6"})
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, _verified("a" * 40), ""),
            subprocess.CompletedProcess([], 0, document, ""),
        ]
    )
    monkeypatch.setattr(subprocess, "run", run)
    _release, actual = reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert actual == document
    verify, execute = [call.args[0] for call in run.call_args_list]
    assert verify == [
        "gh",
        "attestation",
        "verify",
        str(release_files / WHEEL),
        "--repo",
        "nevenincs/vaultspec-core",
        "--signer-workflow",
        "nevenincs/vaultspec-core/.github/workflows/publish.yml",
        "--source-ref",
        "refs/heads/main",
        "--format",
        "json",
    ]
    assert execute[5] == verify[3]


def test_a_wheel_signed_from_a_later_main_commit_carries_its_release(
    monkeypatch: pytest.MonkeyPatch, release_files: Path
) -> None:
    """Publication is dispatched from main's head, which may have moved on."""
    document = json.dumps({"version": "0.2.6"})
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, _verified("c" * 40), ""),
            subprocess.CompletedProcess([], 0, document, ""),
        ]
    )
    monkeypatch.setattr(subprocess, "run", run)
    compare = Mock(return_value=io.BytesIO(json.dumps({"status": "ahead"}).encode()))
    monkeypatch.setattr(urllib.request, "urlopen", compare)
    _release, actual = reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert actual == document
    assert compare.call_args.args[0].endswith(f"/compare/{'a' * 40}...{'c' * 40}")


@pytest.mark.parametrize("status", ["behind", "diverged", "identical", None])
def test_a_wheel_signed_before_its_release_commit_never_executes(
    monkeypatch: pytest.MonkeyPatch, release_files: Path, status: str | None
) -> None:
    """An earlier release's wheel verifies as this repository's, and is not this one."""
    run = Mock(return_value=subprocess.CompletedProcess([], 0, _verified("c" * 40), ""))
    monkeypatch.setattr(subprocess, "run", run)
    compare = Mock(return_value=io.BytesIO(json.dumps({"status": status}).encode()))
    monkeypatch.setattr(urllib.request, "urlopen", compare)
    with pytest.raises(PublishedSurfaceError, match="provenance did not verify"):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert run.call_count == 1


@pytest.mark.parametrize(
    "verified",
    ["", "not json", "[]", "{}", _verified("main"), _verified(None), "[{}]"],
    ids=["empty", "malformed", "none", "object", "ref", "null", "bare"],
)
def test_verifier_output_naming_no_signing_commit_never_executes_the_wheel(
    monkeypatch: pytest.MonkeyPatch, release_files: Path, verified: str
) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, verified, ""))
    monkeypatch.setattr(subprocess, "run", run)
    compare = Mock()
    monkeypatch.setattr(urllib.request, "urlopen", compare)
    with pytest.raises(PublishedSurfaceError, match="provenance did not verify"):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    assert run.call_count == 1
    compare.assert_not_called()


def test_conflicting_checksum_spellings_never_reach_execution(
    monkeypatch: pytest.MonkeyPatch, release_files: Path
) -> None:
    digest = hashlib.sha256((release_files / WHEEL).read_bytes()).hexdigest()
    (release_files / "SHA256SUMS").write_text(
        f"{digest}  {WHEEL}\n{'0' * 64}  ./{WHEEL}\n",
        encoding="utf-8",
        newline="\n",
    )
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PublishedSurfaceError, match="conflicting checksums"):
        reader.read_published_surface(VAULTSPEC_CORE, release_files)
    run.assert_not_called()


def test_container_receives_only_readonly_wheel_and_no_host_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "{}", ""))
    monkeypatch.setattr(subprocess, "run", run)
    reader.emit_surface(tmp_path / WHEEL, container=True)
    command = run.call_args.args[0]
    assert command[:3] == ["docker", "run", "--rm"]
    assert command.count("--mount") == 1
    mount = command[command.index("--mount") + 1]
    assert (
        mount == f"type=bind,source={(tmp_path / WHEEL).resolve()},"
        f"target=/wheel/{WHEEL},readonly"
    )
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert command.count("--env") == 1
    assert command[command.index("--env") + 1] == "UV_CACHE_DIR=/tmp/uv-cache"
    assert not any("TOKEN" in arg or "docker.sock" in arg for arg in command)
    assert run.call_args.kwargs["env"] is None


def test_release_code_is_started_without_the_callers_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The caller needs a token to look provenance up; the release never sees it."""
    for name in (
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
        "UV_PUBLISH_TOKEN",
    ):
        monkeypatch.setenv(name, "never-passed")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LD_LIBRARY_PATH", str(tmp_path / "lib"))
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "{}", ""))
    monkeypatch.setattr(subprocess, "run", run)
    reader.emit_surface(tmp_path / WHEEL)
    environment = run.call_args.kwargs["env"]
    assert "never-passed" not in environment.values()
    assert {name.upper() for name in environment} <= reader.RELEASE_ENVIRONMENT
    assert environment["UV_CACHE_DIR"] == str(tmp_path / "cache")
    # An interpreter built against a shared libpython cannot start without it.
    assert environment["LD_LIBRARY_PATH"] == str(tmp_path / "lib")
    assert any(name.upper() == "PATH" for name in environment)


def test_a_release_that_cannot_be_started_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=FileNotFoundError("uv")))
    with pytest.raises(PublishedSurfaceError, match="could not run uv"):
        reader.emit_surface(tmp_path / WHEEL)


def test_recording_collected_data_does_not_download_or_execute_release_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    surface = tmp_path / "surface.json"
    surface.write_text('{"version":"0.2.6"}', encoding="utf-8")
    monkeypatch.setattr(
        reader,
        "fetch_latest_release",
        Mock(return_value=parse_latest_release(_payload(), VAULTSPEC_CORE)),
    )
    read = Mock(side_effect=AssertionError("release code must not be executed"))
    monkeypatch.setattr(reader, "read_published_surface", read)
    record = Mock()
    monkeypatch.setattr(reader, "_vaultspec_core", record)
    assert reader.main(["record", "--from-file", str(surface)]) == 0
    read.assert_not_called()
    assert record.call_args_list[0].args[:4] == (
        "spec",
        "reference",
        "snapshot",
        "--record",
    )
    assert record.call_args_list[1].args == ("spec", "reference", "generate")


def test_recording_refuses_data_for_a_superseded_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    surface = tmp_path / "surface.json"
    surface.write_text('{"version":"0.2.5"}', encoding="utf-8")
    monkeypatch.setattr(
        reader,
        "fetch_latest_release",
        Mock(return_value=parse_latest_release(_payload(), VAULTSPEC_CORE)),
    )
    record = Mock()
    monkeypatch.setattr(reader, "_vaultspec_core", record)
    assert reader.main(["record", "--from-file", str(surface)]) == 1
    record.assert_not_called()


@pytest.mark.parametrize("payload", [{"sha": "b" * 40}, {"sha": "main"}, []])
def test_release_commit_resolution_requires_a_full_commit_digest(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    response = Mock(return_value=io.BytesIO(json.dumps(payload).encode()))
    monkeypatch.setattr(urllib.request, "urlopen", response)
    release = parse_latest_release(_payload(), VAULTSPEC_CORE)
    if isinstance(payload, dict) and payload == {"sha": "b" * 40}:
        assert reader._release_commit(release, VAULTSPEC_CORE) == "b" * 40
    else:
        with pytest.raises(PublishedSurfaceError, match="did not resolve to a commit"):
            reader._release_commit(release, VAULTSPEC_CORE)
    assert response.call_args.args[0].endswith("/commits/vaultspec-core-v0.2.6")
