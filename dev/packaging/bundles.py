"""Build deterministic, self-describing archives for binary releases."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dev.binaries.build_pyapp import (
    CPYTHON_VERSION,
    GLIBC_FLOOR,
    PYAPP_VERSION,
    PYTHON_VERSION,
)
from dev.packaging.products import VAULTSPEC_CORE, Product, is_windows_target

MANIFEST_NAME = "manifest.json"
LICENSE_NAME = "LICENSE"
README_NAME = "README.txt"
MANIFEST_SCHEMA = "vaultspec.release-bundle.v1"


class BundleError(RuntimeError):
    """A release bundle cannot be built from the supplied files."""


@dataclass(frozen=True)
class BundleFile:
    """One file with a stable archive name and a manifest role."""

    source: Path
    name: str
    role: str


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_revision(repo_root: Path) -> str:
    """Return the checked-out commit used to construct a release bundle."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode or not revision:
        detail = result.stderr.strip() or "git returned no revision"
        raise BundleError(
            f"could not determine source revision in {repo_root}: {detail}"
        )
    return revision


def _readme(product: Product, version: str, target: str) -> bytes:
    """Return the short usage note shipped beside the executables."""
    lines = [
        f"{product.display_name or product.name} {version}",
        "",
        f"Target: {target}",
        "",
        "Executables:",
        *(
            f"  {product.executable_name(executable, target)} - {executable.summary}"
            for executable in product.executables
        ),
        "",
        "Run vaultspec-core --version to verify the installed command.",
    ]
    return ("\n".join(lines) + "\n").encode()


def _manifest(
    product: Product,
    version: str,
    target: str,
    archive_name: str,
    revision: str,
    files: tuple[BundleFile, ...],
) -> bytes:
    """Return a deterministic manifest for the staged bundle members."""
    floor = GLIBC_FLOOR.get(target)
    members = [
        {
            "name": member.name,
            "role": member.role,
            "size": member.source.stat().st_size,
            "sha256": _sha256(member.source),
        }
        for member in files
    ]
    payload = {
        "schema": MANIFEST_SCHEMA,
        "product": product.name,
        "display_name": product.display_name or product.name,
        "publisher": product.publisher or None,
        "legal_copyright": product.legal_copyright or None,
        "version": version,
        "release_tag": product.tag_for(version),
        "target": target,
        "archive": {
            "name": archive_name,
            "format": "zip" if is_windows_target(target) else "tar.gz",
        },
        "files": members,
        "source_revision": revision,
        "runtime": {
            "python": PYTHON_VERSION,
            "cpython": CPYTHON_VERSION,
            "pyapp": PYAPP_VERSION,
        },
        "platform": {
            "glibc_floor": (".".join(str(part) for part in floor) if floor else None),
        },
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _zip_archive(destination: Path, files: tuple[BundleFile, ...]) -> None:
    """Write a timestamp-free ZIP archive from *files*."""
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for member in sorted(files, key=lambda item: item.name):
            info = zipfile.ZipInfo(member.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (member.source.stat().st_mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, member.source.read_bytes())


def _tar_archive(destination: Path, files: tuple[BundleFile, ...]) -> None:
    """Write a timestamp-free TAR.GZ archive from *files*."""
    with (
        destination.open("wb") as raw,
        gzip.GzipFile(
            filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0
        ) as compressed,
        tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
        ) as archive,
    ):
        for member in sorted(files, key=lambda item: item.name):
            data = member.source.read_bytes()
            info = tarfile.TarInfo(member.name)
            info.size = len(data)
            info.mode = member.source.stat().st_mode & 0o777
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))


def _stage_files(
    product: Product,
    version: str,
    target: str,
    raw_dir: Path,
    repo_root: Path,
    root: Path,
) -> tuple[BundleFile, ...]:
    """Copy finalized executables and release material into *root*."""
    members: list[BundleFile] = []
    for executable in product.executables:
        source = raw_dir / product.asset_name(executable, target)
        if not source.is_file():
            raise BundleError(f"missing finalized executable: {source}")
        destination = root / product.executable_name(executable, target)
        shutil.copy2(source, destination)
        if not is_windows_target(target):
            destination.chmod(0o755)
        members.append(BundleFile(destination, destination.name, "executable"))

    license_source = repo_root / LICENSE_NAME
    if not license_source.is_file():
        raise BundleError(f"missing release license: {license_source}")
    license_destination = root / LICENSE_NAME
    shutil.copy2(license_source, license_destination)
    members.append(BundleFile(license_destination, LICENSE_NAME, "license"))

    readme = root / README_NAME
    readme.write_bytes(_readme(product, version, target))
    members.append(BundleFile(readme, README_NAME, "readme"))
    return tuple(members)


