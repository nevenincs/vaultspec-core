"""Approved-structural-vocabulary detection rule (``PLAN050``).

The convention ADR's *Approved structural vocabulary* table restricts
structural nouns to ``Epic``, ``Wave``, ``Phase``, and ``Step``. The
check fires only on **structural positions** (heading lines and
container-identifier code spans); narrative prose inside intent
paragraphs is exempt.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_vocabulary"]


_APPROVED_NOUNS = frozenset({"Epic", "Wave", "Phase", "Step"})

# Structural noun candidates: any heading-leading word that follows the
# canonical container-heading shapes used by the convention.
_RE_HEADING = re.compile(r"^#{2,3} +(\w+) +`")


def check_vocabulary(plan: Plan, source_text: str) -> list[Finding]:  # noqa: ARG001
    """Detect non-canonical structural nouns in heading positions.

    The check walks every heading line in ``source_text`` and reports
    a finding when the leading noun (between the ``##``/``###`` marker
    and the backtick-quoted identifier) is not one of the four
    approved structural nouns.
    """
    findings: list[Finding] = []
    for index, raw_line in enumerate(source_text.splitlines(), start=1):
        match = _RE_HEADING.match(raw_line)
        if match is None:
            continue
        noun = match.group(1)
        if noun in _APPROVED_NOUNS:
            continue
        findings.append(
            Finding(
                code="PLAN050",
                severity=Severity.ERROR,
                message=(
                    f"Heading uses non-canonical structural noun "
                    f"'{noun}'; approved nouns are Epic, Wave, Phase, "
                    "Step."
                ),
                line_number=index,
                fix_hint=(
                    "Replace the noun with one of the canonical four "
                    "(Epic, Wave, Phase, Step) per the convention ADR's "
                    "Approved structural vocabulary."
                ),
                autofixable=False,
            ),
        )
    return findings
