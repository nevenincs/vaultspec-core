"""Project collection uses real Git; hosted ranking uses the real HTTP transport."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.core.enums import TypeSafeModel
from vaultspec_core.project.collect import (
    CollectionError,
    Reader,
    collect,
    parse_worktrees,
    remote_items,
    validate_repo,
)
from vaultspec_core.project.models import SCHEMA, Item, Snapshot, compact
from vaultspec_core.project.ranking import (
    Ranking,
    fingerprint,
    load_previous,
    ordered,
    rank,
    shortlist,
)
from vaultspec_core.search._transport import JevClient
from vaultspec_core.search.tests.scripted_provider import (
    Received,
    Reply,
    ScriptedProvider,
)

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

pytestmark = pytest.mark.integration


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--initial-branch=trunk")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Context test")
    (root / "tracked.txt").write_text("base", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(
        root,
        "-c",
        "core.hooksPath=",
        "commit",
        "--no-gpg-sign",
        "-m",
        "Seed release work",
    )
    return root


def _cli(root: Path, *args: str) -> Result:
    return CliRunner().invoke(
        app,
        ["project", "context", *args, "--target", str(root), "--json"],
        env={"VAULTSPEC_CORE_TYPESAFE_API_KEY": ""},
    )


def test_local_worktrees_are_deduplicated_and_no_key_needs_no_workspace(
    repository: Path,
) -> None:
    sibling = repository.parent / "feature with spaces"
    _git(repository, "worktree", "add", "-b", "feature", str(sibling))
    (sibling / "tracked.txt").write_text("changed", encoding="utf-8")
    before = _git(repository, "status", "--porcelain")
    result = _cli(repository, "release")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["observed_items"] == 2
    assert data["items"][0]["facts"]["branch"] == "refs/heads/feature"
    assert data["items"][0]["signals"] == ["tracked_changes"]
    assert len({item["id"] for item in data["items"]}) == 2
    assert data["hosted"]["status"] == "not_configured"
    assert data["hosted"]["requests"] == 0
    assert data["sources"][-1]["status"] == "not_requested"
    assert _git(repository, "status", "--porcelain") == before
    assert not (repository / ".vaultspec").exists()
    # A sibling invocation resolves the same common Git identity.
    assert {item.id for item in collect(sibling).items} == {
        item["id"] for item in data["items"]
    }


def test_branch_and_result_windows_report_incomplete_coverage(repository: Path) -> None:
    for number in range(33):
        _git(repository, "branch", f"work-{number:02}")
    result = _cli(repository, "release", "--limit", "2", "--no-hosted")
    data = json.loads(result.output)["data"]
    assert len(data["items"]) == 2
    assert data["truncated"] is True
    assert data["shortlisted"] == 12
    assert data["sources"][0]["truncated"] is True
    assert data["hosted"]["status"] == "disabled"


def test_worktrees_sharing_a_branch_retain_both_identities(repository: Path) -> None:
    sibling = repository.parent / "shared"
    _git(repository, "worktree", "add", "--force", str(sibling), "trunk")
    items = collect(repository).items
    assert len(items) == 2
    assert len({item.id for item in items}) == 2
    assert all("shared_branch" in item.signals for item in items)


def test_unresolved_local_merge_is_an_attention_blocker(repository: Path) -> None:
    _git(repository, "switch", "-c", "feature")
    (repository / "tracked.txt").write_text("feature", encoding="utf-8")
    _git(
        repository, "-c", "core.hooksPath=", "commit", "--no-gpg-sign", "-am", "feature"
    )
    _git(repository, "switch", "trunk")
    (repository / "tracked.txt").write_text("trunk", encoding="utf-8")
    _git(repository, "-c", "core.hooksPath=", "commit", "--no-gpg-sign", "-am", "trunk")
    merge = subprocess.run(
        ["git", "-C", str(repository), "merge", "feature"],
        capture_output=True,
        check=False,
    )
    assert merge.returncode == 1
    data = json.loads(_cli(repository, "release").output)["data"]
    assert "unmerged_changes" in data["items"][0]["signals"]
    assert data["items"][0]["attention_band"] == 0


def test_non_repository_is_unknown_not_an_empty_successful_inventory(
    tmp_path: Path,
) -> None:
    data = json.loads(_cli(tmp_path, "release").output)["data"]
    assert data["items"] == []
    assert data["sources"][0]["status"] == "unavailable"


def test_explicit_disable_overrides_a_configured_key(repository: Path) -> None:
    arguments = ["project", "context", "release", "--target", str(repository)]
    environment = {"VAULTSPEC_CORE_TYPESAFE_API_KEY": "invalid\nheader"}
    disabled = CliRunner().invoke(
        app, [*arguments, "--no-hosted", "--json"], env=environment
    )
    assert disabled.exit_code == 0, disabled.output
    assert json.loads(disabled.output)["data"]["hosted"]["status"] == "disabled"
    rejected = CliRunner().invoke(app, [*arguments, "--json"], env=environment)
    assert rejected.exit_code == 0, rejected.output
    data = json.loads(rejected.output)["data"]
    assert data["hosted"]["status"] == "unavailable"
    assert data["returned"] == 1
    assert "invalid" not in rejected.output
    human = CliRunner().invoke(app, [*arguments, "--no-hosted"], env=environment)
    assert human.exit_code == 0, human.output
    assert "Project attention" in human.output
    assert "Uncollected" in human.output


@pytest.mark.parametrize(
    "args", [(" ",), ("release", "--repo", "--evil"), ("release", "--limit", "11")]
)
def test_invalid_cli_input_is_rejected_before_collection(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    assert _cli(tmp_path, *args).exit_code == 2


def test_remote_observations_preserve_blockers_and_nullable_review() -> None:
    response = json.dumps(
        [
            {
                "number": 1,
                "title": "release",
                "updatedAt": "2026-09-25T00:00:00Z",
                "reviewDecision": None,
                "mergeable": "CONFLICTING",
                "headRefName": "feature",
                "statusCheckRollup": [{"conclusion": "FAILURE"}],
                "assignees": [{"login": "a"}, {"login": "b"}],
            },
            {
                "number": 2,
                "title": "fork release",
                "updatedAt": "2026-09-25T00:00:00Z",
                "headRefName": "feature",
                "statusCheckRollup": [{"state": "PENDING"}],
            },
        ]
    )
    items = remote_items(response, "owner/repo", "pr")
    assert len(items) == 2  # Same branch name is not a reliable relationship.
    assert set(items[0].signals) == {
        "multiple_assignees",
        "merge_conflict",
        "ci_failed",
    }
    assert items[1].facts["ci"] == "pending"
    assert "dependencies" in items[0].unknowns


def test_remote_duplicate_identity_is_not_a_second_task() -> None:
    row = {
        "number": 1,
        "title": "release",
        "updatedAt": "2026-09-25T00:00:00Z",
        "labels": [{"name": "blocked"}],
    }
    items = remote_items(json.dumps([row, row]), "owner/repo", "issue")
    assert len(items) == 1
    assert "labelled_blocked" in items[0].signals
    with pytest.raises(ValueError):
        remote_items("{}", "owner/repo", "issue")
    with pytest.raises(ValueError):
        validate_repo("https://user:secret@example.org/repo")


def test_nul_paths_and_unicode_bounds() -> None:
    rows = parse_worktrees("worktree /with\nnewline\0HEAD abc\0detached\0\0")
    assert rows == [{"worktree": "/with\nnewline", "HEAD": "abc", "detached": ""}]
    assert len(compact("界" * 500).encode()) <= 240
    assert "\x1b" not in compact("bad\x1b[31m")


def test_collection_bounds_use_real_processes(tmp_path: Path) -> None:
    reader = Reader(Snapshot())
    with pytest.raises(CollectionError, match="output_limit"):
        reader.run(tmp_path, [sys.executable, "-c", "print('x' * 1000001)"])
    reader.deadline = time.monotonic() - 1
    with pytest.raises(CollectionError, match="collection_deadline"):
        reader.run(
            tmp_path, [sys.executable, "-c", "raise RuntimeError('must not run')"]
        )


def _scores(request: Received) -> Reply:
    payload = request.payload()
    answers = {
        key: {
            "type": "score",
            "score": 3.0,
            "confidence": 1.0,
            "probabilities": {"3": 1.0},
        }
        for key in payload["questions"]
    }
    return Reply.json(
        {
            "model": TypeSafeModel.JEV,
            "answers": answers,
            "usage": {"input_tokens": 120, "output_tokens": 12},
        }
    )


def test_hosted_batch_reuses_unchanged_items_and_invalidates_changed_facts() -> None:
    items = [Item("one", "issue", "release"), Item("two", "pr", "packaging")]
    with (
        ScriptedProvider(responder=_scores) as provider,
        JevClient("test", endpoint=provider.endpoint, max_attempts=1) as client,
    ):
        first = rank("release", items, client, {})
        assert first.status == "available"
        assert first.requests == 1
        assert first.input_tokens == 120
        assert len(provider.received[0].payload()["questions"]) == 2
        assert provider.received[0].payload()["model"] == TypeSafeModel.JEV
        second = rank("release", items, client, first.judgments)
        assert second.requests == 0
        assert second.cache_hits == 2
        changed = [replace(items[0], facts={"head": "different"}), items[1]]
        third = rank("release", changed, client, second.judgments)
        assert third.requests == 1
        assert third.cache_hits == 1
        assert len(provider.received[-1].payload()["questions"]) == 1
        assert len(provider.received) == 2
    assert fingerprint("other objective", items[0]) != fingerprint("release", items[0])


def test_failed_hosted_request_does_not_mix_cached_scores_into_fallback() -> None:
    items = [Item("one", "pr", "release"), Item("two", "issue", "unrelated")]
    previous = {
        fingerprint("release", items[1]): {
            "score": 3,
            "confidence": 1,
            "at": time.time(),
            "model": TypeSafeModel.JEV,
        }
    }
    with (
        ScriptedProvider(Reply.json({}, 503)) as provider,
        JevClient("test", endpoint=provider.endpoint, max_attempts=1) as client,
    ):
        result = rank("release", items, client, previous)
    assert result.status == "unavailable"
    assert result.scores == {}
    assert len(provider.received) == 1
    assert ordered("release", items, result)[0].id == "one"


@pytest.mark.parametrize(
    "changes",
    [
        {"at": 1},
        {"at": time.time() + 86400},
        {"score": float("nan")},
        {"score": 4},
        {"score": True},
        {"confidence": -1},
    ],
)
def test_stale_or_invalid_cached_judgment_is_evaluated_again(
    changes: dict[str, object],
) -> None:
    item = Item("one", "issue", "release")
    saved = {
        "score": 3,
        "confidence": 1,
        "at": time.time(),
        "model": TypeSafeModel.JEV,
        **changes,
    }
    with (
        ScriptedProvider(responder=_scores) as provider,
        JevClient("test", endpoint=provider.endpoint) as client,
    ):
        result = rank("release", [item], client, {fingerprint("release", item): saved})
    assert result.cache_hits == 0
    assert result.requests == 1


def test_model_preference_cannot_move_observed_blockers_below_other_work() -> None:
    blocked = Item("blocked", "pr", "ci", signals=("ci_failed",))
    preferred = Item("preferred", "issue", "release")
    items = shortlist("release", [preferred, preferred, blocked])
    result = Ranking("available", scores={"blocked": 0, "preferred": 3})
    assert ordered("release", items, result) == [blocked, preferred]


def test_previous_reads_only_judgments_and_bounds_input(tmp_path: Path) -> None:
    path = tmp_path / "previous.json"
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "data": {"items": ["stale"], "judgments": {"key": "value"}},
            }
        ),
        encoding="utf-8",
    )
    assert load_previous(path) == {"key": "value"}
    path.write_text(" " * 64_001, encoding="utf-8")
    with pytest.raises(ValueError, match="64000"):
        load_previous(path)
