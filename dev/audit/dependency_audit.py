#!/usr/bin/env python
"""Multi-ecosystem dependency vulnerability audit gate.

This is the fleet's single dependency-audit implementation; the copy in every
repository is identical. It is the ONE audit that GATES: a published advisory
against a pinned version is a verdict, not a lead.

Why it does not simply shell out to ``uv audit``
------------------------------------------------
``uv audit`` is a preview feature that exits ``0`` even when it prints
advisories, so three repositories in this fleet shipped a "GATE" that could not
fail. Deriving a gate's verdict from a preview tool's text summary keeps the
gate one release note away from breaking again, and it covers only Python --
while these repositories also lock npm and cargo dependencies and vendor
binaries.

So the gate resolves the pinned coordinates itself, out of the lockfiles that
are actually committed, and asks OSV (the same database ``uv audit`` queries)
about every one of them. The verdict is then a property of the finding set, not
of anybody's exit code. Consequences that are deliberate:

* Any ecosystem with a committed lockfile is audited. Nothing is Python-only.
* The audit FAILS CLOSED. An unreachable OSV, an unparsable lockfile or a
  malformed allowlist exits non-zero; a gate that cannot run is never a pass.
* Suppressions are declarative, in ``dependency-audit-allowlist.toml``, and
  every one carries an id, a reason and an expiry. An expired suppression fails
  the audit. Nothing is ignored silently.

Exit codes
----------
``0`` clean, ``1`` findings (or an expired suppression), ``7`` the audit could
not complete. Only ``0`` is a pass. The numbers are lane L9's fleet-wide
contract (``dev/exit_codes.py``): ``OK``, ``FAILED``, and the "the scanner did
not actually run" code -- used here on a GATING target because a gate that
could not run must not be readable either as a pass or as a finding. The values
are restated rather than imported so this file stays standalone and stdlib-only
in every repository.

Output
------
A human summary on stdout always. ``--json`` writes the machine-readable report
to stdout instead; when ``VAULTSPEC_CI_REPORTS`` names a directory the same
report is additionally written to ``<dir>/dependency-audit.json``. With the
variable unset nothing is written anywhere, which preserves cadrumo's
deliberate zero-artifact posture.

Self-test
---------
``--extra-package ECOSYSTEM:NAME:VERSION`` injects one additional coordinate
into the scan. It exists so the gate's ability to fail can be demonstrated
against real OSV data without editing a lockfile -- a gate nobody has watched
fail is not a gate. See the repository's dependency-audit guard test.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: See the module docstring: these mirror ``dev/exit_codes.py`` (lane L9).
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_BROKEN = 7

_OSV_QUERYBATCH = "https://api.osv.dev/v1/querybatch"
_OSV_VULN = "https://api.osv.dev/v1/vulns/"
_OSV_BATCH_LIMIT = 1000
_TIMEOUT = 60.0

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = REPO_ROOT / "dependency-audit-allowlist.toml"
BINARIES_PATH = REPO_ROOT / "dependency-audit-binaries.toml"

#: Directories never walked when discovering lockfiles.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "target",
        "dist",
        "build",
        "__pycache__",
        ".pytest-tmp",
        ".mypy_cache",
        ".ruff_cache",
        ".logs",
        "tmp",
        "scratch",
        "typings",
        "stubs",
    }
)
_MAX_DEPTH = 4


class AuditError(Exception):
    """The audit could not be completed. Never a pass."""


# --------------------------------------------------------------------------
# coordinates
# --------------------------------------------------------------------------

#: OSV ecosystem -> the surface name reported to humans.
_SURFACES = {
    "PyPI": "python",
    "npm": "node",
    "crates.io": "rust",
    "Go": "go",
}


@dataclass(frozen=True, order=True)
class Coordinate:
    """One pinned dependency: an OSV ecosystem, a name and an exact version."""

    ecosystem: str
    name: str
    version: str
    source: str = ""

    @property
    def surface(self) -> str:
        """Return the human label for this coordinate's ecosystem."""
        if self.source == BINARIES_PATH.name:
            return "binaries"
        return _SURFACES.get(self.ecosystem, self.ecosystem.lower())


