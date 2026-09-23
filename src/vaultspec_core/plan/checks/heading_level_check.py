"""Container-heading level detection rule (``PLAN070``).

The parser anchors its container headings to an exact level: a Wave is
recognised only at ``##`` and a Phase only at ``###``. A heading that
names a container at any other level matches neither pattern, so the
container disappears from the parsed model while the Step rows beneath
it survive and silently re-parent to whatever container preceded it.
Nothing in the resulting plan looks wrong: the counts are simply lower
than the document's own text claims.

This is reachable through ordinary tooling rather than hand-editing.
A markdown formatter correcting a heading-increment warning will demote
a Phase from ``###`` to ``##``, which reads as a cosmetic fix and costs
the plan a whole container.

The rule therefore scans the raw source for any heading that names a
container, and reports the ones the parser cannot see. It reads the
source text rather than the parsed model precisely because the parsed
model is where the evidence has already been lost.
"""

from __future__ import annotations

import re

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.vaultcore.markdown import iter_headings

__all__ = ["check_heading_levels"]


# The text of a heading naming a container, at whatever level it stands.
_RE_CONTAINER_HEADING = re.compile(r"(?P<noun>Wave|Phase) +`(?P<id>[^`]+)`")

#: The one heading level at which the parser recognises each container.
_CANONICAL_LEVEL = {"Wave": 2, "Phase": 3}


def check_heading_levels(source_text: str) -> list[Finding]:
    """Yield one Finding per container heading the parser cannot recognise.

    Args:
        source_text: Original markdown text of the plan document.

    Returns:
        A list of :class:`Finding`, one per mislevelled container heading.
    """
    findings: list[Finding] = []
    for heading in iter_headings(source_text):
        match = _RE_CONTAINER_HEADING.match(heading.text)
        if match is None:
            continue

        noun = match.group("noun")
        level = heading.level
        canonical = _CANONICAL_LEVEL[noun]
        if level == canonical:
            continue

        findings.append(
            Finding(
                code="PLAN070",
                severity=Severity.ERROR,
                message=(
                    f"{noun} `{match.group('id')}` is written at heading level "
                    f"{level}, but the parser recognises a {noun} only at level "
                    f"{canonical}. This container is dropped from the parsed "
                    "plan while its Step rows survive and re-parent silently, "
                    "so the plan under-reports its own structure."
                ),
                line_number=heading.line,
                fix_hint=(
                    f"Restore the heading to {'#' * canonical} "
                    f"{noun} `{match.group('id')}` - and never let a markdown "
                    "formatter change a container heading's level."
                ),
                autofixable=False,
            )
        )
    return findings
