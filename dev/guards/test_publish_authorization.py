"""Exercise publication's authorization boundary without publishing a release."""

from __future__ import annotations

import base64
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
SHA = "a" * 40
TAG = "vaultspec-core-v0.3.2"
REPOSITORY = "nevenincs/vaultspec-core"

# Mock transport only. The workflow's Bash and jq filters run unchanged against
# API response bodies, so merge identity, labels and metadata are really tested.
# `releases/tags/<tag>` is deliberately not served: GitHub answers 404 there for
# a draft, so a lookup through it cannot see the release this lane publishes.
TRANSPORT = r"""
git() {
  [ "$1" = ls-remote ] && [ "$2" = --tags ] || return 99
  [ "$4" = "refs/tags/$TAG" ] && [ "$5" = "refs/tags/$TAG^{}" ] || return 99
  [ "${MOCK_FAIL:-}" != git ] || return 1
  printf '%s\n' "$MOCK_REFS"
}
gh() {
  [ "$1" = api ] || return 99
  local endpoint="$2" filter='' body=''
  shift 2
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --jq) filter="$2"; shift 2 ;;
      --paginate) shift ;;
      *) return 99 ;;
    esac
  done
  case "$endpoint" in
    */compare/*) body="$MOCK_COMPARE" ;;
    */commits/*/pulls) body="$MOCK_PROPOSALS" ;;
    */contents/.release-please-manifest.json?ref=*) body="$MOCK_MANIFEST" ;;
    */releases) body="$MOCK_RELEASES" ;;
    *) return 99 ;;
  esac
  [ "${MOCK_FAIL:-}" != api ] || return 1
  printf '%s' "$body" | jq -r "$filter"
}
"""


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(
        (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    )


def _proposal(**changes: Any) -> dict[str, Any]:
    proposal = {
        "number": 42,
        "merged_at": "2026-10-04T12:00:00Z",
        "merge_commit_sha": SHA,
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
        "labels": [{"name": "autorelease: tagged"}],
    }
    return proposal | changes


def _releases(*, draft: bool, tag: str = TAG) -> list[dict[str, Any]]:
    return [
        {"tag_name": "vaultspec-core-v0.3.1", "draft": False},
        {"tag_name": tag, "draft": draft},
    ]


def _run_gate(
    tmp_path: Path, changes: dict[str, str], *, publication: bool = False
) -> subprocess.CompletedProcess[str]:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.is_file() else shutil.which("bash")
    assert bash is not None, "Bash is required to exercise the release boundary"
    assert shutil.which("jq") is not None, (
        "jq is required for the API fixture transport"
    )
    env = child_environment(
        {
            "TAG": TAG,
            "SHA": SHA,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "c" * 40,
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_OUTPUT": (tmp_path / "outputs").as_posix(),
            "MOCK_REFS": f"{SHA}\trefs/tags/{TAG}",
            "MOCK_COMPARE": json.dumps({"status": "ahead"}),
            "MOCK_PROPOSALS": json.dumps([_proposal()]),
            "MOCK_MANIFEST": json.dumps(
                {"content": base64.b64encode(b'{".": "0.3.2"}').decode("ascii")}
            ),
            "MOCK_RELEASES": json.dumps(_releases(draft=True)),
            "MOCK_FAIL": "",
        }
    )
    env.update(changes)
    jobs = _workflow()["jobs"]
    job = jobs["publish-pypi" if publication else "authorize"]
    script = job["steps"][0]["run"]
    return subprocess.run(
        [bash, "--noprofile", "--norc", "-c", TRANSPORT + script],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize(
    "tag",
    [
        "main",
        SHA,
        f"refs/tags/{TAG}",
        f"{TAG}^{{}}",
        "vaultspec-core-v00.3.2",
        "vaultspec-core-v0.3.2-rc.1",
        TAG + "\nsha=" + SHA,
        "$(touch injected)",
    ],
)
def test_unverified_ref_is_rejected(tmp_path: Path, tag: str) -> None:
    result = _run_gate(tmp_path, {"TAG": tag})
    assert result.returncode != 0, result.stdout
    assert not (tmp_path / "outputs").exists()
    assert not (tmp_path / "injected").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"GITHUB_REF": f"refs/heads/{TAG}"},
        {"GITHUB_REF": f"refs/tags/{TAG}"},
        {"GITHUB_REF": "refs/heads/other"},
        {"MOCK_REFS": ""},
        {"MOCK_REFS": f"{SHA}\trefs/heads/{TAG}"},
        {"MOCK_REFS": f"{'b' * 40}\trefs/tags/{TAG}"},
        {"MOCK_REFS": f"{SHA}\trefs/tags/{TAG}\n{SHA}\trefs/tags/{TAG}"},
        {"MOCK_REFS": f"{SHA}\trefs/tags/{TAG}\ninvalid\trefs/tags/{TAG}^{{}}"},
        {"MOCK_COMPARE": '{"status": "diverged"}'},
        {"MOCK_COMPARE": '{"status": "behind"}'},
        {"MOCK_PROPOSALS": "[]"},
        {"MOCK_PROPOSALS": json.dumps([_proposal(merged_at=None)])},
        {"MOCK_PROPOSALS": json.dumps([_proposal(merge_commit_sha="b" * 40)])},
        {"MOCK_PROPOSALS": json.dumps([_proposal(labels=[])])},
        {"MOCK_PROPOSALS": json.dumps([_proposal(base={"ref": "other"})])},
        {
            "MOCK_PROPOSALS": json.dumps(
                [_proposal(base={"ref": "main", "repo": {"full_name": "other/repo"}})]
            )
        },
        {"MOCK_PROPOSALS": json.dumps([_proposal(), _proposal(number=43)])},
        {"MOCK_MANIFEST": '{"content": "eyIuIjogIjAuMy4zIn0="}'},
        {"MOCK_FAIL": "api"},
        {"MOCK_FAIL": "git"},
    ],
)
def test_missing_or_mismatched_authority_fails_closed(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    result = _run_gate(tmp_path, changes)
    assert result.returncode != 0, result.stdout
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize("annotated", [False, True])
@pytest.mark.parametrize("label", ["autorelease: tagged", "autorelease: pending"])
@pytest.mark.parametrize("draft", [False, True])
def test_authorized_release_and_repair_preserve_the_commit(
    tmp_path: Path, *, annotated: bool, label: str, draft: bool
) -> None:
    refs = f"{SHA}\trefs/tags/{TAG}"
    if annotated:
        refs = f"{'b' * 40}\trefs/tags/{TAG}\n{SHA}\trefs/tags/{TAG}^{{}}"
    changes = {
        "MOCK_REFS": refs,
        "MOCK_PROPOSALS": json.dumps([_proposal(labels=[{"name": label}])]),
        "MOCK_RELEASES": json.dumps(_releases(draft=draft)),
    }
    result = _run_gate(tmp_path, changes)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs").read_text().splitlines() == [
        f"tag={TAG}",
        f"sha={SHA}",
    ]
    result = _run_gate(tmp_path, changes, publication=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "changes",
    [
        {"MOCK_REFS": ""},
        {"MOCK_REFS": f"{'b' * 40}\trefs/tags/{TAG}"},
        {"MOCK_REFS": f"{SHA}\trefs/tags/{TAG}\n{'b' * 40}\trefs/tags/{TAG}^{{}}"},
        {"MOCK_RELEASES": "[]"},
        {"MOCK_RELEASES": "{}"},
        {"MOCK_RELEASES": "invalid JSON"},
        {"MOCK_RELEASES": json.dumps(_releases(draft=True, tag="other"))},
        {"MOCK_RELEASES": json.dumps(_releases(draft=True) * 2)},
        {"MOCK_RELEASES": json.dumps(_releases(draft=False) * 2)},
        {"MOCK_FAIL": "api"},
        {"MOCK_FAIL": "git"},
    ],
)
def test_publication_rejects_tag_or_release_changes(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    result = _run_gate(tmp_path, changes, publication=True)
    assert result.returncode != 0, result.stdout


def test_a_leftover_draft_does_not_block_repairing_a_published_release(
    tmp_path: Path,
) -> None:
    releases = [*_releases(draft=True), *_releases(draft=False)]
    result = _run_gate(
        tmp_path, {"MOCK_RELEASES": json.dumps(releases)}, publication=True
    )
    assert result.returncode == 0, result.stderr


def test_the_release_is_looked_up_where_a_draft_is_visible() -> None:
    """A draft is the state a release is in when publication first runs.

    GitHub serves no draft from `releases/tags/<tag>`, and lists one only for
    a token with `contents: write`. The lookup therefore lists, from the one
    job that holds that scope.
    """
    text = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    jobs = _workflow()["jobs"]
    lookups = [
        line.strip()
        for line in text.splitlines()
        if "gh api" in line and "/releases" in line
    ]
    assert lookups, "no job requires the release to exist before publication"
    assert not any("/releases/tags/" in line for line in lookups), lookups
    assert "/releases" not in str(jobs["authorize"]["steps"])
    guard = jobs["publish-pypi"]["steps"][0]["run"]
    assert 'gh api "repos/$GITHUB_REPOSITORY/releases" --paginate' in guard
    assert jobs["publish-pypi"]["permissions"]["contents"] == "write"


def test_every_publication_path_requires_authorization() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert jobs["authorize"]["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
    }
    assert "steps.release.outputs.sha" in jobs["authorize"]["outputs"]["sha"]
    assert "steps.release.outputs.tag" in jobs["authorize"]["outputs"]["tag"]
    for job_id in ("build", "smoke-test", "publish-pypi"):
        needs = jobs[job_id]["needs"]
        assert "authorize" in ([needs] if isinstance(needs, str) else needs)
        assert "if" not in jobs[job_id], "authorization failure must block this job"
        for step in jobs[job_id]["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                assert step["with"]["ref"] == "${{ needs.authorize.outputs.sha }}"
            if "TAG" in step.get("env", {}):
                assert step["env"]["TAG"] == "${{ needs.authorize.outputs.tag }}"
    publish_steps = jobs["publish-pypi"]["steps"]
    assert "git ls-remote" in publish_steps[0]["run"]
    assert "gh release create" not in str(publish_steps)
    assert all(
        "inputs.tag" not in str(job)
        for job in (jobs["build"], jobs["smoke-test"], jobs["publish-pypi"])
    )


def test_binaries_dispatches_current_publication_policy() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/binaries.yml").read_text(encoding="utf-8")
    )
    handoffs = [
        step["run"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "gh workflow run publish.yml" in step.get("run", "")
    ]
    assert len(handoffs) == 1
    assert '--ref main -f "tag=${TAG}"' in handoffs[0]
