"""Shared filesystem, YAML, and process helpers for vaultspec runtime code.

The functions here support multiple implementation layers rather than a single
feature area. They provide the low-level operations used by resource
management, config generation, syncing, and hook execution.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


_thread_locks: dict[str, threading.Lock] = {}
_thread_locks_guard = threading.Lock()


def _get_thread_lock(key: str) -> threading.Lock:
    """Return a per-path threading lock, creating one if needed."""
    with _thread_locks_guard:
        if key not in _thread_locks:
            _thread_locks[key] = threading.Lock()
        return _thread_locks[key]


@contextmanager
def advisory_lock(path: Path) -> Iterator[None]:
    """Advisory file lock for serializing concurrent read-modify-write cycles.

    Serializes threads within the same process via a per-path
    :class:`threading.Lock`, then serializes across processes via an
    OS-level file lock (``fcntl.flock`` on Unix, ``msvcrt.locking``
    on Windows).  Both layers block until acquired.

    Args:
        path: The file being protected.  A sibling ``.lock`` file is
            created next to it and used as the lock target.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")

    # Only create the lock file's parent if it already exists.  Creating
    # it unconditionally would cause side-effects (e.g. directory creation
    # during dry-run operations where the target doesn't exist yet).
    # When the parent doesn't exist, no concurrent writer can race on
    # this file, so it is safe to skip locking entirely.
    if not lock_path.parent.exists():
        yield
        return

    resolved_key = str(lock_path.resolve())
    tlock = _get_thread_lock(resolved_key)
    tlock.acquire()
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    finally:
        tlock.release()


def _yaml_load(text: str) -> dict[str, Any]:
    """Parse a YAML string and return a dict, defaulting to empty dict on empty input.

    Args:
        text: A YAML-formatted string to parse.

    Returns:
        Parsed key-value mapping, or an empty dict if *text* is empty or null.
    """
    return yaml.safe_load(text) or {}


class _LiteralStr(str):
    """Marker type for strings that should use YAML literal block scalar."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.ScalarNode:
    """Represent a _LiteralStr value using YAML literal block scalar style (``|``).

    Args:
        dumper: The PyYAML Dumper instance performing serialization.
        data: The string value to represent with literal block style.

    Returns:
        A YAML ScalarNode configured with ``|`` block scalar style.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


_literal_representer_registered = False
_literal_representer_lock = threading.Lock()


def _ensure_literal_representer() -> None:
    """Register :func:`_literal_representer` with PyYAML on first use.

    Performing this registration lazily (rather than at module import)
    prevents a partially broken or missing PyYAML install from taking the
    framework down during ``import vaultspec_core.core``: every CLI entry
    point and downstream package depends on that import succeeding so
    ``vaultspec-core spec doctor`` and ``vaultspec-core install --upgrade`` can
    diagnose and repair a
    degraded environment.  See GitHub issue #85.

    Uses double-checked locking so that two threads calling
    :func:`_yaml_dump` concurrently for the first time both observe a
    registered representer without either of them entering the critical
    section twice.  ``yaml.add_representer`` mutates a class-level
    ``Dumper.yaml_representers`` dict, and although the GIL serialises
    each individual dict assignment in CPython, the lock is the right
    contract for non-CPython runtimes and free-threaded builds.
    """
    global _literal_representer_registered
    if _literal_representer_registered:
        return
    with _literal_representer_lock:
        if _literal_representer_registered:
            return
        yaml.add_representer(_LiteralStr, _literal_representer)
        _literal_representer_registered = True


def _yaml_dump(data: dict[str, Any]) -> str:
    """Serialize a dict to YAML, using literal block style for multi-line values.

    Args:
        data: Key-value mapping to serialize.

    Returns:
        YAML string representation with multi-line string values rendered as
        literal block scalars (``|``).
    """
    _ensure_literal_representer()
    prepared = {}
    for k, v in data.items():
        if isinstance(v, str) and "\n" in v:
            prepared[k] = _LiteralStr(v)
        else:
            prepared[k] = v
    return yaml.dump(
        prepared, default_flow_style=False, allow_unicode=True, sort_keys=False
    ).rstrip("\n")


