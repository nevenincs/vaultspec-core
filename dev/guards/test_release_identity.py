"""Automation writes pull requests as the fleet release App, and nothing else.

A pull request the workflow token writes is authored by `github-actions[bot]`.
The merge gate never reaches the fleet for that author, so its required check
never reports and the pull request cannot merge. Every workaround for that -
dispatching the gate by hand on the branch, approving held runs, merging past
the check - leaves a check GitHub links to no pull request, or a bypass. So a
workflow that opens or updates a pull request does it with a token minted from
the release App, a trusted author whose pull request runs the gate on its own
events. There is no fallback to the workflow token: a missing App must fail
the workflow, not quietly bring the unmergeable pull request back.

Tags and releases stay on the workflow token, because GitHub raises no
workflow events for refs and releases that token creates; nothing that listens
for them is woken twice.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.repo]

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

RELEASE_PLEASE = "googleapis/release-please-action@"
APP_TOKEN_ACTION = re.compile(r"^actions/create-github-app-token@[0-9a-f]{40}$")

#: The inputs every App token is minted with: the fleet App's identity, and
#: exactly the two permissions a pull request writer needs.
APP_TOKEN_INPUTS = {
    "client-id": "${{ vars.RELEASE_APP_CLIENT_ID }}",
    "private-key": "${{ secrets.RELEASE_APP_PRIVATE_KEY }}",
    "permission-contents": "write",
    "permission-pull-requests": "write",
}

_EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
_STEP_TOKEN = re.compile(r"^\$\{\{\s*steps\.([A-Za-z0-9_-]+)\.outputs\.token\s*\}\}$")


def _workflow_paths() -> list[Path]:
    paths = sorted(WORKFLOWS.glob("*.yml"))
    assert paths, f"no workflow files found under {WORKFLOWS}"
    return paths


def _jobs(path: Path) -> dict[str, dict[str, Any]]:
    document = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    return cast("dict[str, dict[str, Any]]", document.get("jobs") or {})


def _steps() -> Iterator[tuple[str, list[dict[str, Any]], int]]:
    """Every step, with the job's step list and its index in it."""
    for path in _workflow_paths():
        for job_id, job in _jobs(path).items():
            steps = cast("list[dict[str, Any]]", job.get("steps") or [])
            for index in range(len(steps)):
                yield f"{path.name}:{job_id}", steps, index


def _minted_by_the_app(token: str, steps: list[dict[str, Any]], index: int) -> bool:
    """Whether `token` is the output of an earlier App-token step in this job."""
    match = _STEP_TOKEN.fullmatch(token.strip())
    if match is None:
        return False
    minters = [step for step in steps[:index] if step.get("id") == match.group(1)]
    return len(minters) == 1 and (
        APP_TOKEN_ACTION.fullmatch(str(minters[0].get("uses", ""))) is not None
        and cast("dict[str, str]", minters[0].get("with") or {}) == APP_TOKEN_INPUTS
    )


