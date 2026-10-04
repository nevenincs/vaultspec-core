"""Pure value parsers shared by the configuration registry and public API."""

from __future__ import annotations

__all__ = ["parse_csv_list", "parse_float_or_none", "parse_int_or_none"]


def parse_csv_list(value: str) -> list[str]:
    """Split a comma-separated string into a list of stripped, non-empty items.

    Args:
        value: Comma-separated string to split.

    Returns:
        List of non-empty, whitespace-stripped tokens.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_int_or_none(value: str | None) -> int | None:
    """Parse *value* as an ``int``, returning ``None`` on failure.

    Args:
        value: String to parse.

    Returns:
        Parsed integer, or ``None`` if the string cannot be converted.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_float_or_none(value: str | None) -> float | None:
    """Parse *value* as a ``float``, returning ``None`` on failure.

    Args:
        value: String to parse.

    Returns:
        Parsed float, or ``None`` if the string cannot be converted.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