def build_file(frontmatter: dict[str, Any], body: str) -> str:
    """Assemble a Markdown file with YAML frontmatter.

    Args:
        frontmatter: Key-value pairs to serialize as the YAML front matter block.
        body: Markdown body text to place after the closing ``---`` delimiter.

    Returns:
        A string of the form ``---\\n<yaml>\\n---\\n\\n<body>``.
    """
    fm_str = _yaml_dump(frontmatter)
    return f"---\n{fm_str}\n---\n\n{body}"


def ensure_dir(path: Path) -> None:
    """Create *path* and all intermediate parents if they do not already exist.

    Refuses to create directories inside symlink targets to prevent
    accidental writes through symbolic links.

    Args:
        path: Directory path to create.
    """
    if path.exists() and path.is_symlink():
        logger.warning("Refusing to create directory inside symlink target: %s", path)
        return
    path.mkdir(parents=True, exist_ok=True)


def _rmtree_robust(path: Path) -> None:
    """Remove a directory tree, handling symlinks and Windows read-only files.

    Symlinks are unlinked directly rather than followed. On Windows, a
    read-only attribute on a child file is cleared before retrying the
    removal so that NTFS-protected trees can be deleted.

    Args:
        path: Directory (or symlink to directory) to remove.
    """
    if path.is_symlink():
        path.unlink()
        return

    def _on_error(
        func: Callable[..., object],
        fpath: str,
        exc_info: tuple[type, BaseException, object],
    ) -> None:
        if os.name == "nt":
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        else:
            raise exc_info[1]

    shutil.rmtree(path, onerror=_on_error)


def _open_atomic_temp(path: Path) -> tuple[int, Path, tuple[int, int]]:
    """Exclusively create an unpredictable regular file beside *path*."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for optional_flag in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW"):
        flags |= getattr(os, optional_flag, 0)

    for _attempt in range(128):
        candidate = path.with_name(f".vs-write-{secrets.token_hex(16)}.tmp")
        try:
            fd = os.open(candidate, flags, 0o666)
        except FileExistsError:
            continue
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            os.close(fd)
            raise OSError(
                f"Atomic write temporary path is not a regular file: {candidate}"
            )
        return fd, candidate, (opened.st_dev, opened.st_ino)
    raise FileExistsError(
        f"Could not allocate an atomic write temporary file for {path}"
    )


def _unlink_owned_temp(path: Path, identity: tuple[int, int]) -> None:
    """Remove *path* only while it is still the temporary file we created."""
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == identity:
        path.unlink()


def _assert_owned_temp(path: Path, identity: tuple[int, int]) -> None:
    """Fail unless *path* still names the temporary regular file we opened."""
    try:
        current = path.lstat()
    except FileNotFoundError as exc:
        raise OSError(f"Atomic write temporary file disappeared: {path}") from exc
    if (
        not stat.S_ISREG(current.st_mode)
        or (
            current.st_dev,
            current.st_ino,
        )
        != identity
    ):
        raise OSError(f"Atomic write temporary file identity changed: {path}")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace *path* from an exclusively created sibling file."""
    destination_mode: int | None = None
    try:
        destination = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISREG(destination.st_mode):
            destination_mode = stat.S_IMODE(destination.st_mode)

    fd, tmp, identity = _open_atomic_temp(path)
    owns_tmp = True
    try:
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            if written == 0:
                raise OSError(f"Atomic write made no progress for {path}")
            view = view[written:]
        if destination_mode is not None and hasattr(os, "fchmod"):
            os.fchmod(fd, destination_mode)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        _assert_owned_temp(tmp, identity)
        os.replace(tmp, path)
        owns_tmp = False
    finally:
        if fd >= 0:
            os.close(fd)
        if owns_tmp:
            _unlink_owned_temp(tmp, identity)


