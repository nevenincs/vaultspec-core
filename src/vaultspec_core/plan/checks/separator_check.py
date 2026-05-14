"""Separator-convention detection rule (``PLAN060``).

The convention ADR's *Separator conventions* section forbids the
em-dash (U+2014) and en-dash (U+2013) anywhere in plan body, plan
headings, frontmatter, and markdown-comment hints. Detection is a
character-level scan; the autofix in
:mod:`vaultspec_core.plan.fixes.separator_fix` replaces every
occurrence with an ASCII spaced hyphen.
"""

from __future__ import annotations

from vaultspec_core.plan.checks._base import Finding, Severity

__all__ = ["check_separator"]


# Forbidden dash codepoints declared via Unicode-name escape so this
# source file does not itself trip RUF001 / RUF003 ambiguous-character
# warnings while keeping the lookup keys as the literal characters.
_EM_DASH = "\N{EM DASH}"
_EN_DASH = "\N{EN DASH}"

_FORBIDDEN_DASHES = {
    _EM_DASH: "em-dash (U+2014)",
    _EN_DASH: "en-dash (U+2013)",
}


def check_separator(source_text: str) -> list[Finding]:
    """Yield one Finding per line that contains a forbidden dash character."""
    findings: list[Finding] = []
    for index, line in enumerate(source_text.splitlines(), start=1):
        for char, label in _FORBIDDEN_DASHES.items():
            if char in line:
                findings.append(
                    Finding(
                        code="PLAN060",
                        severity=Severity.ERROR,
                        message=(
                            f"Line contains forbidden {label}; the "
                            "convention requires ASCII spaced hyphens."
                        ),
                        line_number=index,
                        fix_hint=(
                            "Replace the dash with ' - ' (space, ASCII "
                            "hyphen-minus, space). "
                            "'vaultspec-core vault plan check --fix' "
                            "applies this replacement automatically."
                        ),
                        autofixable=True,
                    ),
                )
    return findings
