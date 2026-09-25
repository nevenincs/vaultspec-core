"""Real filesystem and Git checks for private environment provisioning."""

from __future__ import annotations

import os
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY as KEY
from vaultspec_core.config import get_config
from vaultspec_core.config.credential import CredentialSource, resolve_credential
from vaultspec_core.config.dotenv import format_dotenv, parse_dotenv
from vaultspec_core.config.local_env import LOCAL_ENV, read_local_environment
from vaultspec_core.config.provisioning import (
    apply_environment,
    prepare_environment,
)
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.core.git_artifacts import (
    check_staged_provider_artifacts,
    per_machine_paths,
    untrack_managed_paths,
)
from vaultspec_core.core.install_mode import write_mode_declaration

pytestmark = [pytest.mark.integration]

FAKE_KEY = "fake-local-credential-for-tests"
BUFFER = "VAULTSPEC_IO_BUFFER_SIZE"
HINTS = "VAULTSPEC_NO_HINTS"


def _store(root: Path, **values: str) -> None:
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    request = prepare_environment(root, list(values), environ=values)
    apply_environment(root, request)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize("mode", list(InstallMode))
def test_local_credentials_work_in_every_mode(
    tmp_path: Path, mode: InstallMode
) -> None:
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    write_mode_declaration(tmp_path, mode)
    credential = resolve_credential(
        KEY, tmp_path, {}, interpreter_prefix=Path("/elsewhere")
    )
    assert credential is not None
    assert credential.key == FAKE_KEY
    assert credential.source is CredentialSource.LOCAL_ENV
    assert FAKE_KEY not in repr(credential)


def test_process_and_blank_override_local_and_root_dotenv(tmp_path: Path) -> None:
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    write_mode_declaration(tmp_path, InstallMode.DEV)
    (tmp_path / ".env").write_text(f"{KEY.env_name}=old-root-key\n")
    chosen = resolve_credential(KEY, tmp_path, {KEY.env_name: "session-key"})
    assert chosen is not None and chosen.key == "session-key"
    assert chosen.source is CredentialSource.ENVIRONMENT
    assert resolve_credential(KEY, tmp_path, {KEY.env_name: "  "}) is None
    _store(tmp_path, **{KEY.env_name: ""})
    assert (
        resolve_credential(KEY, tmp_path, {}, interpreter_prefix=tmp_path / ".venv")
        is None
    )


def test_import_precedence_preservation_and_repr(tmp_path: Path) -> None:
    _store(tmp_path, **{KEY.env_name: FAKE_KEY, HINTS: "1"})
    source = tmp_path / "source.env"
    source.write_text(f"{BUFFER}=2048\n{KEY.env_name}=replacement\n")
    request = prepare_environment(
        tmp_path, [f"{BUFFER}=4096", f"{BUFFER}=8192"], source
    )
    assert "replacement" not in repr(request)
    result = apply_environment(tmp_path, request)
    assert result == {BUFFER: "created", KEY.env_name: "updated"}
    assert read_local_environment(tmp_path) == {
        KEY.env_name: "replacement",
        HINTS: "1",
        BUFFER: "8192",
    }
    assert all(
        outcome == "unchanged"
        for outcome in apply_environment(tmp_path, request).values()
    )


@pytest.mark.parametrize(
    "entry",
    [
        f"{KEY.env_name}={FAKE_KEY}",
        "UNSUPPORTED=secret-text",
        f"{BUFFER}=nan",
        f"{BUFFER}=-1",
        f"{HINTS}=a\nb",
        "VAULTSPEC_TARGET_DIR=/another-project",
    ],
)
def test_bad_import_never_echoes_value_or_writes(tmp_path: Path, entry: str) -> None:
    with pytest.raises(VaultSpecError) as caught:
        prepare_environment(tmp_path, [entry])
    assert entry.partition("=")[2] not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_missing_process_import_does_not_read_lower_sources(tmp_path: Path) -> None:
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    with pytest.raises(VaultSpecError, match="not present"):
        prepare_environment(tmp_path, [KEY.env_name], environ={})


@pytest.mark.parametrize(
    "contents",
    ["not an assignment", 'NAME="unterminated', "X=" + "z" * 65536],
    ids=["invalid-line", "unclosed-quote", "oversized"],
)
def test_invalid_file_errors_hide_contents(tmp_path: Path, contents: str) -> None:
    source = tmp_path / "source.env"
    source.write_text(contents)
    with pytest.raises(VaultSpecError) as caught:
        prepare_environment(tmp_path, env_file=source)
    assert contents not in str(caught.value)


def test_quoted_literals_round_trip_without_interpolation() -> None:
    values = {"A": "x\"y'z\\path ${SHELL} # literal", "B": ""}
    assert parse_dotenv(format_dotenv(values)) == values


