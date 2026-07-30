"""Minimal local type stub for the untyped third-party ``radon.complexity`` module.

``radon`` ships no ``py.typed`` marker, so basedpyright treats it as fully
untyped even though the installed source is Python with no annotations to
lose. This stub covers only the surface this codebase actually calls
(:func:`cc_rank`, :func:`cc_visit`), typing the returned blocks by the
``complexity``/``name`` attributes actually read at call sites - a subset of
the real ``Function``/``Class`` namedtuples in ``radon.visitors``.
"""

from typing import Any

class ComplexityBlock:
    complexity: int
    name: str

def cc_rank(cc: int) -> str: ...
def cc_visit(code: str, **kwargs: Any) -> list[ComplexityBlock]: ...
