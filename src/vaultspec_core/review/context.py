"""Credential opt-in and local fallback for review evidence selection."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import TYPE_CHECKING

from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY, resolve_credential
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.search._transport import JevClient

from .collect import (
    COLLECT_SECONDS,
    MAX_CANDIDATES,
    MAX_DIFF_BYTES,
    MAX_LINES,
    MAX_SNIPPET_BYTES,
    collect,
    digest,
)
from .ranking import RANK_SECONDS, Ranking, load_previous, rank

if TYPE_CHECKING:
    from pathlib import Path


def review_context(
    root: Path,
    objective: str,
    *,
    base: str,
    candidates: list[str],
    head: str | None = None,
    limit: int = 3,
    previous: Path | None = None,
    hosted: bool = True,
) -> dict[str, object]:
    """Select supporting passages, never decide a review or verification outcome."""
    objective = objective.strip()
    if not objective or len(objective.encode()) > 1000:
        raise ValueError("objective must contain 1..1000 UTF-8 bytes")
    if not 1 <= limit <= 6:
        raise ValueError("limit must be 1..6")
    started = time.monotonic()
    saved = load_previous(previous)
    snapshot = collect(root, base, head, candidates)
    ranking = Ranking("disabled" if not hosted else "not_configured")
    credential = None
    if hosted:
        try:
            credential = resolve_credential(VAULTSPEC_CORE_TYPESAFE_API_KEY, root)
        except (VaultSpecError, OSError, ValueError):
            ranking = Ranking("unavailable", reason="credential_unavailable")
    if credential:
        if credential.key in objective:
            raise ValueError("objective contains the configured credential")
        safe = []
        for item in snapshot.snippets:
            if credential.key in item.content or credential.key in item.locator:
                snapshot.excluded.append(
                    {"candidate": item.id, "reason": "credential_in_source"}
                )
            else:
                safe.append(item)
        snapshot.snippets = safe
        if credential.key in snapshot.diff:
            snapshot.diff = ""
            snapshot.diff_reason = "credential_in_diff"
        if snapshot.diff_reason:
            ranking = Ranking("unavailable", reason=snapshot.diff_reason)
        elif not snapshot.diff:
            ranking = Ranking("not_needed", reason="no_tracked_diff")
        elif not snapshot.snippets:
            ranking = Ranking("not_needed", reason="no_candidates")
        else:
            try:
                with JevClient(credential.key, max_attempts=1) as client:
                    ranking = rank(objective, snapshot, client, saved)
            except ValueError:
                ranking = Ranking("unavailable", reason="credential_rejected")
    ordered = sorted(
        snapshot.snippets, key=lambda item: -ranking.scores.get(item.id, 0)
    )
    selected = [
        {**asdict(item), "relevance": ranking.scores.get(item.id)}
        for item in ordered[:limit]
    ]
    remaining = [
        {"id": item.id, "locator": item.locator, "sha256": item.sha256}
        for item in ordered[limit:]
    ]
    usage = asdict(ranking)
    usage.pop("scores")
    usage.pop("judgment")
    return {
        "objective": objective,
        "scope": {
            "base": snapshot.base,
            "head": snapshot.head,
            "source": "commit" if snapshot.head else "tracked_working_tree",
            "diff_sha256": digest(snapshot.diff) if not snapshot.diff_reason else None,
            "diff_reason": snapshot.diff_reason,
        },
        "selected": selected,
        "unselected": remaining,
        "excluded": snapshot.excluded,
        "ordering": "hosted_relevance" if ranking.scores else "discovery_order",
        "hosted": usage,
        "judgment": ranking.judgment,
        "bounds": {
            "candidates": MAX_CANDIDATES,
            "lines_per_snippet": MAX_LINES,
            "bytes_per_snippet": MAX_SNIPPET_BYTES,
            "diff_bytes": MAX_DIFF_BYTES,
            "collection_seconds": COLLECT_SECONDS,
            "hosted_seconds": RANK_SECONDS,
        },
        "next_action": (
            "Review the full diff and governing decisions; expand context as needed. "
            "Selection proves neither correctness, verification nor complete coverage. "
            "Untracked files are excluded. Working-tree reads are not atomic."
        ),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }
