"""Exercise the cut's merge of a release pull request without cutting a release."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from dev.environment import child_environment

pytestmark = [pytest.mark.repo]

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "nevenincs/vaultspec-core"
HEAD = "a" * 40
SQUASH = "b" * 40
OPEN = {"state": "OPEN", "headRefOid": HEAD, "mergeStateStatus": "BLOCKED"}
MERGED = OPEN | {"state": "MERGED", "mergeCommit": {"oid": SQUASH}}

# Mock transport only. The workflow's Bash and jq filters run unchanged against
# API response bodies. The pull request is a file, so a merge - this step's or
# somebody else's - changes what the next read returns, as it does on GitHub.
TRANSPORT = r"""
sleep() { :; }
gh() {
  printf '%s\n' "$*" >> "$MOCK_CALLS"
  local filter=''
  case "$1 $2" in
    'pr view')
      filter="${*: -1}"
      jq -r "$filter" "$MOCK_PR"
      ;;
    'pr merge')
      case "$MOCK_MERGE" in
        ok) cp "$MOCK_PR_MERGED" "$MOCK_PR" ;;
        raced) cp "$MOCK_PR_MERGED" "$MOCK_PR"; return 1 ;;
        *) return 1 ;;
      esac
      ;;
    'api --method') [ "$3" = POST ] || return 99 ;;
    api\ *)
      filter="${*: -1}"
      case "$2" in
        */compare/main...*) printf '%s' "$MOCK_COMPARE" | jq -r "$filter" ;;
        */commits/*)
          printf '%s' "$MOCK_TREES" |
            jq --arg sha "${2##*/}" '{commit: {tree: {sha: .[$sha]}}}' |
            jq -r "$filter"
          ;;
        */runs\?*) printf '%s' "$MOCK_HELD" | jq -r "$filter" ;;
        *) return 99 ;;
      esac
      ;;
    *) return 99 ;;
  esac
}
"""


def _step(name: str) -> str:
    workflow: dict[str, Any] = yaml.safe_load(
        (ROOT / ".github/workflows/release-please.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["cut"]["steps"]
    return next(step["run"] for step in steps if step.get("name") == name)


def _run(
    tmp_path: Path,
    step: str,
    pull_request: dict[str, Any],
    **changes: str,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.is_file() else shutil.which("bash")
    assert bash is not None, "Bash is required to exercise the release cut"
    assert shutil.which("jq") is not None, "jq is required for the API fixture"
    state = tmp_path / "pull-request.json"
    state.write_text(json.dumps(pull_request), encoding="utf-8")
    merged = tmp_path / "merged.json"
    merged.write_text(json.dumps(MERGED), encoding="utf-8")
    calls = tmp_path / "calls"
    calls.write_text("", encoding="utf-8")
    env = child_environment(
        {
            "NUMBER": "42",
            "SHA": HEAD,
            "MERGED": "false",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_OUTPUT": (tmp_path / "outputs").as_posix(),
            "MOCK_PR": state.as_posix(),
            "MOCK_PR_MERGED": merged.as_posix(),
            "MOCK_CALLS": calls.as_posix(),
            "MOCK_MERGE": "ok",
            "MOCK_COMPARE": json.dumps({"behind_by": 0}),
            "MOCK_TREES": json.dumps({HEAD: "tree", SQUASH: "tree"}),
            "MOCK_HELD": json.dumps({"workflow_runs": [{"id": 7}]}),
        }
    )
    env.update(changes)
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", TRANSPORT + _step(step)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result, calls.read_text(encoding="utf-8").splitlines()


MERGE = "Merge the proven release pull request"
RELEASE = "Release the held merge gate of the release pull request"


def _merges(calls: list[str]) -> int:
    return sum(call.startswith("pr merge") for call in calls)


def test_the_cut_merges_the_head_it_proved(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, MERGE, OPEN)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs").read_text().splitlines() == [f"commit={SQUASH}"]
    assert _merges(calls) == 1
    assert f"--match-head-commit {HEAD}" in next(c for c in calls if "pr merge" in c)


@pytest.mark.parametrize("merge", ["never-called", "raced"])
def test_a_merge_that_auto_merge_won_is_tagged_not_refused(
    tmp_path: Path, merge: str
) -> None:
    """Refusing it leaves a release commit on main with no tag."""
    before = MERGED if merge == "never-called" else OPEN
    result, calls = _run(tmp_path, MERGE, before, MOCK_MERGE=merge)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs").read_text().splitlines() == [f"commit={SQUASH}"]
    assert _merges(calls) == (0 if merge == "never-called" else 1)


@pytest.mark.parametrize(
    ("pull_request", "changes"),
    [
        (OPEN, {"MOCK_MERGE": "refused"}),
        (OPEN, {"MOCK_COMPARE": json.dumps({"behind_by": 1})}),
        (OPEN | {"headRefOid": "c" * 40}, {}),
        (MERGED | {"headRefOid": "c" * 40}, {}),
        (OPEN | {"state": "CLOSED"}, {}),
        (OPEN, {"MOCK_TREES": json.dumps({HEAD: "tree", SQUASH: "other"})}),
        (MERGED, {"MOCK_TREES": json.dumps({HEAD: "tree", SQUASH: "other"})}),
    ],
    ids=[
        "merge-refused",
        "behind-main",
        "open-at-another-head",
        "merged-at-another-head",
        "closed",
        "tree-differs",
        "auto-merged-tree-differs",
    ],
)
def test_anything_but_the_proven_tree_is_refused(
    tmp_path: Path, pull_request: dict[str, Any], changes: dict[str, str]
) -> None:
    result, _calls = _run(tmp_path, MERGE, pull_request, **changes)
    assert result.returncode != 0, result.stdout
    assert not (tmp_path / "outputs").exists()


def test_a_pull_request_behind_main_is_never_merged(tmp_path: Path) -> None:
    _result, calls = _run(
        tmp_path, MERGE, OPEN, MOCK_COMPARE=json.dumps({"behind_by": 1})
    )
    assert _merges(calls) == 0


def test_a_proposal_merged_before_the_cut_is_taken_as_found(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, MERGE, MERGED, MERGED="true")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs").read_text().splitlines() == [f"commit={HEAD}"]
    assert calls == []


@pytest.mark.parametrize("state", ["CLEAN", "UNSTABLE", "HAS_HOOKS"])
def test_the_held_gate_is_released_and_the_pull_request_waited_for(
    tmp_path: Path, state: str
) -> None:
    result, calls = _run(tmp_path, RELEASE, OPEN | {"mergeStateStatus": state})
    assert result.returncode == 0, result.stderr
    approvals = [call for call in calls if "/approve" in call]
    assert approvals == [
        f"api --method POST repos/{REPOSITORY}/actions/runs/7/approve --silent"
    ]
    held = next(call for call in calls if "/runs?" in call)
    assert f"head_sha={HEAD}" in held
    assert "status=action_required" in held


def test_a_pull_request_merged_on_release_ends_the_wait(tmp_path: Path) -> None:
    result, _calls = _run(tmp_path, RELEASE, MERGED)
    assert result.returncode == 0, result.stderr


def test_a_pull_request_that_stays_blocked_stops_the_cut(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, RELEASE, OPEN)
    assert result.returncode != 0, result.stdout
    assert "::error::" in result.stdout
    assert _merges(calls) == 0


def test_nothing_is_released_for_a_proposal_merged_before_the_cut(
    tmp_path: Path,
) -> None:
    result, calls = _run(tmp_path, RELEASE, MERGED, MERGED="true")
    assert result.returncode == 0, result.stderr
    assert calls == []
