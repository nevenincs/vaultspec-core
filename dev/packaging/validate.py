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
from typing import TYPE_CHECKING

from dev.binaries.build_pyapp import BINARIES, asset_name
from dev.packaging import products
from dev.packaging.generate import formula_path, scoop_path
from dev.packaging.pointer import existing_homebrew_version, existing_scoop_version

if TYPE_CHECKING:
    from dev.packaging.products import Product

SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: Every triple any product may ship. A pointer naming something outside this
#: set names an asset no build can emit, so it would 404 on install.
_ALL_TARGETS = (
    products.WINDOWS_X86_64,
    products.MACOS_ARM64,
    products.MACOS_X86_64,
    products.LINUX_X86_64,
    products.LINUX_ARM64,
)


def _buildable_asset_names() -> set[str]:
    return {
        asset_name(binary, target) for binary in BINARIES for target in _ALL_TARGETS
    }


def validate(root: Path, product: Product) -> list[str]:
    """Return every reason these channel pointers are unfit to publish.

    A list rather than an exception: a half-generated pair usually breaks in
    more than one way, and reporting the first only sends the maintainer round
    the loop again.
    """
    problems: list[str] = []
    manifest_path = scoop_path(root, product)
    formula_path_ = formula_path(root, product)

    for path in (manifest_path, formula_path_):
        if not path.is_file():
            problems.append(f"{path} does not exist")
    if problems:
        return problems

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    formula = formula_path_.read_text(encoding="utf-8")

    # (a) the 0.1.60 failure itself - a pointer with blank digests.
    hashes = manifest.get("hash") or []
    if not hashes:
        problems.append(f"{manifest_path}: pins no hashes")
    if len(hashes) != len(manifest.get("url") or []):
        problems.append(
            f"{manifest_path}: {len(hashes)} hash(es) for "
            f"{len(manifest.get('url') or [])} url(s)",
        )
    problems.extend(
        f"{manifest_path}: not a sha256 digest: {digest!r}"
        for digest in hashes
        if not SHA256.match(str(digest))
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
    referenced = {str(url).rsplit("/", 1)[-1] for url in manifest.get("url") or []}
    referenced |= set(re.findall(r'url "[^"]*/([^"/]+)"', formula))
    unbuildable = sorted(referenced - _buildable_asset_names())
    problems.extend(f"names an asset no build produces: {name}" for name in unbuildable)

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
