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

__all__ = ["check_heading_levels"]


# Any heading naming a container, at any level, capturing the level so the
# canonical one can be compared against it.
_RE_CONTAINER_HEADING = re.compile(
    r"^(?P<hashes>#{1,6}) +(?P<noun>Wave|Phase) +`(?P<id>[^`]+)`",
)

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
    for index, line in enumerate(source_text.splitlines(), start=1):
        match = _RE_CONTAINER_HEADING.match(line)
        if match is None:
            continue

        noun = match.group("noun")
        level = len(match.group("hashes"))
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
                line_number=index,
                fix_hint=(
                    f"Restore the heading to {'#' * canonical} "
                    f"{noun} `{match.group('id')}` - and never let a markdown "
                    "formatter change a container heading's level."
                ),
                autofixable=False,
            )
        )
    return findings
