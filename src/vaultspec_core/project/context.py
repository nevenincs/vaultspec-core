"""Backend-owned collection, opt-in and compact result assembly."""

from __future__ import annotations

import time
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY, resolve_credential
from vaultspec_core.search._transport import JevClient

from .collect import collect, validate_repo
from .models import COLLECT_SECONDS, MAX_ITEMS, RANK_SECONDS, SHORTLIST, compact
from .ranking import (
    Ranking,
    attention,
    lexical_fit,
    load_previous,
    ordered,
    rank,
    shortlist,
)

if TYPE_CHECKING:
    from pathlib import Path


def project_context(
    root: Path,
    objective: str,
    *,
    repo: str | None = None,
    limit: int = 5,
    previous: Path | None = None,
    hosted: bool = True,
) -> dict[str, object]:
    """Return fresh observations and an attention order, never execution permission."""
    objective = objective.strip()
    if not objective or len(objective.encode()) > 1000:
        raise ValueError("objective must contain 1..1000 UTF-8 bytes")
    if not 1 <= limit <= MAX_ITEMS:
        raise ValueError(f"limit must be 1..{MAX_ITEMS}")
    validate_repo(repo)
    saved = load_previous(previous)
    started = time.monotonic()
    observed = datetime.now(UTC).isoformat()
    snapshot = collect(root, repo)
    candidates = shortlist(objective, snapshot.items)
    credential = (
        resolve_credential(VAULTSPEC_CORE_TYPESAFE_API_KEY, root) if hosted else None
    )
    ranking = Ranking("disabled" if not hosted else "not_configured")
    if credential and candidates:
        try:
            with JevClient(credential.key, max_attempts=1) as client:
                ranking = rank(objective, candidates, client, saved)
        except ValueError:
            ranking = Ranking("unavailable", reason="credential_rejected")
    elif credential:
        ranking = Ranking("no_candidates")
    ranked = ordered(objective, candidates, ranking)
    selected = []
    for item in ranked[:limit]:
        selected.append(
            {
                **asdict(item),
                "attention_band": attention(item),
                "objective_fit": ranking.scores.get(item.id)
                if ranking.status == "available"
                else round(lexical_fit(objective, item), 3),
                "fit_source": "hosted_score_0_to_3"
                if ranking.status == "available"
                else "lexical_overlap_0_to_1",
                "next_action": (
                    "Inspect blocker or shared-branch signals before assigning work"
                )
                if attention(item) == 0
                else "Confirm scope, owner and dependencies before assigning work",
            }
        )
    usage = asdict(ranking)
    usage.pop("judgments")
    usage.pop("scores")
    return {
        "objective": compact(objective, 1000),
        "observed_from": observed,
        "observed_to": datetime.now(UTC).isoformat(),
        "items": selected,
        "sources": [asdict(source) for source in snapshot.sources],
        "observed_items": len(snapshot.items),
        "shortlisted": len(candidates),
        "returned": len(selected),
        "truncated": len(snapshot.items) > len(selected),
        "uncollected": [
            "boards",
            "milestones",
            "dependency_edges",
            "vault_plans",
            "untracked_files",
        ],
        "ordering": (
            "Blocker and shared-branch signals, then tracked changes, then other work; "
            "objective fit "
            "and recent activity break ties. This is an attention order, "
            "not an execution plan."
        ),
        "hosted": usage,
        "judgments": ranking.judgments,
        "collection": {
            "commands": snapshot.commands,
            "bytes_read": snapshot.bytes_read,
        },
        "bounds": {
            "collection_seconds": COLLECT_SECONDS,
            "hosted_seconds": RANK_SECONDS,
            "shortlist": SHORTLIST,
        },
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }
