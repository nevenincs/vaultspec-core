"""Refuse to publish a channel pointer that a package manager cannot install.

vaultspec-core-v0.1.60 shipped a Scoop manifest carrying the right version and
the right URLs alongside ``"hash": ["", ""]``. The release job was green, the
unit tests were green, and nothing looked at what had been written. The
generator is unit-tested against synthetic input; what was missing was an
assertion on the REAL pointer, at the moment it is produced.

That assertion used to live in ``tests/test_committed_channels.py`` and read
this repository's own ``bucket/`` and ``Formula/``. Those directories are gone:
channel roots are per-account, not per-product, so the pointers a user installs
now live in ``nevenincs/homebrew-tap``. The test kept passing against files
nothing wrote any more, which is a worse failure than not having it - green,
and guarding nothing.

So the check moved twice: out of this repository's tree, and earlier in time.
It now runs against whatever root the release generated into, between writing
the pointers and committing them, which is the only point where a bad pointer
can still be stopped rather than merely reported.

Offline by construction. Verifying a digest against the release would need the
network; what is checked is internal consistency - well-formed digests,
agreement between the two channels, and agreement with the asset names the
build matrix can actually produce.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dev.binaries.build_pyapp import BINARIES, asset_name
from dev.packaging import products
from dev.packaging.generate import formula_path, scoop_path
from dev.packaging.pointer import existing_homebrew_version, existing_scoop_version

if TYPE_CHECKING:
    from dev.packaging.products import Product

SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: This repository (``dev/packaging/`` -> ``dev/`` -> repo), where the build
#: matrix lives. Distinct from the CHANNEL root, which is a tap checkout.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The workflow whose matrix decides what this repository can actually build.
_WORKFLOW = Path(".github") / "workflows" / "binaries.yml"

#: A matrix row's `target: <triple>`.
_MATRIX_TARGET = re.compile(r"^\s+target:\s+(\S+)\s*$", re.MULTILINE)


class UnknownTargetsError(RuntimeError):
    """The build matrix could not be read, so nothing can be called buildable."""


def buildable_targets(repo_root: Path) -> tuple[str, ...]:
    """The triples the build matrix declares, read from the matrix itself.

    This was a hand-written list of all five triples the products module knows,
    and that made the check weaker than it looks: the matrix builds three, so a
    pointer naming `x86_64-apple-darwin` passed validation even though nothing
    emits it - which is exactly the asset #372 removes, and exactly the one that
    is broken in production. A checker that would approve the artifact its own
    repository is in the middle of withdrawing is not checking much.

    So it is derived, like the release guard's target list and the preflight's
    selectors before it. Three hand-kept lists in one repository drifted from
    this same matrix; the answer each time was to stop keeping a second copy.
    """
    try:
        text = (repo_root / _WORKFLOW).read_text(encoding="utf-8")
    except OSError as exc:
        raise UnknownTargetsError(f"cannot read {_WORKFLOW}: {exc}") from exc
    targets = tuple(sorted(set(_MATRIX_TARGET.findall(text))))
    if not targets:
        raise UnknownTargetsError(
            f"{_WORKFLOW} declares no build target; refusing to treat every "
            f"asset name as unbuildable on the strength of a parse failure",
        )
    return targets


def _buildable_asset_names(repo_root: Path) -> set[str]:
    return {
        asset_name(binary, target)
        for binary in BINARIES
        for target in buildable_targets(repo_root)
    }


def _string_list(manifest: dict[str, object], key: str) -> list[str]:
    """The manifest's ``key`` as a list of strings, however it was written.

    ``json.loads`` returns ``Any``, so anything read out of it is untyped from
    that point on - and this module's whole job is to be certain about the
    contents of a file it did not write. Narrowing at the boundary keeps the
    checks below concrete, and a manifest whose `hash` is a string rather than
    a list stops being a type error and becomes a finding.
    """
    value = manifest.get(key)
    if isinstance(value, list):
        return [str(item) for item in cast("list[object]", value)]
    if isinstance(value, str):
        return [value]
    return []


def _read_manifest(path: Path) -> dict[str, object]:
    """The Scoop manifest as a mapping, or empty when it is not one at all.

    The ``isinstance`` is the real check - a manifest that is not a JSON object
    becomes a reported finding rather than an exception. The ``cast`` only
    tells the type checker what that check established, which is the idiom this
    repository already uses for parsed data it did not write.
    """
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return {}
    return cast("dict[str, object]", parsed)


def validate(root: Path, product: Product, repo_root: Path | None = None) -> list[str]:
    """Return every reason these channel pointers are unfit to publish.

    ``root`` is the CHANNEL root - a checkout of the account tap. ``repo_root``
    is this repository, where the build matrix lives; the two are different
    trees and conflating them is what produced the stale in-repo copies this
    module exists alongside.

    A list rather than an exception: a half-generated pair usually breaks in
    more than one way, and reporting the first only sends the maintainer round
    the loop again.
    """
    repo_root = REPO_ROOT if repo_root is None else repo_root
    problems: list[str] = []
    manifest_path = scoop_path(root, product)
    formula_path_ = formula_path(root, product)

    for path in (manifest_path, formula_path_):
        if not path.is_file():
            problems.append(f"{path} does not exist")
    if problems:
        return problems

    manifest = _read_manifest(manifest_path)
    formula = formula_path_.read_text(encoding="utf-8")
    if not manifest:
        problems.append(f"{manifest_path}: is not a JSON object")
        return problems

    # (a) the 0.1.60 failure itself - a pointer with blank digests.
    hashes = _string_list(manifest, "hash")
    urls = _string_list(manifest, "url")
    if not hashes:
        problems.append(f"{manifest_path}: pins no hashes")
    if len(hashes) != len(urls):
        problems.append(
            f"{manifest_path}: {len(hashes)} hash(es) for {len(urls)} url(s)",
        )
    problems.extend(
        f"{manifest_path}: not a sha256 digest: {digest!r}"
        for digest in hashes
        if not SHA256.match(digest)
    )

    digests = re.findall(r'sha256 "([^"]*)"', formula)
    if not digests:
        problems.append(f"{formula_path_}: pins no digests")
    problems.extend(
        f"{formula_path_}: not a sha256 digest: {digest!r}"
        for digest in digests
        if not SHA256.match(digest)
    )

    # (b) the two channels are generated from one aggregate, so a divergence
    #     means one was hand-edited or a generation half-failed.
    scoop_version = existing_scoop_version(manifest_path)
    brew_version = existing_homebrew_version(formula_path_)
    if scoop_version is None:
        problems.append(f"{manifest_path}: names no version")
    if brew_version is None:
        problems.append(f"{formula_path_}: names no version")
    if scoop_version is not None and scoop_version != brew_version:
        problems.append(
            f"channels disagree: scoop={scoop_version} homebrew={brew_version}",
        )

    # (c) every asset pointed at is one the builder can emit. A typo here is a
    #     404 at install time and nowhere earlier.
    referenced = {url.rsplit("/", 1)[-1] for url in urls}
    referenced |= set(re.findall(r'url "[^"]*/([^"/]+)"', formula))
    try:
        buildable = _buildable_asset_names(repo_root)
    except UnknownTargetsError as exc:
        # Not "assume everything is fine". An unreadable matrix means the
        # question cannot be answered, and answering it anyway - in either
        # direction - is how a check starts lying.
        problems.append(f"cannot determine what this repository builds: {exc}")
    else:
        unbuildable = sorted(referenced - buildable)
        problems.extend(
            f"names an asset no build produces: {name}" for name in unbuildable
        )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="the channel root to validate (the tap checkout, not this repo)",
    )
    parser.add_argument(
        "--product",
        default=products.VAULTSPEC_CORE.name,
        choices=sorted(products.PRODUCTS),
        help="which product's channels to validate",
    )
    args = parser.parse_args()
    product = products.PRODUCTS[args.product]

    try:
        targets = buildable_targets(REPO_ROOT)
    except UnknownTargetsError as exc:
        print(f"::error::{exc}", file=sys.stderr, flush=True)
        return 1
    print(f"matrix builds: {', '.join(targets)}", flush=True)

    problems = validate(args.root, product)
    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr, flush=True)
        print(
            f"::error::refusing to publish {product.name} channel pointers "
            f"from {args.root}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(f"channel pointers for {product.name} are well-formed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
