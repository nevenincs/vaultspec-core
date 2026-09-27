"""Guards for what THIS repository's `just init` does to its tracked files.

A fresh worktree must come out of `init` with nothing to commit. The framework
step once ran ``install --force``, which copies the package's bundled builtins
over the tracked `.vaultspec/`, so every new worktree started with modified
files whenever the two differed. Nothing reported it; the diff just waited to
be swept into somebody's next commit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dev.init import plan

pytestmark = [pytest.mark.repo]

REPO_ROOT = Path(__file__).resolve().parents[3]

#: A tracked builtin the package also bundles, edited in the copy so the
#: tracked and bundled versions disagree however the checkout stands.
DRIFTED = ".vaultspec/rules/vaultspec.builtin.md"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def test_the_framework_step_leaves_tracked_files_untouched(tmp_path: Path) -> None:
    tracked = _git(REPO_ROOT, "ls-files", "--", ".vaultspec", ".gitignore")
    paths = tracked.splitlines()
    assert DRIFTED in paths, f"{DRIFTED} is no longer tracked; pick another builtin"
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    with (tmp_path / DRIFTED).open("a", encoding="utf-8") as drifted:
        drifted.write("\nA local amendment the package does not bundle.\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        "tracked framework",
    )
    (step,) = [step for step in plan.TOOLS.steps if step.name == "framework-install"]
    arguments = step.argv[step.argv.index("vaultspec-core") + 1 :]
    environment = {
        name: value
        for name, value in os.environ.items()
        if name != "VAULTSPEC_TARGET_DIR"
    }

    completed = subprocess.run(
        [sys.executable, "-m", "vaultspec_core", *arguments],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (tmp_path / ".vaultspec" / "providers.json").is_file()
    assert _git(tmp_path, "status", "--porcelain", "--untracked-files=no") == ""