def _iter_lockfiles(root: Path) -> list[Path]:
    """Return every committed lockfile below ``root``, skipping vendor trees."""
    wanted = {"uv.lock", "package-lock.json", "Cargo.lock"}
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
        if depth > _MAX_DEPTH:
            return
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS and not entry.name.startswith("."):
                    walk(entry, depth + 1)
            elif entry.name in wanted:
                found.append(entry)

    walk(root, 0)
    return found


def _read_uv_lock(path: Path) -> list[Coordinate]:
    """Return every ``(name, version)`` pinned by a ``uv.lock``."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rel = path.relative_to(REPO_ROOT).as_posix()
    return [
        Coordinate("PyPI", pkg["name"], pkg["version"], rel)
        for pkg in data.get("package", ())
        if pkg.get("name") and pkg.get("version")
    ]


def _read_package_lock(path: Path) -> list[Coordinate]:
    """Return every version pinned by an npm ``package-lock.json``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rel = path.relative_to(REPO_ROOT).as_posix()
    out: list[Coordinate] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, entry in packages.items():
            if not key or not isinstance(entry, dict):
                continue  # "" is the root project itself.
            name = entry.get("name") or key.rsplit("node_modules/", 1)[-1]
            version = entry.get("version")
            if name and version and not entry.get("link"):
                out.append(Coordinate("npm", name, version, rel))
    else:  # lockfileVersion 1

        def recurse(deps: dict[str, Any]) -> None:
            for name, entry in deps.items():
                if isinstance(entry, dict) and entry.get("version"):
                    out.append(Coordinate("npm", name, entry["version"], rel))
                    nested = entry.get("dependencies")
                    if isinstance(nested, dict):
                        recurse(nested)

        recurse(data.get("dependencies") or {})
    return out


def _read_cargo_lock(path: Path) -> list[Coordinate]:
    """Return every crate version pinned by a ``Cargo.lock``."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rel = path.relative_to(REPO_ROOT).as_posix()
    return [
        Coordinate("crates.io", pkg["name"], pkg["version"], rel)
        for pkg in data.get("package", ())
        if pkg.get("name") and pkg.get("version") and pkg.get("source")
    ]


def _read_binaries(path: Path) -> list[Coordinate]:
    """Return the vendored/shipped binaries declared for auditing.

    Binaries a repository ships but does not resolve through a package
    lockfile have no lockfile to read, so they are declared here instead --
    each with the OSV ecosystem and name under which the upstream project
    publishes its advisories.
    """
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: list[Coordinate] = []
    for entry in data.get("binary", ()):
        missing = [k for k in ("ecosystem", "name", "version") if not entry.get(k)]
        if missing:
            raise AuditError(
                f"{path.name}: a [[binary]] entry is missing {', '.join(missing)}"
            )
        out.append(
            Coordinate(entry["ecosystem"], entry["name"], entry["version"], path.name)
        )
    return out


def collect_coordinates(root: Path = REPO_ROOT) -> list[Coordinate]:
    """Return every pinned coordinate this repository actually has.

    Ecosystems are discovered, never assumed: whichever lockfiles are
    committed decide what gets audited, so a repository that grows a Rust or
    Node surface is covered the moment its lockfile lands.
    """
    readers = {
        "uv.lock": _read_uv_lock,
        "package-lock.json": _read_package_lock,
        "Cargo.lock": _read_cargo_lock,
    }
    seen: set[Coordinate] = set()
    for lockfile in _iter_lockfiles(root):
        try:
            for coord in readers[lockfile.name](lockfile):
                seen.add(coord)
        except AuditError:
            raise
        except (OSError, ValueError, tomllib.TOMLDecodeError, KeyError) as error:
            # An unreadable lockfile is a broken gate, never a clean tree.
            raise AuditError(f"cannot parse {lockfile}: {error}") from error
    seen.update(_read_binaries(BINARIES_PATH))
    return sorted(seen)


# --------------------------------------------------------------------------
# suppressions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Suppression:
    """One accepted advisory, with the reason and the date it stops applying."""

    id: str
    reason: str
    expires: _dt.date

    def expired(self, today: _dt.date) -> bool:
        """Return whether this suppression has passed its expiry date."""
        return today > self.expires


def load_suppressions(path: Path = ALLOWLIST_PATH) -> list[Suppression]:
    """Parse the declarative allowlist.

    Every entry must carry ``id``, ``reason`` and ``expires``. A malformed or
    incomplete entry raises: an allowlist the gate cannot understand must not
    be interpreted generously.
    """
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise AuditError(f"{path.name} is not valid TOML: {error}") from error

    out: list[Suppression] = []
    for index, entry in enumerate(data.get("suppression", ()), start=1):
        missing = [k for k in ("id", "reason", "expires") if not entry.get(k)]
        if missing:
            raise AuditError(
                f"{path.name}: suppression #{index} is missing "
                f"{', '.join(missing)}. Every suppression needs an advisory id, "
                "a reason, and an expiry date."
            )
        expires = entry["expires"]
        if isinstance(expires, _dt.datetime):
            expires = expires.date()
        if not isinstance(expires, _dt.date):
            raise AuditError(
                f"{path.name}: suppression {entry['id']} has expires="
                f"{expires!r}; write it as a bare TOML date, e.g. 2026-12-31."
            )
        if not str(entry["reason"]).strip():
            raise AuditError(
                f"{path.name}: suppression {entry['id']} has an empty reason."
            )
        out.append(Suppression(str(entry["id"]), str(entry["reason"]), expires))
    return out


# --------------------------------------------------------------------------
# OSV
# --------------------------------------------------------------------------


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST ``payload`` as JSON and return the decoded response."""
    if not url.startswith("https://"):
        raise AuditError(f"refusing to POST to a non-HTTPS URL: {url}")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)


