"""THE canonical actionlint provisioner. One implementation, five repos.

Deployed, not called: same constraint as `ci_contract.py` and `preflight.sh`
beside it - ci-fleet is private, every consumer is public.

WHY THIS EXISTS. The fleet acquired actionlint four different ways, one per
repo, and each way was wrong in its own direction:

  vaultspec-core        `curl` the upstream install script, pipe it to bash,
                        run the result. Unpinned and unverified: whatever the
                        script downloads today is what gates the workflows.
  vaultspec-rag         `bash <(curl -sSfL .../download-actionlint.bash)`.
                        The same, with process substitution.
  vaultspec-dashboard   a pinned per-architecture tarball with a verified
                        digest - correct, and 30 lines of YAML nobody can run
                        before pushing.
  cadrumo               a second copy of the dashboard's block, with its own
                        copy of the digests, already at a different version.
  vaultspec-a2a         `uses: docker://rhysd/actionlint` - a daemon dependency
                        on a fleet where a lint gate that reddens because
                        nobody opened Docker Desktop is a gate people learn to
                        ignore.

The dashboard's approach is the right one and is what this file generalises,
with the property that made it hard to reuse removed: it now runs from a
recipe, so the gate a developer runs before pushing is the gate CI runs.

THE ARCHITECTURE PIN IS THE POINT, not tidiness. The dashboard block reached
its current shape after naming `linux_amd64.tar.gz` unconditionally with a
single digest. On an ARM64 runner that does not fail - it PASSES, because the
downloaded file really is the amd64 archive the digest names - and then dies
at `Exec format error` one line later. A verification step that reports
success while handing back an unusable binary is worse than none, because it
reads as assurance. So the digest is per platform, and an unlisted platform is
refused rather than guessed at.

Stdlib only, so it behaves identically on every platform and needs nothing
installed to install something.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.7.12"

#: `(system, machine) -> (archive suffix, sha256)`. Every digest here is one
#: published in the upstream checksum file for THIS version, copied from the
#: workflow blocks this file replaces; bump the version and every digest
#: together, never one of them.
#:
#: ONLY the two platforms whose digests this fleet has actually verified are
#: listed. macOS and Windows are absent on purpose rather than filled in from
#: memory: a digest nobody checked is not a verification, and the honest
#: failure for an unlisted platform is the refusal below - which says exactly
#: what to add and where to get it. Workflow linting runs on the Linux cells
#: in all five repos, so nothing is currently blocked by the gap.
ARCHIVES: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): (
        "linux_amd64.tar.gz",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    ),
    ("linux", "aarch64"): (
        "linux_arm64.tar.gz",
        "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    ),
}

BASE_URL = "https://github.com/rhysd/actionlint/releases/download"

#: Exit codes, from `dev/EXIT-CODES.md`: 0 OK, 1 FAILED, 127 TOOL_MISSING.
OK = 0
FAILED = 1
TOOL_MISSING = 127


def _platform_key() -> tuple[str, str]:
    """Return the normalised `(system, machine)` this process is running on."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(
        machine, machine
    )
    if system == "windows":
        machine = "amd64" if machine == "x86_64" else machine
    if system == "darwin":
        machine = "arm64" if machine == "aarch64" else machine
    return system, machine


def _cache_root() -> Path:
    """Where a verified binary is kept between runs.

    Runner-owned storage when CI provides it, so the containment rules that
    keep a job out of system locations still hold; the project's own `.venv`
    sibling otherwise, which a `just build-clean` already reclaims.
    """
    runner_tool_cache = os.environ.get("RUNNER_TOOL_CACHE")
    if runner_tool_cache:
        return Path(runner_tool_cache) / "actionlint" / VERSION
    return Path.cwd() / ".venv" / "tools" / "actionlint" / VERSION


def _download(url: str, into: Path) -> None:
    """Fetch `url` to `into`, failing loudly rather than partially."""
    with urllib.request.urlopen(url, timeout=120) as response:
        into.write_bytes(response.read())


def _verify(archive: Path, expected: str) -> None:
    """Refuse an archive whose bytes are not the ones this file pins."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(
            f"actionlint {VERSION} archive digest mismatch\n"
            f"  expected {expected}\n"
            f"  got      {digest}\n"
            "Refusing to run an unverified executable."
        )


def ensure() -> Path:
    """Return a verified actionlint executable, downloading it once if needed.

    An actionlint already on PATH is used as-is. That is deliberate: a
    developer who installed it with their package manager should not have a
    second copy downloaded behind their back, and the version skew that
    creates is visible in the report actionlint prints.
    """
    on_path = shutil.which("actionlint")
    if on_path:
        return Path(on_path)

    key = _platform_key()
    if key not in ARCHIVES:
        raise SystemExit(
            f"no pinned actionlint archive for {key[0]}/{key[1]}. "
            f"Add it to ARCHIVES in this file with the digest published in "
            f"actionlint_{VERSION}_checksums.txt for that platform, or put "
            "actionlint on PATH. Guessing an archive is how an amd64 binary "
            "reached an ARM runner and passed its own digest check."
        )
    suffix, expected = ARCHIVES[key]
    root = _cache_root()
    binary = root / ("actionlint.exe" if key[0] == "windows" else "actionlint")
    if binary.is_file():
        return binary

    root.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/v{VERSION}/actionlint_{VERSION}_{suffix}"
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / suffix
        _download(url, archive)
        _verify(archive, expected)
        if suffix.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(root)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(root, filter="data")
    if not binary.is_file():
        raise SystemExit(f"actionlint archive did not contain {binary.name}")
    binary.chmod(0o755)
    return binary


def main(argv: list[str] | None = None) -> int:
    """Run actionlint over the repository's workflows."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        binary = ensure()
    except SystemExit as failure:
        print(str(failure), file=sys.stderr)
        return TOOL_MISSING
    except OSError as failure:
        print(f"could not provision actionlint: {failure}", file=sys.stderr)
        return TOOL_MISSING
    # shellcheck and pyflakes are disabled EXPLICITLY rather than left to
    # whether a runner happens to carry them. actionlint silently skips a
    # missing external linter, so leaving them implicit means the gate checks
    # a different set of things on every machine and nobody can tell which.
    command = [str(binary), "-no-color", "-shellcheck=", "-pyflakes=", *args]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
