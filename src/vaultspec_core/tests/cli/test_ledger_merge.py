"""Two workers, two worktrees, one ledger: the merge that decides the design.

The ledger is one file per plan, so two workers closing Steps of different
Phases in parallel both append to it and both check their Step in the plan.
With the managed ``.gitattributes`` entry (``merge=union`` on ledgers) and
rows that are idempotent and order-insensitive, the branches must merge
with no conflict and the merged tree must read as one clean, resumable
execution: every closed Step paired with rows, the next open Step named.

Real git, real worktrees, real CLI invocations; no mocks, patches, or skips.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.config import reset_config
from vaultspec_core.core.enums import ManagedState
from vaultspec_core.core.gitattributes import ensure_gitattributes_block
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]

_FEATURE = "merge-feat"
_PLAN_STEM = "2026-05-17-merge-feat-plan"
_LEDGER = ".vault/exec/2026-05-17-merge-feat/2026-05-17-merge-feat-ledger.md"

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_plan(root: Path) -> None:
    plan_dir = root / ".vault" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"{_PLAN_STEM}.md").write_text(
        "---\ntags:\n  - '#plan'\n  - '#merge-feat'\ndate: '2026-05-17'\n"
        "modified: '2026-05-17'\ntier: L2\nrelated: []\n---\n\n"
        "# `merge-feat` plan\n\n## Description\n\nApproved 2026-05-17\n\n"
        "### Phase `P01` - one\n\n"
        "- [ ] `P01.S01` - first; `src/foo.py`.\n"
        "- [ ] `P01.S02` - second; `src/bar.py`.\n\n"
        "### Phase `P02` - two\n\n"
        "- [ ] `P02.S03` - third; `src/baz.py`.\n\n"
        "## Parallelization\n\nP01 and P02 may run concurrently.\n\n"
        "## Verification\n\nProse.\n",
        encoding="utf-8",
    )


def _in_conflict(text: str, needle: str) -> bool:
    """Whether *needle* sits inside a conflict hunk of *text*."""
    inside = False
    for line in text.splitlines():
        if line.startswith("<<<<<<<"):
            inside = True
        elif line.startswith(">>>>>>>"):
            inside = False
        elif inside and line == needle:
            return True
    return False


def _take_first_side(text: str) -> str:
    """Resolve every conflict hunk by keeping its first side."""
    kept: list[str] = []
    state = "out"
    for line in text.splitlines(keepends=True):
        if line.startswith("<<<<<<<"):
            state = "ours"
        elif line.startswith("=======") and state == "ours":
            state = "theirs"
        elif line.startswith(">>>>>>>") and state == "theirs":
            state = "out"
        elif state != "theirs":
            kept.append(line)
    return "".join(kept)


def _cli(root: Path, *args: str):
    runner = CliRunner(env={"NO_COLOR": "1"})
    return runner.invoke(app, ["--target", str(root), *args])


def _close_step(root: Path, step: str, path: str) -> None:
    """One worker's checkpoint: log the Step, close it, commit both."""
    logged = _cli(
        root,
        "vault",
        "exec",
        "log",
        "--feature",
        _FEATURE,
        "--related",
        _PLAN_STEM,
        "--step",
        step,
        "--row",
        f"M:{path}",
        "--verify",
        "pytest=pass",
    )
    assert logged.exit_code == 0, logged.output
    checked = _cli(
        root, "vault", "plan", "step", "check", f".vault/plan/{_PLAN_STEM}.md", step
    )
    assert checked.exit_code == 0, checked.output
    assert _git(root, "add", "-A").returncode == 0
    commit = _git(root, "commit", "-q", "-m", f"close {step}")
    assert commit.returncode == 0, commit.stderr


