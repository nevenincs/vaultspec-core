"""Untrack managed provider artifacts and detect staged ones.

Covers the git-index bookkeeping side of install/upgrade (dropping managed
paths that were committed before they became ignored) and the pre-commit
``check-providers`` hook's staged-file scan against
:data:`PROVIDER_ARTIFACT_PATTERNS`.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .gitattributes import has_valid_block as _ga_has_valid_block
from .gitignore import managed_lock_candidates

logger = logging.getLogger(__name__)

__all__ = [
    "PROVIDER_ARTIFACT_PATTERNS",
    "check_staged_provider_artifacts",
]


def has_gitignore_block(gi_path: Path) -> bool:
    """Report whether *gi_path* carries exactly one well-formed managed block."""
    if not gi_path.exists():
        return False
    try:
        content = gi_path.read_text(encoding="utf-8")
        # ``.gitignore`` and ``.gitattributes`` share the same managed-block
        # marker text, so the generic detector applies to both.
        return _ga_has_valid_block(content.splitlines())
    except (OSError, UnicodeDecodeError):
        return False


def has_gitattributes_block(ga_path: Path) -> bool:
    """Report whether *ga_path* carries a well-formed managed block."""
    if not ga_path.exists():
        return False
    try:
        content = ga_path.read_text(encoding="utf-8")
        return _ga_has_valid_block(content.splitlines())
    except (OSError, UnicodeDecodeError):
        return False


def _is_git_repo(target: Path) -> bool:
    """Return ``True`` if *target* is inside a git repository.

    Detects both plain clones (``.git`` is a directory) and linked
    worktrees (``.git`` is a file pointing at the real gitdir).
    """
    return (target / ".git").exists()


# Paths under these prefixes are owned by vaultspec-core and may be
# untracked on install if they were historically committed.  Root-level
# files (CLAUDE.md, .mcp.json, .pre-commit-config.yaml, etc.) are excluded
# because operators may have legitimate reasons to commit them.
#
# Provider-scope directories (``.claude/``, ``.gemini/``, ``.agents/``,
# ``.codex/``) are included per ADR D1: "Each provider's scope directory
# recorded in the manifest, only for files that match the managed
# gitignore entries."  Concretely, ``get_recommended_entries`` emits
# these directories when the manifest records the provider as installed
# and the directory exists on disk; :func:`untrack_managed_paths` only
# acts on entries it receives, so a provider that was never installed
# cannot be accidentally untracked.
_UNTRACK_PREFIXES: tuple[str, ...] = (
    ".vaultspec/",
    ".claude/",
    ".gemini/",
    ".agents/",
    ".codex/",
)

# Advisory-lock sentinels we create ourselves are enumerated per workspace by
# :func:`~vaultspec_core.core.gitignore.managed_lock_paths` - the same
# derivation the managed-ignore policy consumes, so the ownership gate and the
# ignore block can never drift apart.  The set is deliberately path-exact (not
# basename-based) so that unrelated lockfiles (``uv.lock``, ``Cargo.lock``,
# ``bun.lock``, ``package-lock.json`` siblings, etc.) and look-alikes in
# subdirectories can never be untracked even if they reach the helper.


def untrack_managed_paths(target: Path, entries: list[str]) -> list[str]:
    """Stop tracking managed paths that were committed before they became ignored.

    Iterates *entries* and retains only those under :data:`_UNTRACK_PREFIXES`
    or those that are advisory-lock sentinels (``*.lock`` that vaultspec
    itself produces).  For each retained candidate, invokes
    ``git rm --cached --ignore-unmatch -- <path>``.  No-ops when the target
    is not a git repository.  Subprocess failures are logged and do not
    raise.

    Args:
        target: Workspace root directory.
        entries: Managed gitignore entries computed for *target*.

    Returns:
        List of paths that were actually untracked (best-effort; may be
        empty if git is unavailable or nothing was previously tracked).
    """
    if not _is_git_repo(target):
        return []

    owned_lock_sentinels = frozenset(managed_lock_candidates(target))

    candidates: list[str] = []
    for entry in entries:
        # Skip glob patterns; git rm --cached does not expand them on our behalf.
        if "*" in entry or "?" in entry:
            continue
        # Strip leading slash from anchored entries ("/foo.lock" -> "foo.lock").
        candidate = entry[1:] if entry.startswith("/") else entry
        if not candidate:
            continue
        # Only act on paths we own.  Two ownership gates:
        #   1. under a prefix in :data:`_UNTRACK_PREFIXES` (currently only
        #      ``.vaultspec/``);
        #   2. a sentinel path enumerated by ``managed_lock_candidates`` for
        #      this exact workspace.  The comparison is whole-path, so a
        #      look-alike such as ``docs/.gitignore.lock`` cannot match the
        #      root-level ``.gitignore.lock`` we own, and sibling lockfiles
        #      such as ``uv.lock`` or ``Cargo.lock`` are never eligible.
        stem = candidate.rstrip("/")
        owned = (
            any(stem == prefix.rstrip("/") for prefix in _UNTRACK_PREFIXES)
            or any(stem.startswith(prefix) for prefix in _UNTRACK_PREFIXES)
            or stem in owned_lock_sentinels
        )
        if not owned:
            continue
        candidates.append(candidate)

    if not candidates:
        return []

    # The candidate list comes from :func:`get_recommended_entries` and is
    # bounded by the number of managed prefixes we own (``.vaultspec/``,
    # ``.claude/``, ``.gemini/``, ``.agents/``, ``.codex/``, plus a handful
    # of root-level lock sentinels).  It is safe to splat onto the argv.
    try:
        ls_result = subprocess.run(
            ["git", "-C", str(target), "ls-files", "--", *candidates],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        logger.warning("git ls-files probe failed during install untrack: %s", exc)
        return []

    tracked = [line.strip() for line in ls_result.stdout.splitlines() if line.strip()]
    if not tracked:
        return []

    # Chunk ``git rm --cached`` calls so the argv stays well below
    # ``ARG_MAX`` (~32 KiB on Windows, much larger on Linux) even on
    # legacy repos with thousands of tracked managed files.  Chunking
    # is preferred over ``--pathspec-from-file=-`` because that flag
    # was introduced in git 2.26 (March 2020) and some CI runners
    # still carry older git (notably Ubuntu 18.04 LTS with git 2.17).
    # 200 paths at ~256 chars each ~= 50 KiB which could spill ARG_MAX on
    # Windows under edge conditions; 100 keeps us firmly inside the
    # budget.
    _chunk_size = 100
    actually_untracked: list[str] = []
    for chunk_start in range(0, len(tracked), _chunk_size):
        chunk = tracked[chunk_start : chunk_start + _chunk_size]
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(target),
                    "rm",
                    "--cached",
                    "--ignore-unmatch",
                    "--",
                    *chunk,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            OSError,
        ) as exc:
            logger.warning(
                "git rm --cached failed during install untrack (chunk %d-%d): %s",
                chunk_start,
                chunk_start + len(chunk),
                exc,
            )
            # Stop dispatching further chunks but preserve the partial
            # result so callers and operators see exactly which paths
            # were untracked before the failure.
            break
        actually_untracked.extend(chunk)

    for path in actually_untracked:
        logger.info("Untracked previously-committed managed path: %s", path)
    return actually_untracked


# Patterns that must never be committed.  Used by the
# check-provider-artifacts pre-commit hook.
PROVIDER_ARTIFACT_PATTERNS: tuple[str, ...] = (
    ".mcp.json",
    "providers.lock",
    "CLAUDE.md",
    "GEMINI.md",
    "AGENTS.md",
    ".claude/",
    ".gemini/",
    ".codex/",
    ".agents/",
    ".vaultspec/_snapshots/",
)


def check_staged_provider_artifacts(cwd: Path | None = None) -> list[str]:
    """Return staged file paths that match provider artifact patterns.

    Runs ``git diff --cached --name-only --diff-filter=ACMR`` and filters
    against :data:`PROVIDER_ARTIFACT_PATTERNS`.  The ``ACMR`` filter excludes
    staged deletions so remediation commits (``git rm --cached ...``) are
    not blocked by the hook that recommends them.

    Args:
        cwd: Directory to run ``git`` in.  Defaults to the caller's current
            working directory (pre-commit hook behaviour).  Tests pass an
            explicit path to avoid mutating global process state.
    """
    cmd = ["git"]
    if cwd is not None:
        cmd.extend(["-C", str(cwd)])
    cmd.extend(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    staged = result.stdout.strip().splitlines()
    violations: list[str] = []
    for path in staged:
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        for pattern in PROVIDER_ARTIFACT_PATTERNS:
            if pattern.endswith("/"):
                # Directory pattern: match any path segment exactly
                dirname = pattern.rstrip("/")
                if any(seg == dirname for seg in parts):
                    violations.append(path)
                    break
            elif normalized == pattern or parts[-1] == pattern:
                violations.append(path)
                break
    return violations
