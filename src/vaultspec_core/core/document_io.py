"""Contained document reads with opt-in request byte budgets."""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .corpus_io import open_document

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


class DocumentLimitError(RuntimeError):
    """A document read would exceed the active request's byte budget."""


@dataclass
class DocumentReadBudget:
    """Limits for individual files and all reads in one request."""

    file_bytes: int
    remaining_bytes: int


_READ_BUDGET: ContextVar[DocumentReadBudget | None] = ContextVar(
    "document_read_budget", default=None
)


def document_budget_active() -> bool:
    """Return whether document ingestion must bypass unbounded caches."""
    return _READ_BUDGET.get() is not None


@contextmanager
def document_read_budget(file_bytes: int, total_bytes: int) -> Generator[None]:
    """Apply a fresh read budget and restore the previous context on exit."""
    token = _READ_BUDGET.set(DocumentReadBudget(file_bytes, total_bytes))
    try:
        yield
    finally:
        _READ_BUDGET.reset(token)


def read_document_bytes(path: Path, *, root_dir: Path | None = None) -> bytes:
    """Read a whole document, refusing oversized files before allocating them.

    The bounded read also checks growth after stat. Limit failures deliberately
    differ from filesystem errors so tolerant readers cannot silently skip them.
    """
    budget = _READ_BUDGET.get()
    if budget is None and root_dir is None:
        return path.read_bytes()
    with open_document(path, root_dir=root_dir) as source:
        if budget is None:
            return source.read()
        ceiling = min(budget.file_bytes, budget.remaining_bytes)
        if os.fstat(source.fileno()).st_size > ceiling:
            raise DocumentLimitError(
                "find document byte budget exceeded "
                f"(file limit {budget.file_bytes}, remaining {budget.remaining_bytes})"
            )
        raw = source.read(ceiling + 1)
    if len(raw) > ceiling:
        raise DocumentLimitError("find document grew beyond its byte budget")
    budget.remaining_bytes -= len(raw)
    return raw


def read_document_text(path: Path, *, root_dir: Path | None = None) -> str:
    """Read UTF-8 text with the universal newlines used by Path.read_text."""
    return (
        read_document_bytes(path, root_dir=root_dir)
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