@pytest.fixture
def repo(tmp_path: Path):
    """An installed workspace under git, with the managed .gitattributes."""
    if shutil.which("git") is None:
        pytest.fail("git is required for the merge test")
    reset_config()
    root = tmp_path / "repo"
    root.mkdir()
    WorkspaceFactory(root).install()
    _write_plan(root)
    # A plan is verb-owned, so the committed base is the serialiser's own
    # shape: check and uncheck one Step to canonicalise it. A hand-written
    # plan that both workers re-serialise conflicts on the lines the
    # serialiser adds, which is the plan's concern, not the ledger's.
    plan = f".vault/plan/{_PLAN_STEM}.md"
    assert _cli(root, "vault", "plan", "step", "check", plan, "S01").exit_code == 0
    assert _cli(root, "vault", "plan", "step", "uncheck", plan, "S01").exit_code == 0
    ensure_gitattributes_block(root, state=ManagedState.PRESENT)
    assert _git(root, "init", "-q", "-b", "main").returncode == 0
    assert _git(root, "add", "-A").returncode == 0
    assert _git(root, "commit", "-q", "-m", "plan approved").returncode == 0
    try:
        yield root
    finally:
        reset_config()


def test_two_worktrees_merge_into_one_clean_ledger(repo: Path, tmp_path: Path) -> None:
    worker_a = tmp_path / "worker-a"
    worker_b = tmp_path / "worker-b"
    assert _git(repo, "worktree", "add", "-q", "-b", "a", str(worker_a)).returncode == 0
    assert _git(repo, "worktree", "add", "-q", "-b", "b", str(worker_b)).returncode == 0

    # Each worker owns a container and closes its first Step.
    reset_config()
    _close_step(worker_a, "P01.S01", "src/foo.py")
    reset_config()
    _close_step(worker_b, "P02.S03", "src/baz.py")

    # Worker A takes B's work: the ledger must merge on its own. The plan is
    # the one file both workers mutated, and its `body_hash:` attestation
    # cannot agree across two independent edits; that single line is the
    # whole conflict, and re-attesting resolves it.
    merge = _git(worker_a, "merge", "-q", "--no-edit", "b")
    unmerged = _git(worker_a, "diff", "--name-only", "--diff-filter=U").stdout.split()
    assert [p.replace("\\", "/") for p in unmerged] in (
        [],
        [f".vault/plan/{_PLAN_STEM}.md"],
    ), f"{merge.stdout}\n{merge.stderr}"

    text = (worker_a / _LEDGER).read_text(encoding="utf-8")
    assert "- `S01` `M` `src/foo.py`" in text
    assert "- `S03` `M` `src/baz.py`" in text
    assert text.count("## Changes") == 1
    assert "<<<<<<<" not in text

    plan_path = worker_a / ".vault" / "plan" / f"{_PLAN_STEM}.md"
    plan_text = plan_path.read_text(encoding="utf-8")
    if unmerged:
        conflicted = [
            line
            for line in plan_text.splitlines()
            if not line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
            and _in_conflict(plan_text, line)
        ]
        assert all(line.startswith("body_hash:") for line in conflicted), conflicted
        plan_path.write_text(_take_first_side(plan_text), encoding="utf-8")
        reset_config()
        fixed = _cli(worker_a, "vault", "check", "modified-stamp", "--fix")
        assert fixed.exit_code == 0, fixed.output
        assert _git(worker_a, "add", "-A").returncode == 0
        assert _git(worker_a, "commit", "-q", "-m", "merge b").returncode == 0
        plan_text = plan_path.read_text(encoding="utf-8")
    assert "- [x] `P01.S01`" in plan_text and "- [x] `P02.S03`" in plan_text
    assert "- [ ] `P01.S02`" in plan_text

    reset_config()
    check = _cli(worker_a, "vault", "check", "exec-mapping", "--feature", _FEATURE)
    assert check.exit_code == 0, check.output
    assert "ERROR" not in check.output

    status = _cli(worker_a, "status", _PLAN_STEM)
    assert status.exit_code == 0, status.output
    lines = {
        key: next(
            line for line in status.output.splitlines() if key in line and "[" in line
        )
        for key in ("P01.S01", "P01.S02", "P02.S03")
    }
    assert "ledger 1 row" in lines["P01.S01"] and "verify:pass" in lines["P01.S01"]
    assert "ledger 1 row" in lines["P02.S03"]
    assert "no rows" in lines["P01.S02"]
    assert "next P01.S02" in status.output


def test_managed_gitattributes_declares_the_union_merge(repo: Path) -> None:
    text = (repo / ".gitattributes").read_text(encoding="utf-8")

    assert ".vault/exec/**/*-ledger.md merge=union" in text
    attr = _git(repo, "check-attr", "merge", "--", _LEDGER)
    assert attr.stdout.strip().endswith("merge: union"), attr.stdout