def build_bundle(
    product: Product,
    version: str,
    target: str,
    raw_dir: Path,
    output_dir: Path,
    repo_root: Path,
    revision: str | None = None,
) -> Path:
    """Build one target archive and its checksum sidecar."""
    if not product.serves(target):
        raise BundleError(f"{product.name} does not support target {target}")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = product.bundle_name(version, target)
    revision = revision or source_revision(repo_root)
    with tempfile.TemporaryDirectory(prefix="bundle-", dir=output_dir) as temporary:
        root = Path(temporary) / "contents"
        root.mkdir()
        members = _stage_files(product, version, target, raw_dir, repo_root, root)
        manifest_path = root / MANIFEST_NAME
        manifest_path.write_bytes(
            _manifest(product, version, target, archive_name, revision, members)
        )
        archive_members = (
            *members,
            BundleFile(manifest_path, MANIFEST_NAME, "manifest"),
        )
        temporary_archive = Path(temporary) / archive_name
        if is_windows_target(target):
            _zip_archive(temporary_archive, archive_members)
        else:
            _tar_archive(temporary_archive, archive_members)

        archive = output_dir / archive_name
        temporary_archive.replace(archive)

    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(
        f"{_sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
        newline="",
    )
    verify_bundle(archive, product, version, target)
    return archive


def _archive_contents(archive: Path, target: str) -> dict[str, bytes]:
    """Read one archive's regular-file members, rejecting ambiguous layouts."""
    if is_windows_target(target):
        try:
            with zipfile.ZipFile(archive) as handle:
                infos = handle.infolist()
                names = [info.filename for info in infos]
                if any(info.is_dir() for info in infos):
                    raise BundleError(f"bundle contains a directory: {archive}")
                if len(names) != len(set(names)):
                    raise BundleError(f"bundle contains duplicate members: {archive}")
                return {name: handle.read(name) for name in names}
        except (OSError, zipfile.BadZipFile) as exc:
            raise BundleError(f"could not read ZIP bundle {archive}: {exc}") from exc

    try:
        with tarfile.open(archive, "r:gz") as handle:
            members = handle.getmembers()
            names = [member.name for member in members]
            if any(not member.isfile() for member in members):
                raise BundleError(f"bundle contains a non-file member: {archive}")
            if len(names) != len(set(names)):
                raise BundleError(f"bundle contains duplicate members: {archive}")
            contents: dict[str, bytes] = {}
            for member in members:
                payload = handle.extractfile(member)
                if payload is None:
                    raise BundleError(f"bundle member cannot be read: {member.name}")
                contents[member.name] = payload.read()
            return contents
    except (OSError, tarfile.ReadError) as exc:
        raise BundleError(f"could not read TAR.GZ bundle {archive}: {exc}") from exc


