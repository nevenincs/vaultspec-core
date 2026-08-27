"""Render the Scoop manifest that installs the Windows release binaries.

The repository is its own Scoop bucket: Scoop resolves app manifests from a
``bucket/`` subdirectory when one is present, so the product ships through
Scoop without a second repository existing to be kept in sync. Installing is
then::

    scoop bucket add vaultspec-core https://github.com/nevenincs/vaultspec-core
    scoop install vaultspec-core

``checkver`` and ``autoupdate`` are emitted alongside the pinned fields, but
they serve maintainer tooling only - ``scoop install`` reads the committed
``version``/``url``/``hash``. That asymmetry is why the committed hashes are
generated from the release's own ``SHA256SUMS`` and never left blank: an
autoupdate stanza does not rescue a manifest whose pinned hash is wrong.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dev.packaging import products
from dev.packaging.checksums import require

if TYPE_CHECKING:
    from dev.packaging.products import Product


def render_manifest(
    product: Product,
    version: str,
    digests: dict[str, str],
) -> dict[str, object]:
    """Return one Scoop manifest pinned to this release's exact assets."""
    # Scoop serves exactly one target, so the manifest needs no `architecture`
    # split; unpacking asserts that rather than assuming it silently.
    (target,) = products.SCOOP_TARGETS
    base = product.release_base_url(version)
    autoupdate_base = (
        f"{product.homepage}/releases/download/{product.tag_prefix}$version"
    )
    entries = [
        (product.asset_name(executable, target), executable.name)
        for executable in product.executables
    ]
    assets = [asset for asset, _ in entries]
    return {
        "version": version,
        "description": product.description,
        "homepage": product.homepage,
        "license": product.license,
        "url": [f"{base}/{asset}" for asset in assets],
        "hash": [require(digests, asset) for asset in assets],
        "bin": [[asset, name] for asset, name in entries],
        "checkver": {
            "github": product.homepage,
            "regex": f"{product.tag_prefix}([\\d.]+)",
        },
        "autoupdate": {
            "url": [f"{autoupdate_base}/{asset}" for asset in assets],
            "hash": {
                "url": f"{autoupdate_base}/SHA256SUMS",
                "regex": "$sha256\\s+$basename",
            },
        },
        "notes": [
            f"Installed: {', '.join(item.name for item in product.executables)}.",
            f"Verify with: {product.executables[0].name} --version",
            "First launch bootstraps the Python runtime; it needs network once.",
        ],
    }


def render(product: Product, version: str, digests: dict[str, str]) -> str:
    """Return the manifest as the exact bytes committed to ``bucket/``."""
    manifest = render_manifest(product, version, digests)
    return json.dumps(manifest, indent=2) + "\n"
