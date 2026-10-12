"""Pin workspace configuration for one explicit read operation."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from .config import VaultSpecConfig

active_config: ContextVar[tuple[Path, VaultSpecConfig] | None] = ContextVar(
    "config_read_scope", default=None
)


@contextmanager
def config_read_scope(root: Path) -> Generator[VaultSpecConfig]:
    """Resolve current inputs once and restore the caller's scope on exit."""
    from .config import get_config

    root = root.absolute()
    config = get_config(root=root)
    token = active_config.set((root, config))
    try:
        yield config
    finally:
        active_config.reset(token)