def verify_bundle(archive: Path, product: Product, version: str, target: str) -> None:
    """Verify the public archive layout and the hashes in its manifest."""
    expected_archive = product.bundle_name(version, target)
    if archive.name != expected_archive:
        raise BundleError(
            f"bundle is named {archive.name!r}; expected {expected_archive!r}"
        )
    if not archive.is_file():
        raise BundleError(f"missing bundle: {archive}")

    contents = _archive_contents(archive, target)
    expected_roles = {
        **{
            product.executable_name(executable, target): "executable"
            for executable in product.executables
        },
        LICENSE_NAME: "license",
        README_NAME: "readme",
    }
    expected_members = {*expected_roles, MANIFEST_NAME}
    if set(contents) != expected_members:
        raise BundleError(
            f"bundle members differ from the contract: "
            f"expected {sorted(expected_members)}, got {sorted(contents)}"
        )

    try:
        parsed: object = json.loads(contents[MANIFEST_NAME])
    except json.JSONDecodeError as exc:
        raise BundleError(f"manifest.json is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BundleError("manifest.json is not a JSON object")
    manifest = cast("dict[str, object]", parsed)

    expected_values = {
        "schema": MANIFEST_SCHEMA,
        "product": product.name,
        "display_name": product.display_name or product.name,
        "publisher": product.publisher or None,
        "legal_copyright": product.legal_copyright or None,
        "version": version,
        "release_tag": product.tag_for(version),
        "target": target,
    }
    for key, expected in expected_values.items():
        if manifest.get(key) != expected:
            raise BundleError(
                f"manifest.json {key!r} is {manifest.get(key)!r}; expected {expected!r}"
            )

    archive_metadata = manifest.get("archive")
    if not isinstance(archive_metadata, dict):
        raise BundleError("manifest.json archive metadata is missing")
    archive_metadata = cast("dict[str, object]", archive_metadata)
    expected_format = "zip" if is_windows_target(target) else "tar.gz"
    if archive_metadata.get("name") != expected_archive:
        raise BundleError("manifest.json archive name does not match the bundle")
    if archive_metadata.get("format") != expected_format:
        raise BundleError("manifest.json archive format does not match the target")

    revision = manifest.get("source_revision")
    if not isinstance(revision, str) or not revision:
        raise BundleError("manifest.json source revision is missing")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise BundleError("manifest.json runtime metadata is missing")
    runtime = cast("dict[str, object]", runtime)
    expected_runtime = {
        "python": PYTHON_VERSION,
        "cpython": CPYTHON_VERSION,
        "pyapp": PYAPP_VERSION,
    }
    if runtime != expected_runtime:
        raise BundleError("manifest.json runtime metadata is incorrect")

    platform = manifest.get("platform")
    if not isinstance(platform, dict):
        raise BundleError("manifest.json platform metadata is missing")
    platform = cast("dict[str, object]", platform)
    floor = GLIBC_FLOOR.get(target)
    expected_floor = ".".join(str(part) for part in floor) if floor else None
    if platform != {"glibc_floor": expected_floor}:
        raise BundleError("manifest.json platform metadata is incorrect")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise BundleError("manifest.json files must be a list")
    entries = cast("list[object]", raw_files)
    by_name: dict[str, dict[str, object]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise BundleError("manifest.json contains a non-object file entry")
        entry = cast("dict[str, object]", raw_entry)
        name = entry.get("name")
        if not isinstance(name, str) or name in by_name:
            raise BundleError("manifest.json contains a duplicate or invalid name")
        by_name[name] = entry

    if set(by_name) != set(expected_roles):
        raise BundleError("manifest.json files do not describe the bundle members")
    for name, role in expected_roles.items():
        entry = by_name[name]
        if entry.get("role") != role:
            raise BundleError(f"manifest.json role for {name} is incorrect")
        size = entry.get("size")
        digest = entry.get("sha256")
        actual = contents[name]
        if not isinstance(size, int) or isinstance(size, bool) or size != len(actual):
            raise BundleError(f"manifest.json size for {name} is incorrect")
        if digest != hashlib.sha256(actual).hexdigest():
            raise BundleError(f"manifest.json hash for {name} is incorrect")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--tag", help="release tag, e.g. vaultspec-core-v0.2.2")
    source.add_argument("--version", help="PyPI version directly, e.g. 0.2.2")
    parser.add_argument(
        "--verify", type=Path, help="verify an existing public target bundle"
    )
    parser.add_argument("--target", help="Rust target triple")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("dist-bin"),
        help="directory containing finalized target-qualified executables",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("dist-bundles"),
        help="directory for the target archive and checksum",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="repository root containing LICENSE and the source checkout",
    )
    parser.add_argument(
        "--source-revision",
        help="checked-out source revision; defaults to git rev-parse HEAD",
    )
    args = parser.parse_args()
    if args.verify is not None:
        if args.target is None or (args.tag is None and args.version is None):
            parser.error("--verify requires --target and --tag or --version")
        version = (
            args.version
            if args.version is not None
            else VAULTSPEC_CORE.version_from_tag(args.tag)
        )
        verify_bundle(args.verify, VAULTSPEC_CORE, version, args.target)
        print(f"verified {args.verify}")
        return 0
    if args.target is None:
        parser.error("--target is required when building a bundle")
    if args.tag is None and args.version is None:
        parser.error("one of --tag or --version is required when building a bundle")
    version = (
        args.version
        if args.version is not None
        else VAULTSPEC_CORE.version_from_tag(args.tag)
    )
    archive = build_bundle(
        VAULTSPEC_CORE,
        version,
        args.target,
        args.raw_dir,
        args.outdir,
        args.repo_root,
        args.source_revision,
    )
    print(f"built {archive} ({archive.stat().st_size} bytes)")
    print(f"  {archive.with_name(archive.name + '.sha256')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
