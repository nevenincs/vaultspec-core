"""Guards for the `.env` preflight of ``just init``.

Every contract below fails quietly rather than loudly. A `.env` that comes out
empty, or stripped of the example's documentation, still counts as present, so
no later run repairs it. A carry flag the plan never passes looks like it works
until a new worktree turns up without its key. And an existing `.env` that gets
overwritten loses the operator's credentials with no way back.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dev import environment
from dev.init import plan
from dev.init.dotenv import main

pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[3]

#: An example shaped like the real one: CRLF endings, documentation, commented
#: declarations, one active placeholder, and a byte that is not UTF-8. The copy
#: must keep every one of them.
EXAMPLE = (
    b"# Header comment\r\n"
    b"\r\n"
    b"# The hosted-search key. Never commit a credential here.\r\n"
    b"# VAULTSPEC_CORE_TYPESAFE_API_KEY=\r\n"
    b"\r\n"
    b"# Root log level.\r\n"
    b"# VAULTSPEC_LOG_LEVEL=INFO\r\n"
    b"ACTIVE_PLACEHOLDER=change-me\r\n"
    b"# caf\xe9\r\n"
)

#: A main worktree `.env` exercising every rule of the carry: a reassigned
#: name (the last assignment wins), an ``export`` prefix and quotes kept as
#: written, a blank value (unset, so not carried), and a name the example does
#: not declare.
MAIN_ENV = (
    "VAULTSPEC_CORE_TYPESAFE_API_KEY=superseded\n"
    'export VAULTSPEC_CORE_TYPESAFE_API_KEY="carried-secret"\n'
    "ACTIVE_PLACEHOLDER=real-value\n"
    "VAULTSPEC_LOG_LEVEL=\n"
    "GOOGLE_CLOUD_PROJECT_ID=stale\n"
)

#: What a linked worktree's `.env` must hold when carried from ``MAIN_ENV``.
CARRIED = (
    b"# Header comment\r\n"
    b"\r\n"
    b"# The hosted-search key. Never commit a credential here.\r\n"
    b'VAULTSPEC_CORE_TYPESAFE_API_KEY="carried-secret"\r\n'
    b"\r\n"
    b"# Root log level.\r\n"
    b"# VAULTSPEC_LOG_LEVEL=INFO\r\n"
    b"ACTIVE_PLACEHOLDER=real-value\r\n"
    b"# caf\xe9\r\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


def _worktrees(tmp_path: Path, relative: str = ".env") -> tuple[Path, Path]:
    """Create a repository and a linked worktree, both carrying the example.

    Args:
        tmp_path: The directory to create them in.
        relative: Where the example sits inside each worktree.

    Returns:
        The main worktree and the linked one.
    """
    primary, linked = tmp_path / "main", tmp_path / "linked"
    primary.mkdir()
    _git(primary, "init", "-q")
    _git(
        primary,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "initial",
    )
    _git(primary, "worktree", "add", "-q", "-b", "linked", str(linked))
    for root in (primary, linked):
        example = root / relative
        example = example.with_name(f"{example.name}.example")
        example.parent.mkdir(parents=True, exist_ok=True)
        example.write_bytes(EXAMPLE)
    return primary, linked


def test_the_example_is_copied_byte_for_byte(tmp_path: Path) -> None:
    example, target = tmp_path / ".env.example", tmp_path / ".env"
    example.write_bytes(EXAMPLE)

    assert main([str(example), str(target)]) == 0
    assert target.read_bytes() == EXAMPLE


def test_a_linked_worktree_carries_the_declared_values_in_place(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    primary, linked = _worktrees(tmp_path)
    (primary / ".env").write_text(MAIN_ENV, encoding="utf-8")

    code = main(
        [str(linked / ".env.example"), str(linked / ".env"), "--from-main-worktree"]
    )

    assert code == 0
    assert (linked / ".env").read_bytes() == CARRIED
    output = capsys.readouterr()
    reported = output.out + output.err
    assert "Carried VAULTSPEC_CORE_TYPESAFE_API_KEY, ACTIVE_PLACEHOLDER" in reported
    assert "not declared in .env.example: GOOGLE_CLOUD_PROJECT_ID." in reported
    assert "carried-secret" not in reported
    assert "real-value" not in reported


def test_a_nested_target_carries_from_the_same_path_in_the_main_worktree(
    tmp_path: Path,
) -> None:
    primary, linked = _worktrees(tmp_path, relative="service/.env")
    (primary / "service" / ".env").write_text(MAIN_ENV, encoding="utf-8")
    (primary / ".env").write_text("ACTIVE_PLACEHOLDER=wrong-file\n", encoding="utf-8")

    code = main(
        [
            str(linked / "service" / ".env.example"),
            str(linked / "service" / ".env"),
            "--from-main-worktree",
        ]
    )

    assert code == 0
    assert (linked / "service" / ".env").read_bytes() == CARRIED


def test_without_a_main_worktree_env_the_example_is_copied_as_is(
    tmp_path: Path,
) -> None:
    _, linked = _worktrees(tmp_path)

    code = main(
        [str(linked / ".env.example"), str(linked / ".env"), "--from-main-worktree"]
    )

    assert code == 0
    assert (linked / ".env").read_bytes() == EXAMPLE


def test_outside_a_repository_the_carry_falls_back_to_the_example(
    tmp_path: Path,
) -> None:
    example, target = tmp_path / ".env.example", tmp_path / ".env"
    example.write_bytes(EXAMPLE)

    assert main([str(example), str(target), "--from-main-worktree"]) == 0
    assert target.read_bytes() == EXAMPLE


def test_an_existing_env_is_never_overwritten(tmp_path: Path) -> None:
    primary, linked = _worktrees(tmp_path)
    (primary / ".env").write_text(MAIN_ENV, encoding="utf-8")
    (linked / ".env").write_bytes(b"VAULTSPEC_CORE_TYPESAFE_API_KEY=mine\n")

    code = main(
        [str(linked / ".env.example"), str(linked / ".env"), "--from-main-worktree"]
    )

    assert code == 0
    assert (linked / ".env").read_bytes() == b"VAULTSPEC_CORE_TYPESAFE_API_KEY=mine\n"


def test_a_missing_example_fails_and_creates_nothing(tmp_path: Path) -> None:
    target = tmp_path / ".env"

    assert main([str(tmp_path / ".env.example"), str(target)]) == 1
    assert not target.exists()


def test_the_init_preflight_carries_into_a_linked_worktree(tmp_path: Path) -> None:
    """Run the declared preflight step exactly as the runner launches it.

    The flag only matters if the plan passes it, from the worktree root, with
    the relative paths the step declares - which a call to :func:`main` with
    absolute paths would not show.
    """
    primary, linked = _worktrees(tmp_path)
    (primary / ".env").write_text(MAIN_ENV, encoding="utf-8")
    (step,) = [step for step in plan.PREFLIGHT if step.name == "dotenv"]

    completed = subprocess.run(
        step.argv,
        cwd=linked,
        env=environment.child_environment({"PYTHONPATH": str(REPO_ROOT)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (linked / ".env").read_bytes() == CARRIED