def test_real_git_protection_and_force_added_guard(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    assert LOCAL_ENV in _git(tmp_path, "check-ignore", LOCAL_ENV)
    _git(tmp_path, "add", "-A")
    assert LOCAL_ENV not in _git(tmp_path, "ls-files")
    _git(tmp_path, "add", "-f", LOCAL_ENV)
    assert LOCAL_ENV in check_staged_provider_artifacts(tmp_path)
    assert per_machine_paths(
        tmp_path,
        [
            "nested/.vaultspec/.env",
            "nested/.vaultspec/.env.abc.tmp",
            "nested/.env.example",
        ],
    ) == ["nested/.vaultspec/.env", "nested/.vaultspec/.env.abc.tmp"]
    assert untrack_managed_paths(tmp_path, [LOCAL_ENV]) == []
    with pytest.raises(VaultSpecError, match="tracked"):
        prepare_environment(tmp_path, [f"{HINTS}=1"])
    with pytest.raises(VaultSpecError, match="tracked"):
        read_local_environment(tmp_path)


def test_ignore_removal_invalidates_cached_credentials(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    assert read_local_environment(tmp_path)[KEY.env_name] == FAKE_KEY
    (tmp_path / ".gitignore").write_text("")
    with pytest.raises(VaultSpecError, match="gitignored"):
        read_local_environment(tmp_path)


def test_worktrees_keep_separate_local_settings_and_indexes(tmp_path: Path) -> None:
    main, linked = tmp_path / "main", tmp_path / "linked"
    main.mkdir()
    _git(main, "init", "-q")
    _git(
        main,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "initial",
    )
    _git(main, "worktree", "add", "-b", "linked", str(linked))
    _store(main, **{KEY.env_name: "main-key"})
    _store(linked, **{KEY.env_name: "linked-key"})
    assert read_local_environment(main)[KEY.env_name] == "main-key"
    assert read_local_environment(linked)[KEY.env_name] == "linked-key"
    _git(linked, "add", "-f", LOCAL_ENV)
    with pytest.raises(VaultSpecError, match="tracked"):
        read_local_environment(linked)
    assert read_local_environment(main)[KEY.env_name] == "main-key"


def test_redirected_store_is_refused_before_read_or_write(tmp_path: Path) -> None:
    framework = tmp_path / ".vaultspec"
    framework.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    try:
        (tmp_path / LOCAL_ENV).symlink_to(outside)
    except OSError:
        assert not (tmp_path / LOCAL_ENV).exists()
        return
    with pytest.raises(VaultSpecError, match="redirected"):
        prepare_environment(tmp_path, [f"{HINTS}=1"])
    with pytest.raises(VaultSpecError, match="redirected"):
        read_local_environment(tmp_path)
    assert outside.read_text() == "untouched"


def test_workspace_and_file_refresh_for_long_running_host(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _store(left, **{BUFFER: "4096"})
    _store(right, **{BUFFER: "16384"})
    assert get_config(root=left).io_buffer_size == 4096
    assert get_config(root=right).io_buffer_size == 16384
    assert get_config(root=left).io_buffer_size == 4096
    _store(left, **{BUFFER: "8192"})
    assert get_config(root=left).io_buffer_size == 8192
    original = os.environ.get(BUFFER)
    try:
        os.environ[BUFFER] = "2048"
        assert get_config(root=left).io_buffer_size == 2048
        os.environ[BUFFER] = "1024"
        assert get_config(root=left).io_buffer_size == 1024
        assert get_config({"io_buffer_size": 512}, root=left).io_buffer_size == 512
    finally:
        if original is None:
            os.environ.pop(BUFFER, None)
        else:
            os.environ[BUFFER] = original


def test_concurrent_merges_preserve_both_keys(tmp_path: Path) -> None:
    (tmp_path / ".vaultspec").mkdir()
    first = prepare_environment(tmp_path, [f"{BUFFER}=4096"])
    second = prepare_environment(tmp_path, [f"{HINTS}=1"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [
            pool.submit(apply_environment, tmp_path, req) for req in (first, second)
        ]
        for task in tasks:
            task.result()
    assert read_local_environment(tmp_path) == {BUFFER: "4096", HINTS: "1"}


def test_restricted_permissions(tmp_path: Path) -> None:
    _store(tmp_path, **{KEY.env_name: FAKE_KEY})
    path = tmp_path / LOCAL_ENV
    if os.name == "nt":
        # Inspect the actual DACL rather than the Windows chmod facade.
        result = subprocess.run(
            ["icacls", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "(I)" not in result.stdout
        assert result.stdout.count("(F)") == 1
    else:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
