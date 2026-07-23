"""Managed-block support for ``.gitignore`` files."""

from __future__ import annotations

import logging
from pathlib import Path

from .enums import ManagedState, Tool
from .helpers import advisory_lock, atomic_write_bytes

logger = logging.getLogger(__name__)

MARKER_BEGIN = "# >>> vaultspec-managed (do not edit this block) >>>"
MARKER_END = "# <<< vaultspec-managed <<<"

# Internal state that must ALWAYS be ignored if gitignore is managed.
# `.vaultspec/` is an install artefact in any consumer project; the
# canonical source content lives bundled in `src/vaultspec_core/builtins/`.
DEFAULT_ENTRIES = [".vaultspec/"]

# Root-level files vaultspec locks via ``advisory_lock`` irrespective of which
# providers are enrolled.  Provider-native configurations are NOT listed here;
# they are derived from ``resolve_mcp_targets`` so that enrolling a new provider
# cannot silently reintroduce an uncovered sentinel.
_ROOT_LOCK_SUBJECTS: tuple[str, ...] = (
    ".gitignore",
    ".mcp.json",
    ".pre-commit-config.yaml",
)


def _provider_lock_subjects(target: Path) -> tuple[Path, ...]:
    """Return the provider-native MCP configuration paths for *target*.

    Derived from :func:`~vaultspec_core.core.mcps.resolve_mcp_targets`, the same
    source of truth the lock-taking code consumes, so the managed-ignore policy
    tracks provider enrolment automatically.

    Returns an empty tuple when the targets cannot be resolved: a misconfigured
    or unenrolled provider must never break ``.gitignore`` generation.

    Args:
        target: Workspace root directory.
    """
    from . import types as _t

    try:
        ctx = _t.get_context()
        # ``resolve_mcp_targets`` re-initialises the process-wide workspace
        # context when asked for a different root.  Computing ignore entries is
        # a read-only query, so consult it only for the ambient workspace and
        # skip provider derivation otherwise rather than mutate global state.
        if ctx.target_dir.resolve() != target.resolve():
            return ()

        from .mcps import resolve_mcp_targets

        return tuple(t.path for t in resolve_mcp_targets(target_dir=target))
    except Exception:
        return ()


def _lock_subjects(target: Path) -> tuple[Path, ...]:
    """Return every file vaultspec takes an advisory lock on inside *target*."""
    subjects = {target / name for name in _ROOT_LOCK_SUBJECTS}
    subjects.update(_provider_lock_subjects(target))
    # User-scope provider stores (``~/.codex/config.toml``) resolve outside the
    # workspace and are not covered by a repository ``.gitignore``.
    return tuple(sorted(s for s in subjects if _is_within(s, target)))


