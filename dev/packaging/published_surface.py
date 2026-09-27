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
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, cast

from dev.packaging.products import VAULTSPEC_CORE, Product

if TYPE_CHECKING:
    from collections.abc import Mapping

GITHUB = "https://github.com/"


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
    """Download the release's wheel into *into* and return its path.

    The origin is written here as literal text and only the validated asset
    name is interpolated, so no payload value can choose the scheme or host.
    """
    url = (
        f"{GITHUB}{repository(product)}/releases/download/{release.tag}/{release.wheel}"
    )
    target = into / release.wheel
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PublishedSurfaceError(f"could not download {url}: {exc}") from exc
    return target


def emit_surface(wheel: Path) -> str:
    """Return the surface document the wheel reports for itself.

    ``--isolated --no-project``: a project environment would answer with the
    working tree's surface instead of the wheel's, which is the one answer this
    must never give.
    """
    result = subprocess.run(
        [
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
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise PublishedSurfaceError(
            f"{wheel.name} did not emit its surface (exit {result.returncode}):\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout


def read_published_surface(
    product: Product, workdir: Path
) -> tuple[PublishedRelease, str]:
    """Return the latest published release and the surface its wheel emits.

    The document's own version must be the one the tag names: a wheel that
    reports another version is not that release's distribution, and recording
    its surface under the tag would be the falsehood this module removes.
    """
    release = fetch_latest_release(product)
    document = emit_surface(download_wheel(release, product, workdir))
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
    return release, document


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
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="published-surface-") as scratch:
        workdir = Path(scratch)
        try:
            release, document = read_published_surface(VAULTSPEC_CORE, workdir)
        except PublishedSurfaceError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.action == "emit":
            sys.stdout.write(document)
            return 0

        surface = workdir / "surface.json"
        surface.write_text(document, encoding="utf-8", newline="\n")
        print(f"latest published release: {release.tag} ({release.wheel})", flush=True)
        _vaultspec_core("spec", "reference", "snapshot", "--record", str(surface))
        _vaultspec_core("spec", "reference", "generate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
