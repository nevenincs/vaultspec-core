"""Row-contract detection rule (``PLAN040``).

Scans the source text for lines that resemble a Step row but violate
the contract: malformed checkbox glyphs (``[]``, ``[X]``, ``[/]``),
missing ``;`` separator between action and scope, missing trailing
period, or absent inline-backtick scope clause. The parser silently
skips these rows; this rule surfaces them so the writer can repair
them rather than letting them fall out of the model.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_row_contract"]


_RE_STARTS_LIKE_STEP = re.compile(r"^- +\[")
_RE_VALID_STEP_HEAD = re.compile(
    r"^- +\[[ x]\] +`[SPW][\w.]*`",
)
_RE_HAS_BACKTICK_SCOPE = re.compile(r";\s*`[^`]+`\s*\.?\s*$")


def check_row_contract(plan: Plan, source_text: str) -> list[Finding]:
    """Yield findings for lines that look like Step rows but break the contract.

    Args:
        plan: Parsed :class:`Plan`. Required by the harness signature; not
            used directly because the row-contract failures (malformed
            checkbox, missing separator, missing scope) describe lines
            the parser silently skipped, so they never reached
            ``plan.steps`` to begin with.
        source_text: Raw markdown body, scanned line-by-line for
            row-shaped lines that fail one of the contract regexes.
    """
    del plan
    findings: list[Finding] = []
    for index, raw_line in enumerate(source_text.splitlines(), start=1):
        line = raw_line.rstrip()
        if not _RE_STARTS_LIKE_STEP.match(line):
            continue
        if not _RE_VALID_STEP_HEAD.match(line):
            findings.append(
                Finding(
                    code="PLAN040",
                    severity=Severity.ERROR,
                    message=(
                        "Line begins like a Step row but violates the "
                        "header contract (checkbox shape, identifier, "
                        "or display-path backticks): "
                        f"{line!r}"
                    ),
                    line_number=index,
                    fix_hint=(
                        "Repair the row to match: '- [ ] `<display-path>` - "
                        "imperative-verb action; `path/to/file.ext`.'"
                    ),
                    autofixable=False,
                ),
            )
            continue
        if ";" not in line:
            findings.append(
                Finding(
                    code="PLAN040",
                    severity=Severity.ERROR,
                    message=(
                        "Step row missing ';' separator between action "
                        f"and scope: {line!r}"
                    ),
                    line_number=index,
                    fix_hint=(
                        "Insert '; `path/to/file.ext`.' after the "
                        "imperative-verb action."
                    ),
                    autofixable=False,
                ),
            )
            continue
        if not _RE_HAS_BACKTICK_SCOPE.search(line):
            findings.append(
                Finding(
                    code="PLAN040",
                    severity=Severity.ERROR,
                    message=(
                        "Step row scope clause must be wrapped in inline "
                        f"backticks and terminated with '.': {line!r}"
                    ),
                    line_number=index,
                    fix_hint=(
                        "Format the scope as '`path/to/file.ext`.' at the row tail."
                    ),
                    autofixable=False,
                ),
            )
    return findings
