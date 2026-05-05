"""Display-path-recomputation autofix.

Re-parses ``source_text`` into a :class:`Plan` and re-emits the
canonical Markdown form. Display paths on every row, Phase heading,
and Wave heading are recomputed from the current ancestor chain;
canonical identifiers (``S##``/``P##``/``W##``) are preserved
exactly because the parser keeps them and the serialiser uses them
verbatim.

This autofix is the recovery-from-hand-edits path: it catches drift
introduced by manual edits or interrupted multi-step CLI operations.
Routine CLI workflows do not produce display-path drift because the
mutating commands recompute the path on every write.
"""

from __future__ import annotations

from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan

__all__ = ["fix_display_paths"]


def fix_display_paths(source_text: str) -> str:
    """Recompute display paths via parse + serialise round-trip."""
    plan = parse_plan(source_text)
    return serialise_plan(plan)
