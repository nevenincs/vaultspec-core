"""Private project environment storage shared by CLI and MCP.

No values are loaded into the process environment. Git checks and permissions
guard the dedicated local store; the caller supplies its workspace explicitly.
"""

from __future__ import annotations

import csv
import os
import stat
import subprocess
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

from ..core.exceptions import VaultSpecError
from ..core.helpers import require_executable
from .dotenv import format_dotenv, parse_dotenv

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .config import ConfigVariable

LOCAL_ENV: Final = ".vaultspec/.env"
ENV_IGNORE_ENTRIES: Final = ("/.vaultspec/.env", "/.vaultspec/.env.*")
MAX_ENV_BYTES: Final = 65_536

#: The committable dotenv template. It documents the variables and holds no
#: values, so it is the one dotenv name left trackable.
DOTENV_TEMPLATE: Final = ".env.example"

#: Every ``.env`` and ``.env.*`` file, at any depth: dotenv files hold secrets.
#: Unanchored, so Git matches them in every directory. The negation must follow
#: the glob it carves the template out of.
DOTENV_IGNORE_ENTRIES: Final = (".env", ".env.*", f"!{DOTENV_TEMPLATE}")


def _is_dotenv_name(name: str) -> bool:
    return name == ".env" or name.startswith(".env.")


def is_local_environment_path(path: str) -> bool:
    """Identify files that hold credentials and must never be committed.

    Every ``.env`` and ``.env.*`` file at any depth, other than a
    ``.env.example`` template; under ``.vaultspec/`` the private store's
    template-named temporaries count too.
    """
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or not _is_dotenv_name(parts[-1]):
        return False
    return parts[-1] != DOTENV_TEMPLATE or (
        len(parts) >= 2 and parts[-2] == ".vaultspec"
    )


def tracked_dotenv_files(root: Path) -> list[str]:
    """Return the dotenv files the Git index tracks, templates excluded.

    Args:
        root: Workspace root.

    Returns:
        The tracked root-relative paths, at any depth; empty outside a
        repository.

    Raises:
        VaultSpecError: When Git cannot report the index.
    """
    if not _in_git(root):
        return []
    result = _git(root, "ls-files", "--", ":(glob)**/.env", ":(glob)**/.env.*")
    if result.returncode:
        raise VaultSpecError("Cannot verify whether a .env file is tracked.")
    return [
        name
        for name in (line.strip() for line in result.stdout.splitlines())
        if name and is_local_environment_path(name)
    ]