def _get_json(url: str) -> dict[str, Any]:
    """GET ``url`` and return the decoded JSON response."""
    if not url.startswith("https://"):
        raise AuditError(f"refusing to GET a non-HTTPS URL: {url}")
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
        return json.load(response)


def query_osv(coordinates: list[Coordinate]) -> dict[str, set[Coordinate]]:
    """Return ``{advisory id: affected coordinates}`` for the pinned tree.

    Uses OSV's bulk ``querybatch`` -- one request per 1000 coordinates -- which
    is the same call ``uv audit`` makes, minus its exit-code defect.
    """
    hits: dict[str, set[Coordinate]] = {}
    for start in range(0, len(coordinates), _OSV_BATCH_LIMIT):
        chunk = coordinates[start : start + _OSV_BATCH_LIMIT]
        payload = {
            "queries": [
                {
                    "package": {"ecosystem": c.ecosystem, "name": c.name},
                    "version": c.version,
                }
                for c in chunk
            ]
        }
        try:
            response = _post_json(_OSV_QUERYBATCH, payload)
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise AuditError(f"OSV is unreachable: {error}") from error
        results = response.get("results", [])
        for coord, result in zip(chunk, results, strict=False):
            for vuln in (result or {}).get("vulns", ()):
                identifier = vuln.get("id")
                if identifier:
                    hits.setdefault(identifier, set()).add(coord)
    return hits


def describe(identifier: str) -> dict[str, Any]:
    """Return the advisory's summary, aliases and severity, best-effort.

    A description that cannot be fetched degrades the report, never the
    verdict: the advisory id alone is enough to fail the gate.
    """
    try:
        record = _get_json(_OSV_VULN + identifier)
    except (urllib.error.URLError, OSError, ValueError, AuditError):
        # Detail is a nicety; the advisory id alone carries the verdict.
        return {"summary": "", "aliases": [], "severity": ""}
    text = (record.get("summary") or record.get("details") or "").strip()
    summary = text.splitlines()[0][:200] if text else ""
    specific = record.get("database_specific") or {}
    severity = str(specific.get("severity") or "") if isinstance(specific, dict) else ""
    return {
        "summary": summary,
        "aliases": sorted(record.get("aliases") or []),
        "severity": severity,
    }


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------


