#!/usr/bin/env python
"""Generate this release's Scoop manifest and Homebrew formula.

Invoked by the release job in ``.github/workflows/binaries.yml`` once the
binaries are attached, and reproducible locally against a published release::

    uv run --frozen python -m dev.packaging.generate \\
        --tag vaultspec-core-v0.1.60 --checksums dist-bin/SHA256SUMS

The command replaces an inline ``jq`` rewrite that edited the committed
manifest in place. That mattered: the shell version looked up digests with
``awk``, wrote whatever it found, and its ``test -n`` guard was inert under
``set -e`` (bash exempts every command in an ``&&`` list except the one after
the final ``&&``), so a lookup that found nothing produced a manifest with
empty hashes and a green run. Here a missing digest raises, an unbuilt target
is omitted rather than invented, and a backward bump is refused.

Exit status is non-zero on any refusal, so the workflow step fails loudly
instead of committing a pointer a user would install and fail against.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from dev.packaging import homebrew, products, scoop
from dev.packaging.checksums import ChecksumError, read_checksums
from dev.packaging.pointer import (
    PointerError,
    check_forward,
    existing_homebrew_version,
    existing_scoop_version,
)

if TYPE_CHECKING:
    from dev.packaging.products import Product

#: Repository root (``dev/packaging/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]


def scoop_path(root: Path, product: Product) -> Path:
    """Return the committed Scoop manifest path for one product."""
    return root / "bucket" / f"{product.name}.json"


def formula_path(root: Path, product: Product) -> Path:
    """Return the committed Homebrew formula path for one product."""
    return root / "Formula" / f"{product.name}.rb"


def available_targets(product: Product, digests: dict[str, str]) -> tuple[str, ...]:
    """Return the Homebrew triples this release actually attached.

    A triple counts as available only when EVERY executable was published for
    it. A half-built target would otherwise render a formula whose primary
    download resolves and whose resource 404s at install time.
    """
    return tuple(
        target
        for target in products.HOMEBREW_TARGETS
        if all(
            product.asset_name(executable, target) in digests
            for executable in product.executables
        )
    )


def _write(path: Path, content: str) -> None:
    """Write generated channel content with committed-file line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def generate(root: Path, product: Product, tag: str, checksums: Path) -> list[Path]:
    """Write both channel pointers for one release and return their paths."""
    version = product.version_from_tag(tag)
    if not version:
        raise SystemExit(f"tag {tag!r} names no version")
    digests = read_checksums(checksums)

    manifest = scoop_path(root, product)
    formula = formula_path(root, product)
    check_forward(existing_scoop_version(manifest), version)
    check_forward(existing_homebrew_version(formula), version)

    targets = available_targets(product, digests)
    if not targets:
        raise SystemExit(
            f"release {tag} attached no complete Homebrew target; "
            f"SHA256SUMS lists: {', '.join(sorted(digests))}",
        )
    missing = tuple(
        target for target in products.HOMEBREW_TARGETS if target not in targets
    )
    if missing:
        # Not fatal: a gap in the build matrix is a delivery gap to report,
        # not a reason to withhold the platforms that DID build.
        print(f"::warning::no Homebrew coverage for: {', '.join(missing)}", flush=True)

    _write(manifest, scoop.render(product, version, digests))
    _write(formula, homebrew.render(product, version, digests, targets))
    return [manifest, formula]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag", required=True, help="release tag, e.g. vaultspec-core-v0.1.60"
    )
    parser.add_argument(
        "--checksums",
        required=True,
        type=Path,
        help="the release's aggregated SHA256SUMS",
    )
    parser.add_argument(
        "--product",
        default=products.VAULTSPEC_CORE.name,
        choices=sorted(products.PRODUCTS),
        help="which product's channels to generate",
    )
    parser.add_argument(
        "--root", default=ROOT, type=Path, help="repository root to write into"
    )
    return parser


def main() -> int:
    """Generate both channel pointers, reporting a refusal as a failure."""
    args = _parser().parse_args()
    product = products.PRODUCTS[args.product]
    try:
        written = generate(
            args.root, product, args.tag, args.checksums.resolve(strict=True)
        )
    except (ChecksumError, PointerError) as exc:
        print(f"::error::{exc}", file=sys.stderr, flush=True)
        return 1
    for path in written:
        print(path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
