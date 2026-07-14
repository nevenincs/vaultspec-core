#!/usr/bin/env python
"""uv-native dependency vulnerability audit gate.

Wraps ``uv audit`` -- uv's native, preview-feature OSV scanner -- so the
CI supply-chain gate is uv-managed end to end and never shells out to
pip.

Two behaviours of the preview ``uv audit`` need handling:

* It exits ``0`` even when advisories are present, so this wrapper
  inspects the output and fails the gate on real findings.
* Its OSV decoder aborts the whole run with "error decoding response
  body" when an advisory's upstream OSV record is malformed. uv issues
  one bulk ``querybatch`` to discover every advisory affecting the
  locked packages, then fetches each advisory's full record; a single
  malformed record kills the run before findings are printed.

When uv aborts with the decode error this wrapper independently repeats
the bulk OSV ``querybatch`` over every locked package to recover the
authoritative set of advisory IDs. If every ID is one this gate has
already triaged (``IGNORED`` -- disputed and unfixable, see the
justfile), the gate passes with a warning. If any untriaged advisory is
present the gate fails, because uv could not evaluate it.

The querybatch repeat uses only the standard library and ``httpx`` (an
existing project dependency); no pip-named tooling is ever invoked.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

# Advisories triaged and explicitly ignored by the supply-chain gate.
# PYSEC-2025-183 (alias CVE-2025-45768) is a disputed, unfixable pyjwt
# advisory pulled transitively by ``mcp``; its OSV record carries a
# malformed empty event object that uv's preview decoder cannot parse.
# GHSA-rrmf-rvhw-rf47 (alias CVE-2025-3000) is a torch.jit.script memory
# corruption with no fixed release (OSV last_affected == 2.12.0, the
# latest version). torch is dev-only tooling here (vaultspec-rag's
# backend, never shipped in the wheel) and nothing in this repository
# invokes torch.jit. Re-triage when a fixed torch release appears.
# PYSEC-2026-3447 is a summary-less setuptools advisory fixed in 83.0.0;
# setuptools 81.0.0 is held back transitively by torch 2.12.1 (upgrading
# would drag torch to 2.13.0, an untested GPU-stack bump owned by its own
# change). setuptools is dev-env build tooling, never shipped in the
# wheel. Re-triage when torch moves to 2.13+ in a deliberate upgrade.
IGNORED: frozenset[str] = frozenset(
    {
        "PYSEC-2025-183",
        "CVE-2025-45768",
        "GHSA-rrmf-rvhw-rf47",
        "CVE-2025-3000",
        "PYSEC-2026-3447",
    }
)

_OSV_QUERYBATCH = "https://api.osv.dev/v1/querybatch"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_UV_LOCK = _REPO_ROOT / "uv.lock"


def untriaged_advisories(advisories: set[str]) -> list[str]:
    """Return advisory IDs present in the dep tree that this gate has not triaged."""
    return sorted(advisories - IGNORED)


def _run_uv_audit() -> str:
    """Run ``uv audit`` and return its combined stdout/stderr."""
    proc = subprocess.run(
        [
            "uv",
            "audit",
            "--preview-features",
            "audit",
            "--frozen",
            *(arg for vid in sorted(IGNORED) for arg in ("--ignore", vid)),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    return proc.stdout + proc.stderr


def _locked_packages() -> list[tuple[str, str]]:
    """Return every ``(name, version)`` pair pinned in ``uv.lock``."""
    data = tomllib.loads(_UV_LOCK.read_text(encoding="utf-8"))
    return [
        (pkg["name"], pkg["version"])
        for pkg in data.get("package", [])
        if "name" in pkg and "version" in pkg
    ]


def _advisory_ids_from_osv() -> set[str]:
    """Repeat uv's bulk OSV querybatch and collect every advisory ID."""
    import httpx

    queries = [
        {"package": {"ecosystem": "PyPI", "name": name}, "version": version}
        for name, version in _locked_packages()
    ]
    ids: set[str] = set()
    # OSV caps querybatch at 1000 queries per request; chunk defensively.
    for start in range(0, len(queries), 1000):
        chunk = queries[start : start + 1000]
        response = httpx.post(_OSV_QUERYBATCH, json={"queries": chunk}, timeout=60.0)
        response.raise_for_status()
        for result in response.json().get("results", []):
            for vuln in result.get("vulns", []):
                if "id" in vuln:
                    ids.add(vuln["id"])
    return ids


def main() -> int:
    """Run the audit gate; return the process exit code."""
    output = _run_uv_audit()
    print(output, end="" if output.endswith("\n") else "\n")

    clean = ("Found no known vulnerabilit", "Found 0 known vulnerabilit")
    if any(marker in output for marker in clean):
        return 0

    if "error decoding response body" not in output:
        # uv audit exits 0 even on findings; a non-clean, non-decode-error
        # run means it printed advisories.
        print("ERROR: uv audit reported vulnerability findings.", file=sys.stderr)
        return 1

    # uv's OSV decoder aborted before printing findings. Independently
    # recover the authoritative advisory set via the bulk OSV query.
    print(
        "uv audit aborted with an OSV decode error; re-running the bulk OSV "
        "query to recover the advisory set."
    )
    try:
        advisories = _advisory_ids_from_osv()
    except Exception as exc:
        print(f"ERROR: could not reach the OSV service: {exc}", file=sys.stderr)
        return 1

    untriaged = untriaged_advisories(advisories)
    if untriaged:
        print(
            "ERROR: the dependency tree carries advisories this gate has not "
            f"triaged: {', '.join(untriaged)}",
            file=sys.stderr,
        )
        return 1

    triaged = ", ".join(sorted(advisories)) or "an advisory"
    print(
        f"WARNING: uv audit could not decode the OSV record for {triaged}. The "
        "bulk OSV query confirms these are the only advisories affecting the "
        "locked dependencies, and each is disputed/unfixable and explicitly "
        "ignored by this gate. Audit passing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
