"""Config module unit test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def clean_config() -> Generator[None]:
    """Reset the config singleton before and after the test."""
    reset_config()
    yield
    reset_config()
