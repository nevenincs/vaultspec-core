"""Exercise the proposal's failure reporting without creating a release."""

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

# Only the GitHub transport is replaced; the workflow's Bash and jq run as shipped.
TRANSPORT = r"""
gh() {
  [ "$1 $2" = 'pr list' ] || return 99
  [ "$3 $4" = '--repo nevenincs/vaultspec-core' ] || return 99
  [ "$5 $6" = '--base main' ] || return 99
  [ "$7 $8" = '--state merged' ] || return 99
  [ "$9 ${10}" = '--label autorelease: pending' ] || return 99
  [ "${11} ${12}" = '--limit 100' ] || return 99
  [ "${13} ${14}" = '--json number' ] || return 99
  [ "${15}" = '--jq' ] || return 99
  [ "$MOCK_FAIL" != true ] || return 1
  printf '%s' "$MOCK_PROPOSALS" | jq -r "${16}"
}
"""


def _job(name: str = "release-please") -> dict[str, Any]:
    workflow: dict[str, Any] = yaml.safe_load(
        (ROOT / ".github/workflows/release-please.yml").read_text(encoding="utf-8")
    )
    return workflow["jobs"][name]


def _run(
    tmp_path: Path, numbers: list[int], *, api_failure: bool = False
) -> subprocess.CompletedProcess[str]:
    step = next(
        step
        for step in _job()["steps"]
        if step.get("name") == "Reject a blocked release proposal"
    )
    return _run_script(
        tmp_path,
        TRANSPORT + step["run"],
        {
            "GITHUB_REPOSITORY": "nevenincs/vaultspec-core",
            "MOCK_PROPOSALS": json.dumps([{"number": n} for n in numbers]),
            "MOCK_FAIL": str(api_failure).lower(),
        },
    )


