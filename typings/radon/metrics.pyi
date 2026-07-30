"""Minimal local type stub for the untyped third-party ``radon.metrics`` module.

Covers only the surface this codebase actually calls (:func:`mi_rank`,
:func:`mi_visit`). See ``typings/radon/complexity.pyi`` for why a stub is
needed at all.
"""

def mi_visit(code: str, multi: bool) -> float: ...
def mi_rank(score: float) -> str: ...
