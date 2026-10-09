"""Read the latest published release's command and MCP surface back from the release.

The generated references are measured against a committed record of a released
surface. That record may only describe a release a user can install, so it is
taken from the one source that cannot run ahead of publication: the release
GitHub reports as latest - by definition neither a draft nor a prerelease - and
the wheel attached to it, installed in isolation and asked for its own surface.
A source tree is never consulted. The version a tree declares is the
candidate's long before the candidate is a release, and every release that
stopped before publication left that version named as published.

``record`` writes the document through the owning verb and re-renders the
references that cite it. ``emit`` only prints it, which is what the repository
guard compares the committed record against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, cast
from urllib.parse import quote

from dev.environment import child_environment
from dev.packaging.checksums import ChecksumError, read_checksums, require
from dev.packaging.products import VAULTSPEC_CORE, Product

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

GITHUB = "https://github.com/"
SURFACE_IMAGE = (
    "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
    "@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca"
)

# What release code is started with when no container stands between it and
# the caller: enough for `uv` to find itself, its interpreters and the
# libraries they load, its cache and a certificate store, and nothing that
# names a credential.
RELEASE_ENVIRONMENT = frozenset(
    {
        "APPDATA",
        "COMSPEC",
        "DYLD_LIBRARY_PATH",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LD_LIBRARY_PATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "UV_CACHE_DIR",
        "UV_PYTHON_INSTALL_DIR",
        "WINDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)

# Builds the place release code runs in when it is given namespaces of its own.
# It starts as that user namespace's root, with the home directory, the paths
# to keep, `--`, and the command. The home is replaced by an empty one, which
# takes the runner's credentials, every checkout and every other job's files
# out of reach; the kept paths come back read-only.
#
# Staged through the tmpfs that becomes the new home, because a runner's
# temporary directory can sit under the home being replaced. `-n`, because a
# runner's mount table is not always writable, and `mount` reports that as a
# failure after the mount itself has succeeded.
NAMESPACE_SETUP = """\
set -eu
home=$1
shift
stage=$(mktemp -d)
mount -n -t tmpfs -o mode=0700 tmpfs "$stage"
mkdir "$stage/.kept"
index=0
for kept in "$@"; do
  [ "$kept" = "--" ] && break
  mkdir "$stage/.kept/$index"
  mount -n --bind "$kept" "$stage/.kept/$index"
  index=$((index + 1))
done
mount -n --move "$stage" "$home"
index=0
while [ "$1" != "--" ]; do
  mkdir -p "$1"
  mount -n --move "$home/.kept/$index" "$1"
  mount -n -o remount,bind,ro "$1"
  rmdir "$home/.kept/$index"
  index=$((index + 1))
  shift
done
rmdir "$home/.kept"
shift
mkdir "$home/.tmp"
unset XDG_CACHE_HOME XDG_CONFIG_HOME XDG_DATA_HOME UV_PYTHON_INSTALL_DIR
export HOME="$home" TMPDIR="$home/.tmp" UV_CACHE_DIR="$home/.cache/uv"
exec "$@"
"""


class PublishedSurfaceError(RuntimeError):
    """The latest published release could not be read, or did not add up.

    Kept distinct from an assertion so a guard built on this reports an
    unreachable or malformed release as an error rather than as a mismatch:
    one means the record is wrong, the other that the question went unasked.
    """


@dataclass(frozen=True)
class PublishedRelease:
    """The release GitHub reports as latest, and the wheel attached to it."""

    tag: str
    version: str
    wheel: str


def repository(product: Product) -> str:
    """Return ``owner/name`` for the product's GitHub repository."""
    if not product.homepage.startswith(GITHUB):
        raise PublishedSurfaceError(f"{product.name} is not released on GitHub")
    return product.homepage.removeprefix(GITHUB)