def _run_script(
    tmp_path: Path, script: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.is_file() else shutil.which("bash")
    assert bash is not None, "Bash is required to exercise the release workflow"
    assert shutil.which("jq") is not None, "jq is required for the API fixture"
    return subprocess.run(
        [bash, "--noprofile", "--norc", "-c", script],
        env=child_environment(env),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize("numbers", [[600], [600, 601]])
def test_pending_merged_releases_fail_the_proposal(
    tmp_path: Path, numbers: list[int]
) -> None:
    result = _run(tmp_path, numbers)
    assert result.returncode == 1, result.stderr
    assert "::error::Release Please is blocked" in result.stdout
    assert ", ".join(str(n) for n in numbers) in result.stdout
    assert "Dispatch Core Release Please" in result.stdout


def test_no_releasable_changes_can_succeed(tmp_path: Path) -> None:
    result = _run(tmp_path, [])
    assert result.returncode == 0, result.stderr
    assert "::error::" not in result.stdout


def test_failed_pending_lookup_fails_the_proposal(tmp_path: Path) -> None:
    result = _run(tmp_path, [], api_failure=True)
    assert result.returncode != 0


def test_blocked_proposal_check_precedes_conditional_followup_steps() -> None:
    job = _job()
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    guard = names.index("Reject a blocked release proposal")
    assert names.index("Run release-please") < guard
    assert guard < names.index("Check out the release branch")
    assert steps[guard]["if"] == "${{ !steps.release.outputs.pr }}"
    assert steps[guard]["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
    assert not job.get("continue-on-error")
    assert not steps[guard].get("continue-on-error")


CANDIDATE_TRANSPORT = r"""
gh() {
  [ "$1 $2" = 'pr list' ] || return 99
  [ "$MOCK_FAIL" != true ] || return 1
  local body=''
  case "$*" in
    *'--state merged'*) body="$MOCK_MERGED" ;;
    *'--state open'*) body="$MOCK_OPEN" ;;
    *) return 99 ;;
  esac
  printf '%s' "$body" | jq -r "${*: -1}"
}
"""


def _candidate(
    tmp_path: Path, merged: list[dict[str, Any]], **changes: str
) -> subprocess.CompletedProcess[str]:
    env = {
        "GITHUB_REPOSITORY": "nevenincs/vaultspec-core",
        "GITHUB_OUTPUT": (tmp_path / "outputs").as_posix(),
        "EVENT_NAME": "push",
        "PENDING": "autorelease: pending",
        "MOCK_MERGED": json.dumps(merged),
        "MOCK_OPEN": "[]",
        "MOCK_FAIL": "false",
    }
    return _run_script(
        tmp_path,
        CANDIDATE_TRANSPORT + _job("candidate")["steps"][0]["run"],
        env | changes,
    )


def test_merging_a_proposal_selects_its_commit_for_automatic_release(
    tmp_path: Path,
) -> None:
    sha = "a" * 40
    result = _candidate(tmp_path, [{"number": 600, "mergeCommit": {"oid": sha}}])
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs").read_text().splitlines() == [
        "number=600",
        f"sha={sha}",
        "merged=true",
    ]


def test_ordinary_push_refreshes_without_cutting_an_open_proposal(
    tmp_path: Path,
) -> None:
    result = _candidate(
        tmp_path,
        [],
        MOCK_OPEN=json.dumps([{"number": 600, "headRefOid": "a" * 40}]),
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize(
    "changes",
    [{"EVENT_NAME": "workflow_dispatch"}, {"MOCK_FAIL": "true"}],
)
def test_candidate_errors_fail_instead_of_becoming_empty_success(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    result = _candidate(tmp_path, [], **changes)
    assert result.returncode != 0
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize("sha", ["", "bad-sha"])
def test_merged_candidate_without_valid_commit_fails(tmp_path: Path, sha: str) -> None:
    result = _candidate(tmp_path, [{"number": 600, "mergeCommit": {"oid": sha}}])
    assert result.returncode != 0
    assert not (tmp_path / "outputs").exists()


def test_multiple_pending_releases_fail_selection(tmp_path: Path) -> None:
    proposals = [{"number": n, "mergeCommit": {"oid": "a" * 40}} for n in [600, 601]]
    result = _candidate(tmp_path, proposals)
    assert result.returncode != 0
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize(
    ("candidate", "sha", "proposal", "gate", "cut", "expected"),
    [
        ("success", "", "success", "skipped", "skipped", 0),
        ("success", "a" * 40, "skipped", "success", "success", 0),
        ("failure", "", "skipped", "skipped", "skipped", 1),
        ("success", "", "failure", "skipped", "skipped", 1),
        ("success", "", "skipped", "skipped", "skipped", 1),
        ("success", "a" * 40, "skipped", "failure", "skipped", 1),
        ("success", "a" * 40, "skipped", "skipped", "skipped", 1),
        ("success", "a" * 40, "skipped", "success", "failure", 1),
        ("success", "a" * 40, "skipped", "success", "skipped", 1),
    ],
)
def test_workflow_result_rejects_failed_or_skipped_required_jobs(
    tmp_path: Path,
    candidate: str,
    sha: str,
    proposal: str,
    gate: str,
    cut: str,
    expected: int,
) -> None:
    result = _run_script(
        tmp_path,
        _job("result")["steps"][0]["run"],
        {
            "CANDIDATE_RESULT": candidate,
            "RELEASE_SHA": sha,
            "PROPOSAL_RESULT": proposal,
            "GATE_RESULT": gate,
            "CUT_RESULT": cut,
        },
    )
    assert result.returncode == expected, result.stderr


def test_push_routes_pending_release_through_proof_and_cut() -> None:
    assert "if" not in _job("candidate")
    proposal = _job()
    assert proposal["needs"] == "candidate"
    assert (
        proposal["if"] == "github.event_name == 'push' && !needs.candidate.outputs.sha"
    )
    gate = _job("prove-gate")
    assert gate["needs"] == "candidate"
    assert gate["if"] == "needs.candidate.outputs.sha != ''"
    assert gate["with"]["ref"] == "${{ needs.candidate.outputs.sha }}"
    assert "if" not in _job("cut")
    result = _job("result")
    assert result["if"] == "${{ !cancelled() }}"
    assert set(result["needs"]) == {"candidate", "release-please", "prove-gate", "cut"}


def test_proposal_checks_become_mergeable_without_manual_dispatch() -> None:
    """A bot proposal must release its required PR verdict after the full proof."""
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/merge-gate.yml").read_text(encoding="utf-8")
    )
    ready = workflow["jobs"]["release-pr-ready"]
    assert ready["needs"] == "gate"
    assert "always()" not in ready["if"] and "!cancelled()" not in ready["if"]
    assert "github.event_name == 'workflow_dispatch'" in ready["if"]
    assert "inputs.ref == github.sha" in ready["if"]
    assert (
        "startsWith(github.ref_name, 'release-please--branches--main')" in ready["if"]
    )
    assert ready["permissions"] == {"actions": "write", "pull-requests": "read"}
    script = ready["steps"][0]["run"]
    assert '.author.is_bot and .author.login == "app/github-actions"' in script
    assert '--head "$BRANCH" --label "autorelease: pending"' in script
    assert 'if [ "$head" != "$SHA" ]' in script
    assert "head_sha=${SHA}&status=action_required" in script
    assert "actions/runs/${run}/approve" in script
    assert "gh pr merge" not in script


APPROVAL_TRANSPORT = r"""
gh() {
  [ "$MOCK_FAIL" != true ] || return 1
  if [ "$1 $2" = 'pr list' ]; then
    printf '%s' "$MOCK_PROPOSALS" | jq -r "${*: -1}"
  elif [ "$1 $2" = 'api --paginate' ]; then
    printf '%s' '{"workflow_runs":[{"id":123}]}' | jq -r "${*: -1}"
  elif [ "$1 $2 $3" = 'api --method POST' ]; then
    printf '%s\n' "$4" >> "$APPROVALS"
  else
    return 99
  fi
}
"""


@pytest.mark.unit
@pytest.mark.parametrize(
    ("login", "is_bot", "head", "api_failure", "expected_approvals"),
    [
        ("app/github-actions", True, "a" * 40, False, 1),
        ("app/github-actions", True, "b" * 40, False, 0),
        ("app/dependabot", True, "a" * 40, False, 0),
        ("app/github-actions", False, "a" * 40, False, 0),
        ("app/github-actions", True, "a" * 40, True, 0),
    ],
)
def test_approval_requires_the_proven_bot_head(
    tmp_path: Path,
    login: str,
    is_bot: bool,
    head: str,
    api_failure: bool,
    expected_approvals: int,
) -> None:
    """Isolate the approval policy from GitHub's transport."""
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/merge-gate.yml").read_text(encoding="utf-8")
    )
    script = workflow["jobs"]["release-pr-ready"]["steps"][0]["run"]
    approvals = tmp_path / "approvals"
    result = _run_script(
        tmp_path,
        APPROVAL_TRANSPORT + script,
        {
            "GITHUB_REPOSITORY": "nevenincs/vaultspec-core",
            "SHA": "a" * 40,
            "BRANCH": "release-please--branches--main--components--vaultspec-core",
            "MOCK_FAIL": str(api_failure).lower(),
            "APPROVALS": approvals.as_posix(),
            "MOCK_PROPOSALS": json.dumps(
                [
                    {
                        "number": 600,
                        "headRefOid": head,
                        "author": {"login": login, "is_bot": is_bot},
                    }
                ]
            ),
        },
    )
    assert result.returncode == int(api_failure), result.stderr
    requests = approvals.read_text().splitlines() if approvals.exists() else []
    assert len(requests) == expected_approvals
    if expected_approvals:
        assert requests == ["repos/nevenincs/vaultspec-core/actions/runs/123/approve"]