def _is_within(path: Path, root: Path) -> bool:
    """Return ``True`` when *path* is contained by *root*."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sentinel_for(subject: Path) -> Path:
    """Return the advisory-lock sentinel ``advisory_lock`` derives for *subject*."""
    return subject.with_name(subject.name + ".lock")


def managed_lock_candidates(target: Path) -> tuple[str, ...]:
    """Return every advisory-lock sentinel path Core can own inside *target*.

    :func:`~vaultspec_core.core.helpers.advisory_lock` always derives a sibling
    ``<path>.lock`` sentinel and never removes it, so every file vaultspec locks
    leaves a per-machine artefact behind.  This is the single derivation both the
    managed-ignore policy and the untracking ownership gate consume, so the two
    can never drift apart.

    Unlike :func:`managed_lock_paths` this reports the full ownership surface
    regardless of whether the locked subject currently exists: a sentinel
    committed before its subject was retired is still ours to disown.

    Args:
        target: Workspace root directory.

    Returns:
        Sorted root-relative POSIX paths, e.g. ``".codex/config.toml.lock"``.
    """
    return tuple(
        sorted(
            _sentinel_for(subject).relative_to(target).as_posix()
            for subject in _lock_subjects(target)
        )
    )


def managed_lock_paths(target: Path) -> tuple[str, ...]:
    """Return the sentinels Core owns whose locked subject exists on disk.

    The ignore block lists only these, mirroring the long-standing rule that a
    companion-less lock path is not emitted.

    Args:
        target: Workspace root directory.

    Returns:
        Sorted root-relative POSIX paths, e.g. ``".codex/config.toml.lock"``.
    """
    return tuple(
        sorted(
            _sentinel_for(subject).relative_to(target).as_posix()
            for subject in _lock_subjects(target)
            if subject.is_file()
        )
    )


def prune_orphaned_lock_sentinels(target: Path) -> list[str]:
    """Delete Core-owned lock sentinels whose subject file no longer exists.

    A sentinel outlives its subject when a managed file is retired - most
    notably ``.pre-commit-config.yaml.lock`` after a checkout migrates to
    ``prek.toml``.  Because :func:`managed_lock_paths` only covers sentinels with
    a live subject, an orphan would otherwise remain permanently visible in
    ``git status``.

    Only empty sentinels are removed: ``advisory_lock`` never writes to the file,
    so a non-empty ``.lock`` sibling belongs to someone else and is left alone.

    Args:
        target: Workspace root directory.

    Returns:
        Root-relative POSIX paths of the sentinels actually removed.
    """
    removed: list[str] = []
    for subject in _lock_subjects(target):
        if subject.exists():
            continue
        sentinel = _sentinel_for(subject)
        try:
            if not sentinel.is_file() or sentinel.stat().st_size != 0:
                continue
            sentinel.unlink()
        except OSError:
            # The sentinel may be held by a concurrent process; leaving it in
            # place is always safe.
            continue
        removed.append(sentinel.relative_to(target).as_posix())
        logger.debug("Removed orphaned lock sentinel %s", sentinel)
    return removed


def get_recommended_entries(target: Path) -> list[str]:
    """Return the runtime-only gitignore entries for the managed block.

    Per the ``cli-spec-gitignore`` ADR the spec layer is team-shared:
    authored content under ``.vaultspec/`` (rules, skills, agents, system),
    the synthesised ``CLAUDE.md``, ``.mcp.json``, and the generated provider
    directories are committed to git so a teammate cloning the project
    inherits its authoritative policy. The managed block therefore ignores
    only genuine per-machine runtime by-products: the snapshot directory,
    advisory-lock sentinels, the install manifest, and the vault's local
    caches. Authored content is never added here.

    Args:
        target: Workspace root directory.
    """
    entries: set[str] = set()

    try:
        # Internal state that must ALWAYS be ignored if the framework
        # exists. The snapshot directory, advisory-lock sentinels, the
        # install manifest (providers.json), and the MCP ownership ledger
        # (mcp-ownership.json, absolute machine paths) are per-machine
        # state, never authored content. Everything else under .vaultspec/
        # (rules, skills, agents, system) is team-shared and is not listed
        # here.
        framework_installed = (target / ".vaultspec").is_dir()
        if framework_installed:
            entries.add(".vaultspec/_snapshots/")
            entries.add(".vaultspec/*.lock")
            entries.add(".vaultspec/providers.json")
            entries.add(".vaultspec/mcp-ownership.json")
        if (target / ".vault").is_dir():
            entries.add(".vault/.obsidian/")
            entries.add(".vault/.trash/")
            entries.add(".vault/data/")
            entries.add(".vault/logs/")

        # Advisory-lock sentinels produced by ``advisory_lock`` when vaultspec
        # locks a managed file during install or sync.  Enumerated from
        # :func:`managed_lock_paths` rather than via a broad ``*.lock`` glob
        # because legitimately-tracked lockfiles (uv.lock, bun.lock,
        # Cargo.lock, ...) must not be ignored.  Each entry is anchored with a
        # leading slash so it matches only at its exact location.  Only emitted
        # when vaultspec itself is installed, to avoid polluting the
        # recommended set on bare workspaces.
        if framework_installed:
            for lock_path in managed_lock_paths(target):
                entries.add(f"/{lock_path}")

    except Exception:
        # Fallback for very early bootstrap or corruption
        pass

    return sorted(entries)


# Managed-block entries the cli-spec-gitignore reversal removed. Their
# presence marks a block still on the pre-reversal team-hidden policy.
_PRE_REVERSAL_MARKERS = (".vaultspec/", ".mcp.json")


def block_is_pre_reversal(target: Path) -> bool:
    """Return ``True`` when ``.gitignore``'s managed block predates the reversal.

    A managed block that still lists ``.vaultspec/`` wholesale or
    ``.mcp.json`` is on the pre-``cli-spec-gitignore`` policy that hid
    team-shared content from teammates. Callers use this to decide
    whether an upgrade should surface the sharing-policy statement.

    Args:
        target: Workspace root directory containing ``.gitignore``.
    """
    gi_path = target / ".gitignore"
    if not gi_path.exists():
        return False
    try:
        lines = gi_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    begins, ends = _find_markers(lines)
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return False
    block = {line.strip() for line in lines[begins[0] + 1 : ends[0]]}
    return any(marker in block for marker in _PRE_REVERSAL_MARKERS)


def _collect_provider_artifacts(
    path: Path, tool: ManagedState | Tool
) -> tuple[list[Path], list[Path]]:
    """Return ``(directories, files)`` managed by a single provider.

    Args:
        path: Workspace root directory.
        tool: :class:`~vaultspec_core.core.enums.Tool` to inspect.

    Returns:
        A two-tuple of ``(directory_paths, file_paths)`` owned by *tool*.
    """
    from . import types as _t
    from .enums import DirName, FileName

    if not isinstance(tool, Tool):
        return [], []

    cfg = _t.get_context().tool_configs.get(tool)
    dirs: list[Path] = []
    files: list[Path] = []

    if tool == Tool.CLAUDE:
        dirs.append(path / DirName.CLAUDE.value)
        files.append(path / FileName.CLAUDE.value)
    elif tool == Tool.GEMINI:
        dirs.append(path / DirName.GEMINI.value)
        files.append(path / FileName.GEMINI.value)
    elif tool == Tool.ANTIGRAVITY:
        dirs.append(path / DirName.ANTIGRAVITY.value)
        files.append(path / FileName.GEMINI.value)
    elif tool == Tool.CODEX:
        dirs.append(path / DirName.CODEX.value)
        files.append(path / FileName.AGENTS.value)

    if cfg and cfg.native_config_file and cfg.native_config_file.parent not in dirs:
        dirs.append(cfg.native_config_file.parent)

    # The provider-native MCP config (e.g. .agents/mcp_config.json) is a managed
    # artefact written by mcp_sync; protect it explicitly so per-provider
    # uninstall and gitignore reconciliation own it rather than relying on it
    # happening to sit under a removed provider directory.
    if cfg and cfg.mcp_config_file and cfg.mcp_config_file not in files:
        files.append(cfg.mcp_config_file)

    return dirs, files


def _detect_line_ending(raw: bytes) -> str:
    """Return ``"\\r\\n"`` if CRLF is dominant in *raw*, else ``"\\n"``."""
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _find_markers(lines: list[str]) -> tuple[list[int], list[int]]:
    """Return ``(begin_indices, end_indices)`` of the managed block markers."""
    begins: list[int] = []
    ends: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == MARKER_BEGIN:
            begins.append(i)
        elif stripped == MARKER_END:
            ends.append(i)
    return begins, ends


def _collapse_double_blanks(lines: list[str]) -> list[str]:
    """Collapse consecutive blank lines into a single blank line."""
    result: list[str] = []
    prev_blank = False
    for line in lines:
        blank = line.strip() == ""
        if blank and prev_blank:
            continue
        result.append(line)
        prev_blank = blank
    return result


def ensure_gitignore_block(
    target: Path,
    entries: list[str],
    *,
    state: ManagedState = ManagedState.PRESENT,
) -> bool:
    """Add or remove a vaultspec-managed block inside ``.gitignore``.

    The block is delimited by :data:`MARKER_BEGIN` / :data:`MARKER_END` and
    contains the caller-supplied *entries*.  The function is idempotent - it
    returns ``False`` when the file already matches the desired state.

    Args:
        target: Workspace root directory containing ``.gitignore``.
        entries: Gitignore patterns to manage inside the block.
        state: Desired state (PRESENT or ABSENT).

    Returns:
        ``True`` if the file was modified, ``False`` otherwise.
    """
    gi_path = target / ".gitignore"
    if not gi_path.exists():
        return False

    with advisory_lock(gi_path):
        raw = gi_path.read_bytes()
        eol = _detect_line_ending(raw)

        # Preserve BOM if present.
        bom = b""
        text = raw
        if raw.startswith(b"\xef\xbb\xbf"):
            bom = b"\xef\xbb\xbf"
            text = raw[3:]

        content = text.decode("utf-8")
        lines = content.splitlines()
        begins, ends = _find_markers(lines)

        if state == ManagedState.ABSENT:
            return _remove_block(gi_path, lines, begins, ends, eol, bom)
        return _add_block(gi_path, lines, begins, ends, entries, eol, bom)


def _add_block(
    gi_path: Path,
    lines: list[str],
    begins: list[int],
    ends: list[int],
    entries: list[str],
    eol: str,
    bom: bytes,
) -> bool:
    """Add or update the vaultspec-managed block in-place.

    Replaces exactly one valid block in its original position. For multiple
    or mismatched markers, purges them and appends a fresh block to the end.
    """
    new_block = [MARKER_BEGIN, *entries, MARKER_END]

    # If we have exactly one block, update it in-place.
    if len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        replaced = lines[: begins[0]] + new_block + lines[ends[0] + 1 :]
        if replaced == lines:
            return False
        result = eol.join(replaced) + eol
        _write(gi_path, result, bom)
        return True

    # Otherwise, clean up all existing markers and content between them.
    # Identify and remove all valid pairs (markers + content)
    # Simple pairing: find ENDs that come after a BEGIN
    ranges: list[tuple[int, int]] = []
    stack: list[int] = []
    marker_indices = sorted(
        [(i, "B") for i in begins] + [(i, "E") for i in ends], key=lambda x: x[0]
    )
    for idx, type in marker_indices:
        if type == "B":
            stack.append(idx)
        elif type == "E" and stack:
            start = stack.pop()
            ranges.append((start, idx))

    if ranges:
        # Remove ranges from end to start to avoid index shifts.
        for start, end in sorted(ranges, key=lambda x: x[0], reverse=True):
            lines[start : end + 1] = []

        # If any orphaned markers remain (unpaired), remove them individually.
        begins_left, ends_left = _find_markers(lines)
        to_pop = sorted(begins_left + ends_left, reverse=True)
        for idx in to_pop:
            lines.pop(idx)
    else:
        # No valid pairs? Just strip any markers found.
        to_pop = sorted(begins + ends, reverse=True)
        for idx in to_pop:
            lines.pop(idx)

    # Strip trailing blank lines, add separator, append block.
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines.append("")
    lines.extend(new_block)

    result = eol.join(lines) + eol
    _write(gi_path, result, bom)
    return True


def _remove_block(
    gi_path: Path,
    lines: list[str],
    begins: list[int],
    ends: list[int],
    eol: str,
    bom: bytes,
) -> bool:
    if not begins and not ends:
        return False

    # If we have exactly one block, remove it and its contents.
    if len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        lines = lines[: begins[0]] + lines[ends[0] + 1 :]
    else:
        # For multiple or mismatched markers, clean up paired blocks first.
        ranges: list[tuple[int, int]] = []
        stack: list[int] = []
        marker_indices = sorted(
            [(i, "B") for i in begins] + [(i, "E") for i in ends], key=lambda x: x[0]
        )
        for idx, type in marker_indices:
            if type == "B":
                stack.append(idx)
            elif type == "E" and stack:
                start = stack.pop()
                ranges.append((start, idx))

        if ranges:
            for start, end in sorted(ranges, key=lambda x: x[0], reverse=True):
                lines[start : end + 1] = []

            # Clean up any remaining orphaned markers.
            begins_left, ends_left = _find_markers(lines)
            to_pop = sorted(begins_left + ends_left, reverse=True)
            for idx in to_pop:
                lines.pop(idx)
        else:
            # Just strip any markers found.
            to_pop = sorted(begins + ends, reverse=True)
            for idx in to_pop:
                lines.pop(idx)

    lines = _collapse_double_blanks(lines)
    result = eol.join(lines) + eol
    _write(gi_path, result, bom)
    return True


def _write(gi_path: Path, content: str, bom: bytes) -> None:
    """Write *content* to *gi_path* atomically, restoring BOM if originally present.

    Uses a temporary file and rename to avoid partial writes.  Always
    writes in binary mode to preserve the caller-chosen line endings.
    Using text-mode would double ``\\r`` on Windows when the content
    already contains ``\\r\\n``.
    """
    atomic_write_bytes(gi_path, bom + content.encode("utf-8"))