def atomic_write(path: Path, content: str) -> None:
    """Write UTF-8 content through :func:`atomic_write_bytes`.

    Args:
        path: Destination file path to write.
        content: Text content to write, encoded as UTF-8.
    """
    try:
        atomic_write_bytes(path, content.encode("utf-8"))
    except Exception as exc:
        logger.error("atomic_write failed for %s: %s", path, exc)
        raise


def _launch_editor(editor: str, file_path: str) -> None:
    """Launch editor, handling Windows .cmd/.bat wrappers.

    Args:
        editor: Editor command string (may include flags, e.g. ``"code --wait"``).
        file_path: Absolute path to the file to open in the editor.
    """
    parts = editor.split()
    resolved = shutil.which(parts[0]) or parts[0]
    if sys.platform == "win32" and resolved.lower().endswith((".cmd", ".bat")):
        result = subprocess.run(["cmd.exe", "/c", resolved, *parts[1:], file_path])
    else:
        result = subprocess.run([resolved, *parts[1:], file_path])
    if result.returncode != 0:
        logger.warning("Editor exited with code %d", result.returncode)


def collect_md_resources(
    src_dir: Path,
    warnings: list[str] | None = None,
) -> dict[str, tuple[Path, dict[str, Any], str]]:
    """Collect all ``*.md`` resource definitions from *src_dir*.

    Reads and parses frontmatter from every Markdown file found directly in
    *src_dir*, returning a mapping of filename -> (path, metadata, body).

    Args:
        src_dir: Directory to scan for ``*.md`` files.
        warnings: Optional list to append parse-error messages to, so callers
            can propagate them into :class:`~vaultspec_core.core.types.SyncResult`.

    Returns:
        Ordered mapping of filename to ``(source_path, frontmatter_dict, body_text)``
        tuples; empty if *src_dir* does not exist.
    """
    from ..vaultcore import parse_frontmatter

    sources: dict[str, tuple[Path, dict[str, Any], str]] = {}
    if not src_dir.exists():
        return sources
    for f in sorted(src_dir.glob("**/*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            rel_path = f.relative_to(src_dir).as_posix()
            sources[rel_path] = (f, meta, body)
        except Exception as e:
            logger.error("Failed to read/parse %s: %s", f, e)
            if warnings is not None:
                warnings.append(f"Failed to read/parse {f}: {e}")
    return sources


def kill_process_tree(pid: int) -> None:
    """Forcefully terminate a process and all its children.

    On Windows, uses ``taskkill /f /t /pid``. On other platforms, uses
    ``pkill -P``.

    Args:
        pid: Root process ID to kill.
    """
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/f", "/t", "/pid", str(pid)], capture_output=True)
    else:
        # Simple fallback for Unix; in production use psutil if available
        subprocess.run(["pkill", "-9", "-P", str(pid)], capture_output=True)
        subprocess.run(["kill", "-9", str(pid)], capture_output=True)


def package_version() -> str:
    """Return the running ``vaultspec-core`` package version string.

    Wraps :func:`importlib.metadata.version` and falls back to
    ``"unknown"`` so callers still complete when running from a
    development tree without installed metadata. The fallback parses
    via :func:`parse_version_tuple` to the empty tuple, which sorts
    strictly below any real version - safe for "is the workspace below
    the running version?" comparisons.
    """
    try:
        from importlib.metadata import version

        return version("vaultspec-core")
    except Exception:
        return "unknown"


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a PEP 440 version string into a comparable integer tuple.

    Strips any pre/post/dev suffixes and splits on dots. An empty string
    parses to ``()`` so the empty-manifest case sorts strictly below any
    real version.

    Args:
        version_str: Version string like ``"0.1.4"`` or ``"1.2.3rc1"``.

    Returns:
        Tuple of integer version segments.

    Raises:
        ValueError: If the cleaned string contains a non-integer segment
            (e.g. ``"1.x"``).
    """
    import re

    if not version_str:
        return ()
    clean = re.split(r"[^0-9.]", version_str)[0].rstrip(".")
    if not clean:
        return ()
    return tuple(int(x) for x in clean.split("."))
