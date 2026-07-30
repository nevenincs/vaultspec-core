"""Guards for the ``uv audit`` supply-chain gate wrapper.

The gate's whole job is to decide which advisories are allowed through. That
decision is :func:`dev.audit.dependency_audit.untriaged_advisories` over the
:data:`dev.audit.dependency_audit.IGNORED` allowlist, and it is the one piece of
the script that runs without a network round trip.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from dev.audit.dependency_audit import IGNORED, untriaged_advisories

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

#: OSV, CVE, and GitHub advisory identifier shapes. An entry that matches none
#: of these can never equal an ID the OSV query returns, so it would silently
#: allowlist nothing.
ADVISORY_ID = re.compile(
    r"^(?:PYSEC-\d{4}-\d+"
    r"|CVE-\d{4}-\d+"
    r"|GHSA-[a-z0-9]{4}(?:-[a-z0-9]{4}){2})$"
)


def test_untriaged_advisories_reports_only_ids_outside_the_allowlist() -> None:
    """An advisory the gate has never triaged must reach the caller."""
    triaged = next(iter(IGNORED))
    assert untriaged_advisories({triaged, "GHSA-aaaa-bbbb-cccc"}) == [
        "GHSA-aaaa-bbbb-cccc"
    ]


def test_untriaged_advisories_passes_a_fully_triaged_tree() -> None:
    """Every advisory being on the allowlist is the passing case."""
    assert untriaged_advisories(set(IGNORED)) == []


def test_untriaged_advisories_passes_a_clean_tree() -> None:
    """No advisories at all is also the passing case."""
    assert untriaged_advisories(set()) == []


def test_untriaged_advisories_returns_a_sorted_report() -> None:
    """The failure message lists IDs in a stable order across runs."""
    findings = {"PYSEC-2030-2", "CVE-2030-1", "GHSA-zzzz-yyyy-xxxx"}
    assert untriaged_advisories(findings) == sorted(findings)


def test_untriaged_advisories_does_not_mutate_its_input() -> None:
    """The caller reuses its advisory set for the pass-through report."""
    findings = {"CVE-2030-1", *IGNORED}
    snapshot = set(findings)
    untriaged_advisories(findings)
    assert findings == snapshot


@pytest.mark.parametrize("advisory", sorted(IGNORED))
def test_every_allowlisted_id_has_a_real_advisory_shape(advisory: str) -> None:
    """A malformed entry allowlists nothing and reads as though it does."""
    assert ADVISORY_ID.match(advisory), advisory


def test_every_allowlisted_id_is_justified_in_the_module_docstring_or_comment(
    repo_root: Path,
) -> None:
    """Each suppression carries its written triage next to the allowlist.

    A bare identifier in the set is indistinguishable from a forgotten one; the
    gate's own module documents why each is disputed or unfixable, and that is
    the only record of the decision.
    """
    gate = repo_root / "dev" / "audit" / "dependency_audit.py"
    source = gate.read_text(encoding="utf-8")
    prose = "\n".join(
        line for line in source.splitlines() if line.lstrip().startswith("#")
    )
    undocumented = sorted(entry for entry in IGNORED if entry not in prose)
    assert not undocumented, (
        f"allowlisted advisories with no triage comment: {undocumented}"
    )
