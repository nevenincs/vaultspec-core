"""Read Git and explicitly selected GitHub state without repository mutations."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vaultspec_core.config import child_environment

from .models import COLLECT_SECONDS, Item, Snapshot, Source, compact

if TYPE_CHECKING:
    from collections.abc import Sequence

_MAX_BYTES = 1_000_000
_BRANCHES = 30
_WORKTREES = 8
_REMOTE_ITEMS = 20
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class CollectionError(Exception):
    """A source could not be read within the collection bounds."""


class Reader:
    """Share one deadline and usage count across fixed-argument subprocess reads."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self.deadline = time.monotonic() + COLLECT_SECONDS

    def run(self, root: Path, args: Sequence[str]) -> str:
        """Read capped stdout; diagnostics omit command output and credentials."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CollectionError("collection_deadline")
        env = {
            **child_environment(),
            "GIT_OPTIONAL_LOCKS": "0",
            "GH_PROMPT_DISABLED": "1",
        }
        self.snapshot.commands += 1
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(
                    args,
                    cwd=root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=remaining,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise CollectionError("collection_deadline") from error
            except OSError as error:
                raise CollectionError("command_unavailable") from error
            size = output.tell()
            self.snapshot.bytes_read += size
            if result.returncode:
                raise CollectionError("command_failed")
            if size > _MAX_BYTES:
                raise CollectionError("output_limit")
            output.seek(0)
            return output.read().decode("utf-8", errors="replace")


def validate_repo(repo: str | None) -> None:
    """Restrict optional remote reads to an explicit GitHub owner/repository."""
    if repo is not None and (len(repo) > 160 or not _REPO.fullmatch(repo)):
        raise ValueError("repo must be OWNER/REPO on github.com")


def parse_worktrees(text: str) -> list[dict[str, str]]:
    """Parse Git's NUL-delimited records, preserving paths containing newlines."""
    records: list[dict[str, str]] = []
    row: dict[str, str] = {}
    for token in text.split("\0"):
        if not token:
            if row:
                records.append(row)
                row = {}
        else:
            key, _, value = token.partition(" ")
            row[key] = value
    if row:
        records.append(row)
    return records


def _git_id(common: str, ref: str) -> str:
    return "git:" + hashlib.sha256(f"{common}\0{ref}".encode()).hexdigest()


def _has_conflicts(status: str) -> bool:
    entries = iter(status.split("\0"))
    for entry in entries:
        code = entry[:2]
        if code in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}:
            return True
        if "R" in code or "C" in code:
            next(entries, None)  # A rename/copy carries a second filename.
    return False


def _local(root: Path, reader: Reader, snapshot: Snapshot) -> None:
    # Resolve the common directory for stable identities across sibling worktrees.
    common = reader.run(
        root, ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
    ).strip()
    raw = reader.run(
        root,
        [
            "git",
            "for-each-ref",
            f"--count={_BRANCHES + 1}",
            "--sort=-committerdate",
            "--format=%(refname)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)",
            "refs/heads/",
        ],
    )
    branches = raw.splitlines()
    by_ref: dict[str, Item] = {}
    for line in branches[:_BRANCHES]:
        ref, head, updated, subject = line.split("\0", 3)
        by_ref[ref] = Item(
            id=_git_id(common, ref),
            kind="branch",
            title=compact(f"{ref.removeprefix('refs/heads/')}: {subject}"),
            updated=updated,
            facts={"branch": compact(ref), "head": head},
        )
    snapshot.sources.append(
        Source("branches", "ok", len(by_ref), len(branches) > _BRANCHES)
    )
    try:
        rows = parse_worktrees(
            reader.run(root, ["git", "worktree", "list", "--porcelain", "-z"])
        )
    except CollectionError as error:
        snapshot.sources.append(Source("worktrees", "unavailable", reason=str(error)))
        snapshot.items.extend(by_ref.values())
        return
    branch_counts = Counter(row.get("branch", "") for row in rows)
    # Inspect the requested worktree first, then a bounded set of siblings.
    rows.sort(
        key=lambda row: (
            Path(row["worktree"]).resolve() != root.resolve(),
            row["worktree"],
        )
    )
    for row in rows[:_WORKTREES]:
        path = row["worktree"]
        ref = row.get("branch", "")
        item = by_ref.pop(ref, None) or Item(
            id=_git_id(common, ref or path),
            kind="worktree",
            title=compact(ref.removeprefix("refs/heads/") or path),
        )
        facts = {
            **item.facts,
            "path": compact(path, 320),
            "head": row.get("HEAD", ""),
            "branch": compact(ref),
        }
        signals = [
            key for key in ("locked", "prunable", "bare", "detached") if key in row
        ]
        if ref and branch_counts[ref] > 1:
            signals.append("shared_branch")
        unknowns = list(item.unknowns)
        try:
            status = reader.run(
                Path(path),
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=no"],
            )
            facts["tracked_changes"] = bool(status)
            if status:
                signals.append("tracked_changes")
            if _has_conflicts(status):
                signals.append("unmerged_changes")
        except CollectionError as error:
            facts["status_error"] = str(error)
            unknowns.append("working_tree_status")
        unknowns.append("untracked_files")
        snapshot.items.append(
            replace(
                item,
                id=_git_id(common, path),
                kind="worktree",
                facts=facts,
                signals=tuple(signals),
                unknowns=tuple(unknowns),
            )
        )
    snapshot.items.extend(by_ref.values())
    snapshot.sources.append(
        Source("worktrees", "ok", min(len(rows), _WORKTREES), len(rows) > _WORKTREES)
    )


