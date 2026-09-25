"""Review selection against real Git scopes and the real HTTP transport."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.core.enums import TypeSafeModel
from vaultspec_core.review.collect import collect
from vaultspec_core.review.ranking import SCHEMA, load_previous, rank
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
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--initial-branch=trunk")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Review test")
    _git(root, "config", "core.autocrlf", "false")
    (root / "caller.py").write_text(
        "from service import value\nassert value == 1\n", encoding="utf-8", newline="\n"
    )
    (root / "service.py").write_bytes(b"value = 1\n")
    (root / "large.py").write_text("# supporting line\n" * 150, encoding="utf-8")
    (root / ".env").write_text("PRIVATE_TEST_SENTINEL=never-submit\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "core.hooksPath=", "commit", "--no-gpg-sign", "-m", "Seed")
    (root / "service.py").write_bytes(b"value = 2\n")
    return root


def _cli(root: Path, *args: str, key: str = "") -> Result:
    return CliRunner().invoke(
        app,
        [
            "review",
            "context",
            "caller contract",
            "--base",
            "HEAD",
            "--candidate",
            "caller.py",
            "--target",
            str(root),
            "--json",
            *args,
        ],
        env={"VAULTSPEC_CORE_TYPESAFE_API_KEY": key},
    )


def test_keyless_cli_is_read_only_and_preserves_discovery_order(
    repository: Path,
) -> None:
    before = _git(repository, "status", "--porcelain")
    result = _cli(repository, "--candidate", "service.py", "--limit", "1")
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["schema"] == SCHEMA
    data = envelope["data"]
    assert data["hosted"]["status"] == "not_configured"
    assert data["hosted"]["requests"] == 0
    assert data["ordering"] == "discovery_order"
    assert data["selected"][0]["locator"] == "caller.py:1-2"
    assert data["selected"][0]["content"].startswith("from service import value")
    assert data["unselected"][0]["locator"] == "service.py:1-1"
    assert _git(repository, "status", "--porcelain") == before
    assert not (repository / ".vaultspec").exists()


def test_explicit_head_reads_committed_evidence_and_worktree_includes_index(
    repository: Path,
) -> None:
    base = _git(repository, "rev-parse", "HEAD")
    _git(
        repository, "-c", "core.hooksPath=", "commit", "--no-gpg-sign", "-am", "Change"
    )
    (repository / "caller.py").write_bytes(b"staged caller\n")
    _git(repository, "add", "caller.py")
    (repository / "service.py").write_text("dirty service\n", encoding="utf-8")
    historical = collect(repository, base, "HEAD", ["caller.py", "service.py"])
    assert "assert value == 1" in historical.snippets[0].content
    assert historical.snippets[1].content == "value = 2\n"
    assert "dirty" not in historical.diff and "staged" not in historical.diff
    working = collect(repository, "HEAD", None, ["caller.py", "service.py"])
    assert "staged caller" in working.diff and "dirty service" in working.diff
    assert working.snippets[0].content == "staged caller\n"
    assert working.head is None


def test_private_untracked_binary_and_out_of_bounds_candidates_are_explicit(
    repository: Path,
) -> None:
    (repository / "untracked.py").write_text("untracked", encoding="utf-8")
    (repository / "binary.dat").write_bytes(b"a\x00b")
    _git(repository, "add", "binary.dat")
    snapshot = collect(
        repository,
        "HEAD",
        None,
        [
            ".env",
            "../outside",
            "C:/outside",
            "untracked.py",
            "binary.dat",
            "large.py",
            "large.py:10-12",
            "caller.py:10-12",
            "large.py:10-12",
        ],
    )
    assert len(snapshot.snippets) == 1
    assert snapshot.snippets[0].locator == "large.py:10-12"
    assert [item["reason"] for item in snapshot.excluded] == [
        "private_path",
        "invalid_locator",
        "invalid_locator",
        "not_one_tracked_file",
        "binary_file",
        "narrower_range_required",
        "line_range_unavailable",
        "duplicate_locator",
    ]
    assert "never-submit" not in snapshot.diff


def test_symlink_blob_is_not_read_as_regular_source(repository: Path) -> None:
    # An index symlink exercises this on Windows without requiring symlink privileges.
    oid = _git(repository, "hash-object", "caller.py")
    _git(repository, "update-index", "--add", "--cacheinfo", f"120000,{oid},link")
    result = collect(repository, "HEAD", None, ["link"])
    assert result.excluded == [{"candidate": "c0", "reason": "not_regular_file"}]


def test_private_changed_path_disables_hosted_before_reading_diff(
    repository: Path,
) -> None:
    (repository / ".env").write_text(
        "PRIVATE_TEST_SENTINEL=changed\n", encoding="utf-8"
    )
    result = _cli(repository, key="invalid\nheader")
    data = json.loads(result.output)["data"]
    assert data["scope"]["diff_reason"] == "private_changed_path"
    assert data["hosted"]["requests"] == 0
    assert data["selected"]
    assert "PRIVATE_TEST_SENTINEL" not in result.output


def test_large_diff_preserves_candidates_without_partial_hosted_judgment(
    repository: Path,
) -> None:
    (repository / "service.py").write_text("# content\n" * 4000, encoding="utf-8")
    data = json.loads(_cli(repository, key="invalid\nheader").output)["data"]
    assert data["scope"]["diff_reason"] == "byte_limit"
    assert data["hosted"]["requests"] == 0
    assert data["selected"][0]["locator"] == "caller.py:1-2"


def test_disable_and_rejected_credential_continue_locally_without_secret_echo(
    repository: Path,
) -> None:
    key = "credential-sentinel\ninvalid-header"
    disabled = _cli(repository, "--no-hosted", key=key)
    assert json.loads(disabled.output)["data"]["hosted"]["status"] == "disabled"
    rejected = _cli(repository, key=key)
    assert rejected.exit_code == 0
    data = json.loads(rejected.output)["data"]
    assert data["hosted"]["reason"] == "credential_rejected"
    assert data["ordering"] == "discovery_order"
    assert "credential-sentinel" not in rejected.output


def test_enrolled_credential_in_source_is_neither_returned_nor_submitted(
    repository: Path,
) -> None:
    key = "private-credential-sentinel"
    (repository / "caller.py").write_text(key, encoding="utf-8")
    result = _cli(repository, key=key)
    data = json.loads(result.output)["data"]
    assert key not in result.output
    assert data["hosted"]["requests"] == 0
    assert data["selected"] == []
    assert data["scope"]["diff_reason"] == "credential_in_diff"


def _scores(request: Received) -> Reply:
    payload = request.payload()
    return Reply.json(
        {
            "model": TypeSafeModel.JEV,
            "answers": {
                key: {
                    "type": "score",
                    "score": number,
                    "confidence": 1,
                    "probabilities": {str(number): 1},
                }
                for number, key in enumerate(payload["questions"])
            },
            "usage": {"input_tokens": 120, "output_tokens": 12},
        }
    )


def test_one_score_batch_reuses_exact_inputs_and_invalidates_changed_evidence(
    repository: Path,
) -> None:
    snapshot = collect(repository, "HEAD", None, ["service.py", "caller.py"])
    with (
        ScriptedProvider(responder=_scores) as provider,
        JevClient("test", endpoint=provider.endpoint, max_attempts=1) as client,
    ):
        first = rank("caller contract", snapshot, client, {})
        assert first.status == "available"
        assert first.scores["c1"] > first.scores["c0"]
        assert first.input_tokens == 120 and first.output_tokens == 12
        sent = provider.received[0].payload()
        assert sent["model"] == TypeSafeModel.JEV
        assert len(sent["questions"]) == 2
        assert "PRIVATE_TEST_SENTINEL" not in json.dumps(sent)
        reused = rank("caller contract", snapshot, client, first.judgment)
        assert reused.status == "reused" and reused.requests == 0
        assert reused.judgment == first.judgment
        changed = replace(snapshot, diff=snapshot.diff + "\nchanged")
        assert rank("caller contract", changed, client, first.judgment).requests == 1
        changed = replace(
            snapshot,
            snippets=[
                replace(snapshot.snippets[0], content="changed"),
                snapshot.snippets[1],
            ],
        )
        assert rank("caller contract", changed, client, first.judgment).requests == 1
        assert rank("other review", snapshot, client, first.judgment).requests == 1
        assert len(provider.received) == 4


@pytest.mark.parametrize("status", [401, 429, 503, 200])
def test_provider_failures_discard_all_scores_and_make_one_attempt(
    repository: Path, status: int
) -> None:
    snapshot = collect(repository, "HEAD", None, ["caller.py", "service.py"])
    with (
        ScriptedProvider(
            Reply.json({"provider_secret": "never-echo"}, status)
        ) as provider,
        JevClient("test", endpoint=provider.endpoint, max_attempts=1) as client,
    ):
        result = rank("contract", snapshot, client, {})
    assert result.status == "unavailable"
    assert result.scores == {} and result.judgment == {}
    assert len(provider.received) == 1
    assert "never-echo" not in str(result)


def test_timeout_does_not_retry_or_block_local_fallback(repository: Path) -> None:
    snapshot = collect(repository, "HEAD", None, ["caller.py"])
    with (
        ScriptedProvider(Reply.json({}, delay=0.2)) as provider,
        JevClient(
            "test", endpoint=provider.endpoint, timeout=0.01, max_attempts=1
        ) as client,
    ):
        result = rank("contract", snapshot, client, {})
    assert result.status == "unavailable" and result.scores == {}
    assert len(provider.received) == 1


@pytest.mark.parametrize(
    "change", [{"at": 1}, {"at": time.time() + 86400}, {"scores": {"c0": float("nan")}}]
)
def test_expired_or_invalid_judgment_is_not_reused(
    repository: Path, change: dict[str, object]
) -> None:
    snapshot = collect(repository, "HEAD", None, ["caller.py"])
    with (
        ScriptedProvider(responder=_scores) as provider,
        JevClient("test", endpoint=provider.endpoint, max_attempts=1) as client,
    ):
        first = rank("contract", snapshot, client, {})
        result = rank("contract", snapshot, client, {**first.judgment, **change})
    assert result.status == "available" and result.requests == 1
    assert len(provider.received) == 2


def test_previous_envelope_is_bounded_and_cannot_enable_hosted_when_keyless(
    repository: Path,
) -> None:
    previous = repository / "previous.json"
    previous.write_text(
        json.dumps({"schema": SCHEMA, "data": {"judgment": {"marker": "ignored"}}}),
        encoding="utf-8",
    )
    assert load_previous(previous) == {"marker": "ignored"}
    data = json.loads(_cli(repository, "--previous", str(previous)).output)["data"]
    assert data["hosted"]["status"] == "not_configured"
    assert data["judgment"] == {}
    previous.write_bytes(b" " * 128_001)
    with pytest.raises(ValueError, match="128000"):
        load_previous(previous)


@pytest.mark.parametrize(
    "args", [("--base", "--bad"), ("--limit", "7"), ("--candidate", "caller.py:0")]
)
def test_invalid_input_is_rejected_or_excluded(
    repository: Path, args: tuple[str, ...]
) -> None:
    result = _cli(repository, *args)
    if "caller.py:0" in args:
        assert (
            json.loads(result.output)["data"]["excluded"][0]["reason"]
            == "invalid_locator"
        )
    else:
        assert result.exit_code == 2
