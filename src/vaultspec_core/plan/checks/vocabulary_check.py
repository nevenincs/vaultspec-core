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
from vaultspec_core.vaultcore.markdown import iter_headings

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_vocabulary"]


_APPROVED_NOUNS = frozenset({"Epic", "Wave", "Phase", "Step"})

# Structural noun candidates in two heading-text shapes:
# * ``Wave `W01` - title`` / ``Phase `W01.P01` - title`` at level two or
#   three (backticked id)
# * ``Epic intent`` at level two (no backtick; bare ``intent`` after the noun)
_RE_HEADING_WITH_BACKTICK = re.compile(r"(\w+) +`")
_RE_HEADING_BARE_INTENT = re.compile(r"(\w+) +intent")


def check_vocabulary(plan: Plan, source_text: str) -> list[Finding]:
    """Detect non-canonical structural nouns in heading positions.

    Walks every heading line in ``source_text`` and reports a finding
    when the leading noun (between the ``##``/``###`` marker and either
    a backtick-quoted identifier or the literal ``intent`` keyword) is
    not one of the four approved structural nouns. Both shapes are
    treated as structural positions per the convention ADR.

    Args:
        plan: Parsed :class:`Plan`. Used to scope the check to heading
            line numbers known to the model so off-template prose lines
            cannot produce spurious findings; an unused-but-required
            handle into the harness.
        source_text: Raw markdown body, scanned line-by-line.
    """
    del plan
    findings: list[Finding] = []
    for heading in iter_headings(source_text):
        match = None
        if heading.level in (2, 3):
            match = _RE_HEADING_WITH_BACKTICK.match(heading.text)
        if match is None and heading.level == 2:
            match = _RE_HEADING_BARE_INTENT.fullmatch(heading.text)
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
                line_number=heading.line,
                fix_hint=(
                    "Replace the noun with one of the canonical four "
                    "(Epic, Wave, Phase, Step) per the convention ADR's "
                    "Approved structural vocabulary."
                ),
                autofixable=False,
            ),
        )
    return findings