class _Named(BaseModel):
    name: str = ""
    login: str = ""


class _Check(BaseModel):
    status: str = ""
    conclusion: str = ""
    state: str = ""


class _Remote(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    number: int = Field(gt=0, le=1_000_000_000)
    title: str
    updated: str = Field(alias="updatedAt", max_length=40)
    assignees: list[_Named] = Field(default_factory=list)
    labels: list[_Named] = Field(default_factory=list)
    head: str = Field(default="", alias="headRefOid", max_length=64)
    branch: str = Field(default="", alias="headRefName")
    draft: bool = Field(default=False, alias="isDraft")
    review: str | None = Field(default=None, alias="reviewDecision", max_length=64)
    merge: str | None = Field(default=None, alias="mergeable", max_length=64)
    checks: list[_Check] | None = Field(default=None, alias="statusCheckRollup")


def remote_items(text: str, repo: str, kind: str) -> list[Item]:
    """Normalize a bounded GitHub response; never infer local/fork branch identity."""
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("expected a GitHub listing")
    items: dict[str, Item] = {}
    for value in rows[: _REMOTE_ITEMS + 1]:
        row = _Remote.model_validate(value)
        signals: list[str] = []
        facts: dict[str, object] = {
            "repo": repo,
            "number": row.number,
            "owners": [compact(owner.login, 64) for owner in row.assignees[:4]],
            "labels": [compact(label.name, 64) for label in row.labels[:4]],
            "metadata_truncated": len(row.assignees) > 4 or len(row.labels) > 4,
        }
        if len(row.assignees) > 1:
            signals.append("multiple_assignees")
        if any(label.name.casefold() == "blocked" for label in row.labels):
            signals.append("labelled_blocked")
        if kind == "pr":
            facts.update(
                head=row.head,
                branch=compact(row.branch),
                draft=row.draft,
                review=row.review,
                mergeable=row.merge,
            )
            if row.draft:
                signals.append("draft")
            if row.merge == "CONFLICTING":
                signals.append("merge_conflict")
            if row.review == "CHANGES_REQUESTED":
                signals.append("changes_requested")
            failed = any(
                check.conclusion
                in {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
                or check.state in {"FAILURE", "ERROR"}
                for check in row.checks or []
            )
            pending = any(
                check.status
                in {"QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED"}
                or check.state in {"PENDING", "EXPECTED"}
                for check in row.checks or []
            )
            facts["ci"] = (
                "failed"
                if failed
                else "pending"
                if pending
                else "reported"
                if row.checks
                else "unknown"
            )
            if failed:
                signals.append("ci_failed")
        identity = f"github:{repo}:{kind}:{row.number}"
        items[identity] = Item(
            identity, kind, compact(row.title), row.updated, facts, tuple(signals)
        )
    return list(items.values())


def collect(root: Path, repo: str | None = None) -> Snapshot:
    """Gather bounded local state and optional github.com issues and PRs."""
    validate_repo(repo)
    snapshot = Snapshot()
    reader = Reader(snapshot)
    try:
        _local(root, reader, snapshot)
    except (CollectionError, ValueError) as error:
        snapshot.sources.append(
            Source(
                "git",
                "unavailable",
                reason=str(error)
                if isinstance(error, CollectionError)
                else "invalid_response",
            )
        )
    for kind in ("issue", "pr"):
        name = f"github_{kind}"
        if repo is None:
            snapshot.sources.append(Source(name, "not_requested"))
            continue
        fields = "number,title,updatedAt,assignees,labels"
        if kind == "pr":
            fields += (
                ",headRefOid,headRefName,isDraft,reviewDecision,mergeable,"
                "statusCheckRollup"
            )
        try:
            raw = reader.run(
                root,
                [
                    "gh",
                    kind,
                    "list",
                    "--repo",
                    f"github.com/{repo}",
                    "--state",
                    "open",
                    "--limit",
                    str(_REMOTE_ITEMS + 1),
                    "--json",
                    fields,
                ],
            )
            items = remote_items(raw, repo, kind)
            snapshot.items.extend(items[:_REMOTE_ITEMS])
            snapshot.sources.append(
                Source(
                    name,
                    "ok",
                    min(len(items), _REMOTE_ITEMS),
                    len(items) > _REMOTE_ITEMS,
                )
            )
        except (CollectionError, ValueError, ValidationError) as error:
            reason = (
                str(error) if isinstance(error, CollectionError) else "invalid_response"
            )
            snapshot.sources.append(Source(name, "unavailable", reason=reason))
    return snapshot
