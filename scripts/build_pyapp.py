#!/usr/bin/env python
"""Build the standalone ``vaultspec-core`` and ``vaultspec-mcp`` binaries with PyApp.

PyApp (https://ofek.dev/pyapp) is a Rust bootstrapper from the Hatch
ecosystem. It is configured entirely through ``PYAPP_*`` environment
variables read at ``cargo`` build time; there is no project-side config
file. This script encodes the decided build model once so the release
workflow (and a maintainer reproducing a release locally) can invoke it
identically on every target.

Two binaries are produced from the same PyPI distribution, differing only
in their execution entry point:

- ``vaultspec-core`` runs ``python -m vaultspec_core`` (PYAPP_EXEC_MODULE).
- ``vaultspec-mcp`` runs the object reference ``vaultspec_core.mcp_server.app:run``
  (PYAPP_EXEC_SPEC), matching the ``vaultspec-mcp`` console script.

The distribution source is the published PyPI package pinned to the release
version: PyApp installs it into a per-user data directory on first launch
(PYAPP_PROJECT_NAME + PYAPP_PROJECT_VERSION), while the CPython runtime is
embedded into the binary itself (PYAPP_DISTRIBUTION_EMBED). The binary
therefore needs no Python on the user's machine, but does resolve
``vaultspec-core==<version>`` from PyPI on first run - so the release must
be published to PyPI for the binary to bootstrap.

Usage::

    uv run --no-project --python 3.13 python scripts/build_pyapp.py \
        --tag vaultspec-core-v0.1.48 --outdir dist-bin [--target <triple>]

``--target`` cross-compiles for a Rust target triple other than the host
(the CI matrix uses it to build the macOS x86_64 binary on an Apple Silicon
runner); the matching ``rustup target`` must already be installed. Only the
Python standard library is used, so any Python 3.13 interpreter can run it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Pinned PyApp crate version. Bumping this changes the bootstrapper and the
# embedded python-build-standalone distributions it selects, so it is an
# explicit, reviewable dependency rather than "whatever is latest".
PYAPP_VERSION = "0.29.0"

# The PyPI distribution both binaries install from.
PROJECT_NAME = "vaultspec-core"

# Embedded CPython series. Must satisfy the package's requires-python.
PYTHON_VERSION = "3.13"


@dataclass(frozen=True)
class Binary:
    """One console entry point rendered as a standalone binary."""

    name: str
    # Exactly one of exec_module / exec_spec is set (PyApp execution modes
    # are mutually exclusive).
    exec_module: str | None = None
    exec_spec: str | None = None

    def pyapp_exec_env(self) -> dict[str, str]:
        if self.exec_module is not None:
            return {"PYAPP_EXEC_MODULE": self.exec_module}
        assert self.exec_spec is not None
        return {"PYAPP_EXEC_SPEC": self.exec_spec}


BINARIES = (
    Binary(name="vaultspec-core", exec_module="vaultspec_core"),
    Binary(name="vaultspec-mcp", exec_spec="vaultspec_core.mcp_server.app:run"),
)


def version_from_tag(tag: str) -> str:
    """Derive the PyPI version from a release tag.

    Release tags are ``vaultspec-core-v<version>`` (see publish.yml); a bare
    ``v<version>`` or ``<version>`` is also accepted for local invocation.
    """
    for prefix in (f"{PROJECT_NAME}-v", "v"):
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return tag


def host_target_triple() -> str:
    """Return the host Rust target triple as reported by ``rustc``."""
    out = subprocess.run(
        ["rustc", "-vV"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not determine host target triple from `rustc -vV`")


def build_one(binary: Binary, version: str, target: str, workdir: Path) -> Path:
    """Build a single PyApp binary and return the path to the raw executable."""
    root = workdir / binary.name
    env = os.environ.copy()
    env.update(
        {
            "PYAPP_PROJECT_NAME": PROJECT_NAME,
            "PYAPP_PROJECT_VERSION": version,
            "PYAPP_PYTHON_VERSION": PYTHON_VERSION,
            # Install the project with uv rather than pip on first launch.
            "PYAPP_UV_ENABLED": "1",
            # Bake the CPython distribution into the binary so the target
            # machine needs no interpreter.
            "PYAPP_DISTRIBUTION_EMBED": "1",
        }
    )
    env.update(binary.pyapp_exec_env())

    cmd = [
        "cargo",
        "install",
        "pyapp",
        "--version",
        PYAPP_VERSION,
        "--locked",
        "--force",
        "--root",
        str(root),
        "--target",
        target,
    ]
    print(f"::group::cargo install pyapp ({binary.name}, {target})", flush=True)
    subprocess.run(cmd, check=True, env=env)
    print("::endgroup::", flush=True)

    exe = "pyapp.exe" if target.endswith("windows-msvc") else "pyapp"
    produced = root / "bin" / exe
    if not produced.is_file():
        raise FileNotFoundError(f"pyapp did not produce {produced}")
    return produced


def asset_name(binary: Binary, target: str) -> str:
    suffix = ".exe" if target.endswith("windows-msvc") else ""
    return f"{binary.name}-{target}{suffix}"


def write_checksum(asset: Path) -> Path:
    """Write ``<asset>.sha256`` in ``sha256sum``-compatible format."""
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    checksum = asset.with_name(asset.name + ".sha256")
    checksum.write_text(f"{digest}  {asset.name}\n", encoding="utf-8")
    return checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tag", help="release tag, e.g. vaultspec-core-v0.1.48")
    source.add_argument("--version", help="PyPI version directly, e.g. 0.1.48")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("dist-bin"),
        help="directory to place the renamed binaries and checksums in",
    )
    parser.add_argument(
        "--target",
        help="Rust target triple to (cross-)build for; defaults to the host",
    )
    args = parser.parse_args()

    version = args.version if args.version else version_from_tag(args.tag)
    target = args.target if args.target else host_target_triple()

    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    produced: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="pyapp-build-") as tmp:
        workdir = Path(tmp)
        for binary in BINARIES:
            raw = build_one(binary, version, target, workdir)
            asset = outdir / asset_name(binary, target)
            shutil.copy2(raw, asset)
            if not target.endswith("windows-msvc"):
                asset.chmod(0o755)
            checksum = write_checksum(asset)
            produced.extend((asset, checksum))
            print(f"built {asset} ({asset.stat().st_size} bytes)", flush=True)

    print(f"\n{PROJECT_NAME} {version} binaries for {target}:")
    for path in produced:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