def _with(step: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", step.get("with") or {})


def test_every_pull_request_writer_uses_the_release_app() -> None:
    """Release Please's pull request and `gh pr create` both carry the App token.

    Mutation proof: setting the proposal step's `token` to
    `${{ secrets.GITHUB_TOKEN }}` makes this fail on
    `release-please.yml:release-please`; restoring it makes this pass.
    """
    writers: list[str] = []
    offenders: list[str] = []
    for where, steps, index in _steps():
        step = steps[index]
        uses = str(step.get("uses", ""))
        if uses.startswith(RELEASE_PLEASE):
            if str(_with(step).get("skip-github-pull-request", "")).lower() == "true":
                continue
            token = str(_with(step).get("token", ""))
        elif "gh pr create" in str(step.get("run", "")):
            token = str(cast("dict[str, Any]", step.get("env") or {}).get("GH_TOKEN"))
        else:
            continue
        writers.append(where)
        if not _minted_by_the_app(token, steps, index):
            offenders.append(f"{where}: {token or '(default token)'}")
    assert {"release-please.yml:release-please", "surface.yml:record"} <= set(
        writers
    ), f"the pull request writers resolved to {writers}"
    assert not offenders, (
        "these steps write a pull request without a token minted from the "
        f"release App with exactly its pinned inputs: {offenders}"
    )


def test_tags_and_releases_stay_on_the_workflow_token() -> None:
    """The step that creates the release passes no token of its own.

    Mutation proof: adding `token: ${{ steps.app.outputs.token }}` to the
    cut's release step makes this fail on `release-please.yml:cut`; removing it
    makes this pass.
    """
    creators: list[str] = []
    for where, steps, index in _steps():
        step = steps[index]
        if not str(step.get("uses", "")).startswith(RELEASE_PLEASE):
            continue
        if str(_with(step).get("skip-github-release", "")).lower() == "true":
            continue
        creators.append(where)
        assert "token" not in _with(step), (
            f"{where} creates the release with a token of its own; tags and "
            "releases stay on the workflow token so no workflow is woken twice"
        )
    assert creators == ["release-please.yml:cut"], creators


def test_no_token_falls_back_to_another() -> None:
    """`a || b` over credentials hides a missing App behind the workflow token.

    Mutation proof: setting the proposal step's `token` to
    `${{ steps.app.outputs.token || secrets.GITHUB_TOKEN }}` makes this fail
    naming that expression; restoring it makes this pass.
    """
    offenders = [
        f"{path.name}: {expression.strip()}"
        for path in _workflow_paths()
        for expression in _EXPRESSION.findall(path.read_text(encoding="utf-8"))
        if "||" in expression
        and re.search(r"secrets\.|github\.token|outputs\.token", expression)
    ]
    assert not offenders, f"these expressions fall back between tokens: {offenders}"


def test_no_workflow_works_around_an_unmergeable_pull_request() -> None:
    """No hand-dispatched gate, no approved held run, no merge past the check.

    A dispatched merge-gate run is linked to no pull request, so it never
    satisfies the ruleset; approving held runs and merging by workflow are
    what used to stand in for a trusted author.

    Mutation proof: restoring `gh workflow run merge-gate.yml` to surface.yml's
    pull request step makes this fail naming it; removing it makes this pass.
    """
    forbidden = {
        "gh workflow run merge-gate.yml": "dispatches the merge gate by hand",
        "/approve": "approves a held run",
        "gh pr merge": "merges a pull request itself",
        "--admin": "merges past the ruleset",
    }
    offenders = [
        f"{where}: {reason}"
        for where, steps, index in _steps()
        for needle, reason in forbidden.items()
        if needle in str(steps[index].get("run", ""))
    ]
    assert not offenders, offenders


def test_the_lockfile_version_rides_in_the_release_commit() -> None:
    """Release Please bumps `uv.lock` in its own commit; nothing pushes after it.

    A second commit on the release branch is a second head, and one pushed by
    the workflow token would start no merge gate at all. The jsonpath names
    the lock's entry for this project; the manifest and the lock must already
    agree, or the bump would land on a version the lock never held.

    Mutation proof: deleting the `extra-files` entry from
    release-please-config.json makes this fail; restoring it makes this pass.
    """
    config = json.loads((ROOT / "release-please-config.json").read_text("utf-8"))
    package = cast("dict[str, Any]", config["packages"]["."])
    name = str(package["package-name"])
    assert {
        "type": "toml",
        "path": "uv.lock",
        "jsonpath": f"$.package[?(@.name.value=='{name}')].version",
    } in cast("list[dict[str, str]]", package.get("extra-files", [])), (
        "release-please no longer bumps this project's version in uv.lock"
    )

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in cast("list[dict[str, Any]]", lock["package"])
        if entry.get("name") == name
    ]
    manifest = json.loads(
        (ROOT / ".release-please-manifest.json").read_text(encoding="utf-8")
    )
    assert [entry.get("version") for entry in entries] == [manifest["."]]

    pushers = [
        where
        for where, steps, index in _steps()
        if "uv lock" in str(steps[index].get("run", ""))
    ]
    assert not pushers, f"these steps regenerate uv.lock in a workflow: {pushers}"
