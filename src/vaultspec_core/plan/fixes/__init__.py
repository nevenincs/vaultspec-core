"""Idempotent autofix transformations for ``vault plan check --fix``.

Every autofix preserves canonical identifiers exactly; no autofix
mutates an ``S##``, ``P##``, or ``W##`` token. The autofix list is
deliberately conservative per the convention ADR's *check --fix*
section: anything that would re-pad an existing identifier or
otherwise renumber is reported as a finding but not auto-resolved.
"""

from __future__ import annotations

from vaultspec_core.plan.fixes._harness import apply_all_fixes

__all__ = ["apply_all_fixes"]