def parse_latest_release(
    payload: Mapping[str, object], product: Product
) -> PublishedRelease:
    """Validate a latest-release API payload and name the one wheel it carries.

    The endpoint already excludes drafts and prereleases; the flags are checked
    anyway, because the whole claim rests on them and the payload states them.
    """
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith(product.tag_prefix):
        raise PublishedSurfaceError(
            f"latest release tag {tag!r} is not a {product.name} release tag"
        )
    if payload.get("draft") or payload.get("prerelease"):
        raise PublishedSurfaceError(f"{tag} is a draft or a prerelease")

    raw_assets = payload.get("assets")
    assets = cast("list[object]", raw_assets) if isinstance(raw_assets, list) else []
    wheels = sorted(
        str(cast("Mapping[str, object]", asset).get("name"))
        for asset in assets
        if isinstance(asset, dict)
        and str(cast("Mapping[str, object]", asset).get("name", "")).endswith(".whl")
    )
    if len(wheels) != 1:
        raise PublishedSurfaceError(
            f"{tag} carries {len(wheels)} wheels; exactly one is its distribution"
        )
    wheel = wheels[0]
    # The asset name becomes a URL path segment and a local file name, so it
    # must be a bare name and nothing that could climb out of either.
    if PurePosixPath(wheel).name != wheel or "\\" in wheel:
        raise PublishedSurfaceError(f"{tag} carries a wheel with a path: {wheel!r}")
    if re.fullmatch(r"[A-Za-z0-9_.+-]+", wheel) is None:
        raise PublishedSurfaceError(f"{tag} carries an unsafe wheel name: {wheel!r}")

    return PublishedRelease(tag=tag, version=product.version_from_tag(tag), wheel=wheel)


