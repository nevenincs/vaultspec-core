"""Autofix harness composing every autofix transformation in canonical order.

Running ``apply_all_fixes`` repeatedly is idempotent: once every
autofixable violation is resolved, subsequent invocations make no
changes. The harness is the implementation of ``vault plan check
--fix`` once the CLI command lands in W02.P07.
"""

from __future__ import annotations

__all__ = ["apply_all_fixes"]


def apply_all_fixes(source_text: str) -> str:
    """Apply every autofix transformation to ``source_text`` in canonical order.

    Order:

    1. Checkbox-spacing normalisation (``[ ]`` / ``[x]``).
    2. Separator normalisation (em-dash / en-dash to ASCII spaced
       hyphen).
    3. Trailing-whitespace removal on row sentences.
    4. Display-path recomputation against the current ancestor chain.

    The first three operate on raw text; the fourth re-parses, edits
    the model, and re-serialises. The ordering matters: separator
    normalisation must run before display-path recomputation so that
    rows previously broken by an em-dash become parseable Steps and
    can be subjected to the path check.

    Args:
        source_text: Raw markdown text of a plan document.

    Returns:
        Markdown text with every autofixable violation resolved. The
        canonical identifiers (``S##``/``P##``/``W##``) are preserved
        exactly.
    """
    from vaultspec_core.plan.fixes.checkbox_fix import fix_checkbox_spacing
    from vaultspec_core.plan.fixes.display_path_fix import fix_display_paths
    from vaultspec_core.plan.fixes.separator_fix import fix_separator
    from vaultspec_core.plan.fixes.whitespace_fix import fix_trailing_whitespace

    text = fix_checkbox_spacing(source_text)
    text = fix_separator(text)
    text = fix_trailing_whitespace(text)
    text = fix_display_paths(text)
    return text
