"""Small, serializable observations shared by collection and ranking."""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA = "vaultspec.project.context.v1"
MAX_ITEMS = 10
SHORTLIST = 12
COLLECT_SECONDS = 10.0
RANK_SECONDS = 5.0


def compact(value: str, limit: int = 240) -> str:
    """Bound text by UTF-8 bytes and remove terminal control characters."""
    clean = " ".join(value.split())
    clean = "".join(char for char in clean if char.isprintable())
    encoded = clean.encode("utf-8")
    if len(encoded) <= limit:
        return clean
    return encoded[: limit - 3].decode("utf-8", errors="ignore") + "..."


@dataclass(frozen=True)
class Item:
    """One observed workstream; facts never imply execution authorization."""

    id: str
    kind: str
    title: str
    updated: str = ""
    facts: dict[str, object] = field(default_factory=dict)
    signals: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ("dependencies", "developer_availability")


@dataclass(frozen=True)
class Source:
    """Coverage and failure are explicit, including a bounded listing window."""

    name: str
    status: str
    count: int = 0
    truncated: bool = False
    reason: str | None = None


@dataclass
class Snapshot:
    """An observation window, not an atomic or complete project inventory."""

    items: list[Item] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    commands: int = 0
    bytes_read: int = 0