@dataclass
class Finding:
    """One advisory affecting this repository's pinned dependencies."""

    id: str
    aliases: list[str]
    summary: str
    severity: str
    packages: list[str]
    surfaces: list[str]
    suppressed_by: Suppression | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the machine-readable form of this finding."""
        return {
            "id": self.id,
            "aliases": self.aliases,
            "summary": self.summary,
            "severity": self.severity,
            "packages": self.packages,
            "surfaces": self.surfaces,
            "suppressed": self.suppressed_by is not None,
            "suppression_reason": (
                self.suppressed_by.reason if self.suppressed_by else None
            ),
            "suppression_expires": (
                self.suppressed_by.expires.isoformat() if self.suppressed_by else None
            ),
        }


@dataclass
class Report:
    """The audit's whole result, human- and machine-readable."""

    surfaces: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    expired: list[Suppression] = field(default_factory=list)
    stale: list[Suppression] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        """Return the findings no live suppression covers."""
        return [f for f in self.findings if f.suppressed_by is None]

    @property
    def exit_code(self) -> int:
        """Return the gate's verdict: 0 only when nothing blocks."""
        return EXIT_FINDINGS if (self.blocking or self.expired) else EXIT_OK

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON report body."""
        return {
            "schema": "vaultspec.dependency-audit/1",
            "generated": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
            "repository": REPO_ROOT.name,
            "surfaces": self.surfaces,
            "exit_code": self.exit_code,
            "gating": True,
            "findings": [f.as_dict() for f in self.findings],
            "expired_suppressions": [
                {"id": s.id, "reason": s.reason, "expires": s.expires.isoformat()}
                for s in self.expired
            ],
            "stale_suppressions": [s.id for s in self.stale],
            "probes": self.probes,
        }


def build_report(
    coordinates: list[Coordinate],
    hits: dict[str, set[Coordinate]],
    suppressions: list[Suppression],
    *,
    today: _dt.date,
    describe_fn: Any = describe,
) -> Report:
    """Turn a raw OSV result into the audit's verdict.

    Pure apart from ``describe_fn``, so the gating behaviour is testable
    without a network call.
    """
    report = Report()
    for coord in coordinates:
        report.surfaces[coord.surface] = report.surfaces.get(coord.surface, 0) + 1

    live = {s.id: s for s in suppressions if not s.expired(today)}
    report.expired = sorted(
        (s for s in suppressions if s.expired(today)), key=lambda s: s.id
    )
    used: set[str] = set()
    # OSV returns the same advisory under several ids (GHSA-..., PYSEC-...,
    # CVE-...). Report each advisory once, under the first id encountered,
    # with the rest shown as its aliases.
    seen_ids: set[str] = set()

    for identifier in sorted(hits):
        if identifier in seen_ids:
            continue
        detail = describe_fn(identifier)
        aliases = list(detail.get("aliases") or [])
        seen_ids.add(identifier)
        seen_ids.update(aliases)
        covering = None
        for key in (identifier, *aliases):
            if key in live:
                covering = live[key]
                used.add(key)
                break
        merged: set[Coordinate] = set()
        for key in (identifier, *aliases):
            merged |= hits.get(key, set())
        affected = sorted(merged)
        report.findings.append(
            Finding(
                id=identifier,
                aliases=aliases,
                summary=detail.get("summary", ""),
                severity=detail.get("severity", ""),
                packages=[f"{c.name} {c.version}" for c in affected],
                surfaces=sorted({c.surface for c in affected}),
                suppressed_by=covering,
            )
        )

    report.stale = sorted(
        (s for s in live.values() if s.id not in used), key=lambda s: s.id
    )
    return report


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render(report: Report) -> str:
    """Return the human summary."""
    lines: list[str] = []
    scanned = ", ".join(
        f"{count} {surface}" for surface, count in sorted(report.surfaces.items())
    )
    lines.append(f"dependency audit (GATES) -- scanned {scanned or 'nothing'}")
    for probe in report.probes:
        lines.append(f"  probe: {probe} (injected via --extra-package)")

    for finding in report.findings:
        mark = "SUPPRESSED" if finding.suppressed_by else "FINDING"
        alias = f" ({', '.join(finding.aliases)})" if finding.aliases else ""
        lines.append(f"  {mark:11s} {finding.id}{alias} [{'/'.join(finding.surfaces)}]")
        lines.append(f"      packages: {', '.join(finding.packages)}")
        if finding.summary:
            lines.append(f"      {finding.summary}")
        if finding.suppressed_by:
            lines.append(
                f"      accepted until {finding.suppressed_by.expires.isoformat()}: "
                f"{finding.suppressed_by.reason}"
            )

    for suppression in report.expired:
        lines.append(
            f"  EXPIRED     {suppression.id} -- the acceptance lapsed on "
            f"{suppression.expires.isoformat()}; re-triage it or fix the dependency."
        )
    for suppression in report.stale:
        lines.append(
            f"  stale       {suppression.id} matches nothing in the tree; "
            "delete it from the allowlist."
        )

    if report.exit_code == EXIT_OK:
        suppressed = len(report.findings)
        tail = f" ({suppressed} suppressed)" if suppressed else ""
        lines.append(f"PASS: no unaccepted advisories{tail}.")
    else:
        plural = "y" if len(report.blocking) == 1 else "ies"
        expired = (
            f", {len(report.expired)} expired suppression(s)" if report.expired else ""
        )
        lines.append(
            f"FAIL: {len(report.blocking)} unaccepted advisor{plural}{expired}."
        )
    return "\n".join(lines)


def write_artifact(report: Report) -> Path | None:
    """Write the JSON report when ``VAULTSPEC_CI_REPORTS`` names a directory.

    With the variable unset nothing is written: cadrumo adopts the whole
    standard and simply never sets it.
    """
    target = os.environ.get("VAULTSPEC_CI_REPORTS")
    if not target:
        return None
    directory = Path(target)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "dependency-audit.json"
    path.write_text(json.dumps(report.as_dict(), indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def _parse_extra(raw: str) -> Coordinate:
    """Parse an ``ECOSYSTEM:NAME:VERSION`` self-test coordinate."""
    parts = raw.split(":")
    if len(parts) != 3 or not all(parts):
        raise AuditError(
            f"--extra-package {raw!r} is not ECOSYSTEM:NAME:VERSION "
            "(e.g. PyPI:requests:2.19.0)"
        )
    return Coordinate(parts[0], parts[1], parts[2], "--extra-package")


def main(argv: list[str] | None = None) -> int:
    """Run the dependency audit gate; return its exit code."""
    parser = argparse.ArgumentParser(
        prog="dependency-audit",
        description="Gate on published advisories against pinned dependencies.",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the machine report on stdout"
    )
    parser.add_argument(
        "--extra-package",
        action="append",
        default=[],
        metavar="ECOSYSTEM:NAME:VERSION",
        help="inject one coordinate; used to prove the gate can fail",
    )
    args = parser.parse_args(argv)

    try:
        coordinates = collect_coordinates()
        probes: list[str] = []
        for raw in args.extra_package:
            extra = _parse_extra(raw)
            coordinates.append(extra)
            probes.append(f"{extra.ecosystem}:{extra.name}:{extra.version}")
        if not coordinates:
            raise AuditError(
                "no lockfile found; the audit has nothing to check, which is "
                "not the same as a clean tree."
            )
        suppressions = load_suppressions()
        hits = query_osv(coordinates)
        report = build_report(coordinates, hits, suppressions, today=_dt.date.today())
        report.probes = probes
    except AuditError as error:
        print(f"ERROR: dependency audit could not complete: {error}", file=sys.stderr)
        return EXIT_BROKEN

    artifact = write_artifact(report)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(render(report))
        if artifact:
            print(f"report: {artifact}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
