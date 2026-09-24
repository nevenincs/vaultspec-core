"""Write real ADR records for the crossref tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["write_adr"]


def write_adr(
    root: Path,
    stem: str,
    *,
    feature: str = "demo",
    title: str | None = None,
    status: str = "accepted",
    problem: str = "A problem worth deciding.",
    implementation: str = "The decision is implemented plainly.",
    related: tuple[str, ...] = (),
    extra: str = "",
) -> Path:
    """Write one ADR with real frontmatter and the decision sections.

    Args:
        root: The workspace root.
        stem: The file stem.
        feature: The feature tag, without ``#``.
        title: The title; the stem when omitted.
        status: The status token on the title heading.
        problem: The Problem Statement text.
        implementation: The Implementation text.
        related: Stems the record's ``related:`` names.
        extra: A body section appended after the decision sections.

    Returns:
        The written path.
    """
    path = root / ".vault" / "adr" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    front = ["---", "tags:", "  - '#adr'", f"  - '#{feature}'", "date: '2026-01-02'"]
    if related:
        front += ["related:", *(f"  - '[[{link}]]'" for link in related)]
    front.append("---")
    body = [
        "",
        f"# `{feature}` adr: `{title or stem}` | (**status:** `{status}`)",
        "",
        "## Problem Statement",
        "",
        problem,
        "",
        "## Implementation",
        "",
        implementation,
        "",
        "## Rationale",
        "",
        "It is the simplest option that holds.",
        "",
    ]
    if extra:
        body += [extra, ""]
    path.write_text("\n".join(front + body), encoding="utf-8")
    return path