def _plain_path(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise VaultSpecError("Local environment storage cannot use redirected paths.")


def validate_store_path(root: Path) -> Path:
    """Reject symlinks, junctions and non-files at the private storage paths."""
    path = root / LOCAL_ENV
    for item in (path.parent, path, path.with_name(".env.lock")):
        _plain_path(item)
    if path.exists() and not path.is_file():
        raise VaultSpecError("Local environment storage must be a regular file.")
    return path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [require_executable("git"), "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VaultSpecError(
            "Cannot verify Git protection for local settings."
        ) from None


def _in_git(root: Path) -> bool:
    if not root.exists():
        return False
    probe = root
    if not any((parent / ".git").exists() for parent in (probe, *probe.parents)):
        return False
    result = _git(probe, "rev-parse", "--is-inside-work-tree")
    if result.returncode:
        raise VaultSpecError("Cannot verify repository protection for local settings.")
    return True


def reject_tracked_store(root: Path, *, provisioning: bool = False) -> None:
    """Refuse tracked local credentials instead of silently untracking them."""
    path = validate_store_path(root)
    if not provisioning and not path.exists() and not any(path.parent.glob(".env.*")):
        return
    if not _in_git(root):
        return
    tracked = _git(root, "ls-files", "--", LOCAL_ENV, LOCAL_ENV + ".*")
    if tracked.returncode or tracked.stdout.strip():
        raise VaultSpecError(
            "Local environment storage is tracked or Git status cannot be verified.",
            hint="Remove it from the Git index and rotate any exposed credentials.",
        )


def _check_ignored(root: Path) -> None:
    if _in_git(root):
        result = _git(root, "check-ignore", "-q", "--", LOCAL_ENV)
        if result.returncode:
            raise VaultSpecError("Local environment storage must be gitignored.")
    else:
        ignore = root / ".gitignore"
        _plain_path(ignore)
        try:
            lines = ignore.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            lines = []
        if not all(entry in lines for entry in ENV_IGNORE_ENTRIES):
            raise VaultSpecError(
                "Local environment storage requires ignore protection."
            )


def protect_store(root: Path) -> None:
    """Establish compulsory ignores outside the optional managed block."""
    from ..core.helpers import advisory_lock, atomic_write

    reject_tracked_store(root, provisioning=True)
    ignore = root / ".gitignore"
    _plain_path(ignore)
    _plain_path(root / ".gitignore.lock")
    with advisory_lock(ignore):
        text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        # Keep these at the end so earlier negations cannot re-include secrets.
        suffix = "\n# Private VaultSpec environment (never commit)\n"
        suffix += "\n".join(ENV_IGNORE_ENTRIES) + "\n"
        if not text.endswith(suffix):
            atomic_write(ignore, text.rstrip("\n") + "\n" + suffix)
    _check_ignored(root)


def read_environment_file(path: Path) -> dict[str, str]:
    """Read a bounded import; all failures omit path and file contents."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_ENV_BYTES + 1)
        if len(raw) > MAX_ENV_BYTES:
            raise VaultSpecError("Environment file exceeds the 64 KiB limit.")
        return parse_dotenv(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError):
        raise VaultSpecError("Cannot read environment file as UTF-8.") from None
    except ValueError:
        raise VaultSpecError(
            "Environment file contains an invalid assignment."
        ) from None


def _stamp(path: Path) -> tuple[int, int, int, int]:
    try:
        data = path.stat()
        return data.st_mtime_ns, data.st_ctime_ns, data.st_size, data.st_mode
    except OSError:
        return (0, 0, 0, 0)


def read_local_environment(root: Path) -> dict[str, str]:
    """Return private settings, refreshed after file, index or ignore changes."""
    root = root.resolve()
    path = validate_store_path(root)
    if not path.exists():
        return {}
    # Git worktrees may keep their index elsewhere. Ask Git only when a store
    # exists; keyless installations pay no subprocess cost here.
    markers = tuple(
        (parent / ".git", _stamp(parent / ".git")) for parent in (root, *root.parents)
    )
    index_path = _index_path(root, markers)
    ignores = tuple(
        _stamp(parent / ".gitignore") for parent in (path.parent, root, *root.parents)
    )
    return dict(_read_cached(root, _stamp(path), ignores, _stamp(index_path)))


def store_root(root: Path | None = None) -> Path:
    """Return the workspace whose store a read consults: *root*, else the context's."""
    if root is not None:
        return root.resolve()
    from ..core.types import get_context

    try:
        return get_context().target_dir.resolve()
    except LookupError:
        return Path.cwd().resolve()


def stored_setting(
    chain: Sequence[ConfigVariable], root: Path | None = None
) -> tuple[ConfigVariable, str] | None:
    """Return the first persistable entry of *chain* the store sets, and its value.

    The store is persisted configuration, so the settings resolver asks it only
    after the session environment. Blank is unset here as there.

    Args:
        chain: Entries in resolution order; only persistable ones are looked up.
        root: Workspace whose store is read; ``None`` is the current context's.

    Returns:
        The entry and its stripped value, or ``None`` when none is set.

    Raises:
        VaultSpecError: If the store exists but cannot be trusted.
    """
    persistable = [var for var in chain if var.persistable]
    if not persistable:
        return None
    values = read_local_environment(store_root(root))
    for var in persistable:
        value = values.get(var.env_name, "").strip()
        if value:
            return var, value
    return None


@lru_cache(maxsize=16)
def _index_path(
    root: Path, markers: tuple[tuple[Path, tuple[int, int, int, int]], ...]
) -> Path:
    del markers
    if not _in_git(root):
        return root / ".git"
    index = _git(root, "rev-parse", "--git-path", "index")
    path = Path(index.stdout.strip()) if index.returncode == 0 else root / ".git"
    return path if path.is_absolute() else root / path


@lru_cache(maxsize=16)
def _read_cached(
    root: Path,
    file_stamp: tuple[int, int, int, int],
    ignore_stamp: tuple[tuple[int, int, int, int], ...],
    index_stamp: tuple[int, int, int, int],
) -> tuple[tuple[str, str], ...]:
    del ignore_stamp, index_stamp
    reject_tracked_store(root)
    _check_ignored(root)
    if os.name != "nt" and file_stamp[3] & (stat.S_IRWXG | stat.S_IRWXO):
        raise VaultSpecError(
            "Local environment file requires owner-only permissions (0600)."
        )
    from .provisioning import validate_values

    values = read_environment_file(root / LOCAL_ENV)
    validate_values(values)
    return tuple(values.items())


@lru_cache(maxsize=1)
def _windows_sid() -> str:
    result = subprocess.run(
        [
            require_executable("whoami", windows_system=True),
            "/user",
            "/fo",
            "csv",
            "/nh",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    sid = next(csv.reader([result.stdout.strip()]))[-1]
    if not sid.startswith("S-1-") or not all(c.isdigit() or c in "S-" for c in sid):
        raise ValueError("Invalid account identifier")
    return sid


def _restrict_temp(descriptor: int, temporary: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            [
                require_executable("icacls", windows_system=True),
                str(temporary),
                "/inheritance:r",
                "/grant:r",
                f"*{_windows_sid()}:(F)",
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
    else:
        os.fchmod(descriptor, 0o600)


def write_local_environment(root: Path, values: dict[str, str]) -> None:
    """Atomically replace an ignored store, restricting access before writing."""
    from ..core.helpers import atomic_write_bytes

    path = validate_store_path(root)
    content = format_dotenv(values).encode("utf-8")
    if len(content) > MAX_ENV_BYTES:
        raise VaultSpecError("Combined environment settings exceed the 64 KiB limit.")
    try:
        atomic_write_bytes(
            path, content, prepare_temp=_restrict_temp, temp_prefix=".env."
        )
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration) as exc:
        raise VaultSpecError(
            "Cannot securely write local environment settings.",
            hint=f"Permission setup or atomic replacement failed: {exc}",
        ) from None
    _read_cached.cache_clear()