def fetch_latest_release(product: Product) -> PublishedRelease:
    """Ask GitHub which release is latest.

    Unauthenticated, as a user asks: the repository is public, and a token here
    would be a credential for the one question anybody can answer.
    """
    url = f"https://api.github.com/repos/{repository(product)}/releases/latest"
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload: object = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise PublishedSurfaceError(
            f"GitHub refused {url}: HTTP {exc.code} {exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PublishedSurfaceError(f"GitHub is unreachable at {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PublishedSurfaceError(f"{url} did not answer with a release")
    return parse_latest_release(cast("Mapping[str, object]", payload), product)


def download_wheel(release: PublishedRelease, product: Product, into: Path) -> Path:
    """Download and verify the release's wheel before returning executable bytes."""
    wheel = _download_asset(release, product, into, release.wheel)
    sums = _download_asset(release, product, into, "SHA256SUMS")
    try:
        digests = read_checksums(sums)
        # publish.yml runs sha256sum ./*, so its entries have a literal ./
        # prefix. Accept that spelling and the bare asset name, but never
        # choose between conflicting digests for the same wheel.
        bare = digests.get(release.wheel)
        relative = digests.get(f"./{release.wheel}")
        if bare is not None and relative is not None and bare != relative:
            raise ChecksumError(f"conflicting checksums for {release.wheel!r}")
        expected = require(
            digests, release.wheel if bare is not None else f"./{release.wheel}"
        )
    except (ChecksumError, UnicodeError) as exc:
        raise PublishedSurfaceError(f"invalid release checksums: {exc}") from exc
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
        raise PublishedSurfaceError(f"{release.wheel} does not match SHA256SUMS")
    commit = _release_commit(release, product)
    # Publication runs `publish.yml` from main with the tag as its input, so a
    # wheel's provenance names main and the head it was dispatched at, never
    # the tag or its commit. What binds the wheel to this release is that the
    # head already carried the release commit: a wheel attested for an earlier
    # release was signed before that commit existed.
    try:
        result = subprocess.run(
            [
                "gh",
                "attestation",
                "verify",
                str(wheel),
                "--repo",
                repository(product),
                "--signer-workflow",
                f"{repository(product)}/.github/workflows/publish.yml",
                "--source-ref",
                "refs/heads/main",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise PublishedSurfaceError(
            f"could not run gh attestation verify: {exc}"
        ) from exc
    if result.returncode:
        raise PublishedSurfaceError(
            f"{release.wheel} provenance did not verify: {result.stderr.strip()}"
        )
    if not any(
        _carries_release(product, commit, signed)
        for signed in _attested_commits(release, result.stdout)
    ):
        raise PublishedSurfaceError(
            f"{release.wheel} provenance did not verify: no attestation was "
            f"signed from a commit that carries {release.tag} ({commit})"
        )
    return wheel


def _attested_commits(release: PublishedRelease, verified: str) -> list[str]:
    """Return the workflow commits the verified attestations were signed from."""
    try:
        attestations: object = json.loads(verified)
    except json.JSONDecodeError as exc:
        raise PublishedSurfaceError(
            f"{release.wheel} provenance did not verify: unreadable verifier "
            f"output: {exc}"
        ) from exc
    entries = (
        cast("list[object]", attestations) if isinstance(attestations, list) else []
    )
    commits: list[str] = []
    for entry in entries:
        node: object = entry
        for key in (
            "verificationResult",
            "signature",
            "certificate",
            "sourceRepositoryDigest",
        ):
            node = (
                cast("Mapping[str, object]", node).get(key)
                if isinstance(node, dict)
                else None
            )
        if isinstance(node, str) and re.fullmatch(r"[0-9a-f]{40}", node):
            commits.append(node)
    return commits


def _carries_release(product: Product, commit: str, signed: str) -> bool:
    """Say whether the signing commit is the release commit or descends from it."""
    if signed == commit:
        return True
    url = (
        f"https://api.github.com/repos/{repository(product)}/compare/"
        f"{commit}...{signed}"
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload: object = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PublishedSurfaceError(
            f"could not compare {signed} with the release commit: {exc}"
        ) from exc
    status = (
        cast("Mapping[str, object]", payload).get("status")
        if isinstance(payload, dict)
        else None
    )
    return status == "ahead"


def _release_commit(release: PublishedRelease, product: Product) -> str:
    """Resolve the tag to its commit, including annotated tags, without execution."""
    url = (
        f"https://api.github.com/repos/{repository(product)}/commits/"
        f"{quote(release.tag, safe='')}"
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload: object = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PublishedSurfaceError(f"could not resolve release commit: {exc}") from exc
    commit = (
        cast("Mapping[str, object]", payload).get("sha")
        if isinstance(payload, dict)
        else None
    )
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise PublishedSurfaceError(f"{release.tag} did not resolve to a commit")
    return commit


def _download_asset(
    release: PublishedRelease, product: Product, into: Path, name: str
) -> Path:
    """Download a validated asset name from the fixed release origin.

    The origin is written here as literal text and only the validated asset
    name is interpolated, so no payload value can choose the scheme or host.
    """
    url = (
        f"{GITHUB}{repository(product)}/releases/download/"
        f"{quote(release.tag, safe='')}/{quote(name, safe='')}"
    )
    target = into / name
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PublishedSurfaceError(f"could not download {url}: {exc}") from exc
    return target


def namespace_command(
    command: Sequence[str], home: PurePosixPath, kept: Iterable[PurePosixPath]
) -> list[str]:
    """Wrap *command* to run behind an empty home, in namespaces of its own.

    A new pid namespace with its own ``/proc`` matters as much as the home:
    the caller's environment, token included, is readable from ``/proc`` by
    any process of the same user that can see the caller.

    Parents are restored before the paths beneath them, so a kept directory
    is never covered by a kept ancestor.
    """
    ordered = sorted(set(kept), key=lambda path: (len(path.parts), str(path)))
    for path in ordered:
        if path == home or path in home.parents:
            raise PublishedSurfaceError(
                f"{path} holds the home directory, so keeping it would hide nothing"
            )
    return [
        "unshare",
        "--user",
        "--map-root-user",
        "--mount",
        "--pid",
        "--fork",
        "--mount-proc",
        "sh",
        "-c",
        NAMESPACE_SETUP,
        "sh",
        str(home),
        *(str(path) for path in ordered),
        "--",
        *command,
    ]


def emit_surface(
    wheel: Path, *, container: bool = False, namespace: bool = False
) -> str:
    """Return the surface document the wheel reports for itself.

    ``--isolated --no-project``: a project environment would answer with the
    working tree's surface instead of the wheel's, which is the one answer this
    must never give.
    """
    if container and namespace:
        raise PublishedSurfaceError("choose a container or namespaces, not both")
    command = [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(wheel),
        "vaultspec-core",
        "spec",
        "reference",
        "snapshot",
        "--emit",
    ]
    if container:
        # Only the wheel crosses this boundary. No host environment, checkout,
        # Docker socket, credential directory or Actions runtime token is mounted.
        command[5] = f"/wheel/{wheel.name}"
        command = [
            "docker",
            "run",
            "--rm",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,exec",
            "--env",
            "UV_CACHE_DIR=/tmp/uv-cache",
            "--mount",
            f"type=bind,source={wheel.resolve()},target=/wheel/{wheel.name},readonly",
            SURFACE_IMAGE,
            *command,
        ]
    if namespace:
        # Linux only: the fleet's Linux runners expose no container runtime
        # to a job, and unprivileged namespaces are what they do allow.
        if sys.platform != "linux":
            raise PublishedSurfaceError("namespace isolation needs Linux")
        home = child_environment().get("HOME")
        uv = shutil.which("uv")
        if not home or uv is None:
            raise PublishedSurfaceError(
                "namespace isolation needs HOME, and uv on PATH"
            )
        # The interpreter is named outright, because discovery would look in
        # the home that is about to be emptied.
        base = Path(sys.base_prefix).resolve()
        interpreter = (
            base / "bin" / f"python{sys.version_info[0]}.{sys.version_info[1]}"
        )
        command = namespace_command(
            [
                str(Path(uv).resolve()),
                *command[1:4],
                "--python",
                str(interpreter),
                "--with",
                str(wheel.resolve()),
                *command[6:],
            ],
            PurePosixPath(Path(home).resolve()),
            [
                PurePosixPath(Path(uv).resolve().parent),
                PurePosixPath(base),
                PurePosixPath(wheel.resolve().parent),
            ],
        )
    # The caller holds a token for the provenance lookup; the release's own
    # code is not handed it, or anything else the job was given. A container
    # starts from its image's environment, so there is nothing to withhold.
    environment = (
        None
        if container
        else {
            name: value
            for name, value in child_environment().items()
            if name.upper() in RELEASE_ENVIRONMENT
        }
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=environment,
        )
    except OSError as exc:
        raise PublishedSurfaceError(f"could not run {command[0]}: {exc}") from exc
    if result.returncode != 0:
        raise PublishedSurfaceError(
            f"{wheel.name} did not emit its surface (exit {result.returncode}):\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout


def read_published_surface(
    product: Product,
    workdir: Path,
    *,
    container: bool = False,
    namespace: bool = False,
) -> tuple[PublishedRelease, str]:
    """Return the latest published release and the surface its wheel emits.

    The document's own version must be the one the tag names: a wheel that
    reports another version is not that release's distribution, and recording
    its surface under the tag would be the falsehood this module removes.
    """
    release = fetch_latest_release(product)
    document = emit_surface(
        download_wheel(release, product, workdir),
        container=container,
        namespace=namespace,
    )
    validate_document(release, document)
    return release, document


def validate_document(release: PublishedRelease, document: str) -> None:
    """Require data to name the selected release before recording it."""
    try:
        declared = cast("Mapping[str, object]", json.loads(document)).get("version")
    except (json.JSONDecodeError, AttributeError) as exc:
        raise PublishedSurfaceError(
            f"{release.wheel} emitted no surface document: {exc}"
        ) from exc
    if declared != release.version:
        raise PublishedSurfaceError(
            f"{release.wheel} declares {declared!r}, but {release.tag} names "
            f"{release.version}"
        )


def _vaultspec_core(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "vaultspec_core", *args], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("record", "emit"),
        help=(
            "record: write the surface as the committed snapshot and re-render "
            "the references; emit: print the surface document"
        ),
    )
    parser.add_argument(
        "--container",
        action="store_true",
        help="execute the verified wheel in a credential-free Docker container",
    )
    parser.add_argument(
        "--namespace",
        action="store_true",
        help=(
            "execute the verified wheel in Linux namespaces of its own, behind "
            "an empty home directory"
        ),
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        help="record previously collected JSON data without executing release code",
    )
    args = parser.parse_args(argv)
    if args.container and args.namespace:
        parser.error("--container and --namespace are alternatives")
    if args.from_file and (args.action != "record" or args.container or args.namespace):
        parser.error("--from-file is only valid for record, with no isolation flag")

    with tempfile.TemporaryDirectory(prefix="published-surface-") as scratch:
        workdir = Path(scratch)
        try:
            if args.from_file:
                release = fetch_latest_release(VAULTSPEC_CORE)
                document = args.from_file.read_text(encoding="utf-8")
                validate_document(release, document)
            else:
                release, document = read_published_surface(
                    VAULTSPEC_CORE,
                    workdir,
                    container=args.container,
                    namespace=args.namespace,
                )
        except PublishedSurfaceError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.action == "emit":
            sys.stdout.write(document)
            return 0

        surface = workdir / "surface.json"
        surface.write_text(document, encoding="utf-8", newline="\n")
        print(f"latest published release: {release.tag} ({release.wheel})", flush=True)
        _vaultspec_core(
            "spec", "reference", "snapshot", "--record", str(surface), "--development"
        )
        _vaultspec_core("spec", "reference", "generate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
