"""THE canonical actionlint provisioner. One implementation, five repos.

Deployed, not called: same constraint as the CI contract checker and the
runner preflight - their source repository is private, every consumer is
public.

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
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from dev import environment

VERSION = "1.7.12"

#: `(system, machine) -> (archive suffix, sha256)`. Every digest here is one
#: published in the upstream checksum file for THIS version, copied from the
#: workflow blocks this file replaces; bump the version and every digest
#: together, never one of them.
#:
#: Every entry is read from `actionlint_<VERSION>_checksums.txt` on the
#: release, never filled in from memory: a digest nobody checked is not a
#: verification. Every platform a runner has must be listed, because init's
#: tools phase provisions actionlint on all of them and an unlisted platform
#: is refused - which is the honest failure, and says what to add.
ARCHIVES: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): (
        "linux_amd64.tar.gz",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    ),
    ("linux", "aarch64"): (
        "linux_arm64.tar.gz",
        "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    ),
    ("darwin", "x86_64"): (
        "darwin_amd64.tar.gz",
        "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    ),
    ("darwin", "aarch64"): (
        "darwin_arm64.tar.gz",
        "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    ),
    ("windows", "x86_64"): (
        "windows_amd64.zip",
        "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
    ),
    ("windows", "aarch64"): (
        "windows_arm64.zip",
        "cadcf7ea4efe3a68728893813643cebe1185e5b1d4be5b96245f65c9a4d5ea41",
    ),
}

#: The release artefact path under the download host, which `_download` joins
#: to a literal `https://` origin.
RELEASE_PATH = "rhysd/actionlint/releases/download"

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
    return system, machine


def _cache_root() -> Path:
    """Where a verified binary is kept between runs.

    Runner-owned storage when CI provides it, so the containment rules that
    keep a job out of system locations still hold; the project's own `.venv`
    sibling otherwise, which a `just build-clean` already reclaims.
    """
    runner_tool_cache = environment.value(environment.RUNNER_TOOL_CACHE)
    if runner_tool_cache:
        return Path(runner_tool_cache) / "actionlint" / VERSION
    return Path.cwd() / ".venv" / "tools" / "actionlint" / VERSION


def _download(path: str, into: Path) -> None:
    """Fetch one release artefact to `into`, failing loudly rather than partially.

    The caller passes a PATH, never a URL, and the scheme and host are written
    here as literal text. That is the whole scheme control: a variable URL can
    carry `file:` or any other scheme urlopen happens to handle, and this way
    the only reachable origin is the one this line spells out.
    """
    with urllib.request.urlopen(f"https://github.com/{path}", timeout=120) as response:
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


def _extract_member(archive: Path, suffix: str, destination: Path) -> None:
    """Write the archive's `actionlint` entry to `destination`, by basename.

    Archive-embedded paths are discarded rather than honoured: the digest
    proves the bytes are the published release, not that the release's own
    member names are safe to write to.
    """
    wanted = destination.name
    if suffix.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            member = next(
                (n for n in bundle.namelist() if Path(n).name == wanted), None
            )
            if member is None:
                raise SystemExit(f"actionlint archive has no {wanted}")
            destination.write_bytes(bundle.read(member))
        return
    with tarfile.open(archive) as bundle:
        entry = next(
            (m for m in bundle.getmembers() if Path(m.name).name == wanted), None
        )
        if entry is None:
            raise SystemExit(f"actionlint archive has no {wanted}")
        extracted = bundle.extractfile(entry)
        if extracted is None:
            raise SystemExit(f"{wanted} in the archive is not a regular file")
        with extracted:
            destination.write_bytes(extracted.read())


def find() -> Path | None:
    """Return an actionlint already available here, without provisioning one.

    This is what the CHECK path asks, and the distinction is the contract: the
    workflow check verifies workflows and changes nothing, so a missing
    executable is a refusal naming the provisioning command, never a download
    nobody asked for. A check that quietly fetches a binary is a check
    that behaves differently the first time it runs.

    An actionlint on PATH wins over the provisioned copy: a developer who
    installed it with their package manager should not have a second copy used
    behind their back, and the version skew that creates is visible in the
    report actionlint prints.
    """
    on_path = shutil.which("actionlint")
    if on_path:
        return Path(on_path)
    key = _platform_key()
    if key not in ARCHIVES:
        return None
    binary = _cache_root() / ("actionlint.exe" if key[0] == "windows" else "actionlint")
    return binary if binary.is_file() else None


def ensure() -> Path:
    """Return a verified actionlint executable, downloading it once if needed.

    Provisioning, not checking: reached through ``--install``, which the
    repository's tool setup runs to install the pinned version. The check path
    uses :func:`find` and refuses instead.
    """
    available = find()
    if available is not None:
        return available

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
    artefact = f"{RELEASE_PATH}/v{VERSION}/actionlint_{VERSION}_{suffix}"
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / suffix
        _download(artefact, archive)
        _verify(archive, expected)
        # ONE member, written to a path this function chose. Not
        # `extractall`: an archive names its own paths, and honouring them is
        # how an entry called `../../.ssh/authorized_keys` gets written
        # somewhere nobody asked for. The digest above says these bytes are
        # the release; it says nothing about where the release wants to put
        # them. Only `actionlint` is wanted, and its name here is ours.
        _extract_member(archive, suffix, binary)
    if not binary.is_file():
        raise SystemExit(f"actionlint archive did not contain {binary.name}")
    binary.chmod(0o755)
    return binary


def main(argv: list[str] | None = None) -> int:
    """Run actionlint over the repository's workflows, or provision it.

    ``--install`` is the provisioning entry point the repository's tool setup
    runs; every other invocation is the read-only check, which refuses rather
    than downloading. Remaining arguments are actionlint's own.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if "--install" in args:
        try:
            binary = ensure()
        except SystemExit as failure:
            print(str(failure), file=sys.stderr)
            return TOOL_MISSING
        except OSError as failure:
            print(f"could not provision actionlint: {failure}", file=sys.stderr)
            return TOOL_MISSING
        print(f"actionlint {VERSION} available at {binary}")
        return OK

    binary = find()
    if binary is None:
        print(
            "actionlint is not available, so workflows cannot be checked. This check "
            f"installs nothing: provision the pinned version ({VERSION}) with "
            "`python -m dev.actionlint --install`, which the repository's tool setup "
            "runs, or put actionlint on PATH.",
            file=sys.stderr,
        )
        return TOOL_MISSING
    # shellcheck and pyflakes are disabled EXPLICITLY rather than left to
    # whether a runner happens to carry them. actionlint silently skips a
    # missing external linter, so leaving them implicit means the gate checks
    # a different set of things on every machine and nobody can tell which.
    # Runner labels are provisioned by infrastructure outside this codebase.
    # Keep actionlint's workflow parsing and all code-owned checks without
    # turning this project into a registry for fleet topology.
    command = [
        str(binary),
        "-no-color",
        "-shellcheck=",
        "-pyflakes=",
        "-ignore",
        'label ".+" is unknown',
        *args,
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
