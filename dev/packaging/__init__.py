"""Release-channel manifest generation for the vaultspec delivery matrix.

One product ships through four channels: PyPI (``publish.yml``), standalone
PyApp binaries attached to the GitHub Release (``binaries.yml``), Scoop, and
Homebrew. The first two produce artifacts. The last two produce *pointers* -
a manifest that names a version and pins a SHA-256 a user's package manager
will act on - and that difference is what this package exists to enforce.

A pointer is generated from the release's own ``SHA256SUMS``, never
hand-authored and never partially rewritten in place by shell. The failure
that motivated the package is the alternative: an inline ``jq`` bump in the
release workflow wrote vaultspec-core-v0.1.60's Scoop manifest with the right
URLs and empty hashes, out of a green run, because the digest lookup silently
found nothing (see :mod:`dev.packaging.checksums`).

The modules here are deliberately product-parameterised - the vaultspec family
and cadrumo ship the same channel shapes from different repositories, so the
product identity is data (:mod:`dev.packaging.products`) and the rendering is
shared.
"""

from __future__ import annotations
