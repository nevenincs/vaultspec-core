"""Scan source-file content for references to the project's own vault records.

The one-way vault reference boundary holds that ``.vault/`` and
``.vaultspec/`` are removable development scaffolding: vault documents cite
code by locator, and tracked source-file content never references the
project's own development records. This checker is the boundary's opt-in
mechanical instrument. It enumerates the vault's document stems (authored
records and generated feature indexes), walks the source tree outside the
vault, the harness, the provider directories, and common caches, and reports
every source file whose text contains one of those stems - as a plain
substring or in wiki-link form - as a ``WARNING``.

The scan is advisory by construction: warnings never affect the exit code,
nothing is mutated, and the checker is deliberately not a member of
``run_all_checks`` (the ``check all`` pipeline stays vault-scoped). Needles
are stems only - never bare Step ids or the literal ``.vault`` path string -
so vault-domain codebases that legitimately construct vault paths as product
functionality do not false-positive.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["check_code_boundary"]

# Directories never scanned: the vault and harness themselves, provider
# directories (generated projections of the harness), VCS internals, and
# common build/cache trees whose contents are derived, not authored.
_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".vault",
        ".vaultspec",
        ".claude",
        ".gemini",
        ".agents",
        ".codex",
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)

# Files larger than this are skipped: generated bundles and data blobs, not
# authored source. The cap keeps the walk's worst case bounded.
_MAX_FILE_BYTES = 1_000_000


def _collect_needles(root_dir: Path, feature: str | None) -> set[str]:
    """Return the vault's document stems to scan for.

    Authored records contribute their filename stem (date-prefixed,
    high-precision); generated feature indexes contribute their
    ``<feature>.index`` stem. With *feature* set, only documents carrying
    that feature tag (by stem convention: the feature segment between the
    date prefix and the type suffix) plus that feature's index are needled.

    Args:
        root_dir: Project root directory.
        feature: Optional feature tag (without ``#``) restricting the
            needle set to one feature's documents.
    """
    from ...config import get_config

    needles: set[str] = set()
    docs_dir = root_dir / get_config().docs_dir
    if not docs_dir.exists():
        return needles

    for path in docs_dir.rglob("*.md"):
        if ".obsidian" in path.parts or "_archive" in path.parts:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        stem = path.name[: -len(".md")]
        if feature is not None and feature not in stem:
            continue
        needles.add(stem)

    return needles


def _iter_source_files(root_dir: Path):
    """Yield candidate source files under *root_dir*, honoring exclusions."""
    stack = [root_dir]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name in _EXCLUDED_DIR_NAMES:
                    continue
                stack.append(entry)
                continue
            if entry.is_file():
                yield entry


def check_code_boundary(
    root_dir: Path,
    *,
    feature: str | None = None,
) -> CheckResult:
    """Report source files that reference the project's own vault records.

    Enumerates the needle stems from ``.vault/`` (optionally restricted to
    one feature), walks every non-excluded file under *root_dir*, skips
    files above the size cap or that do not decode as UTF-8, and emits one
    ``WARNING`` diagnostic per file naming the matched stems. Read-only and
    advisory: ``supports_fix`` is ``False`` and warnings never fail the
    command.

    Args:
        root_dir: Project root directory.
        feature: Optional feature tag (without ``#``) restricting the
            needles to that feature's documents.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"code-boundary"``.
    """
    result = CheckResult(check_name="code-boundary", supports_fix=False)

    needles = _collect_needles(root_dir, feature)
    if not needles:
        return result

    for path in _iter_source_files(root_dir):
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

        matched = sorted(stem for stem in needles if stem in text)
        if not matched:
            continue

        rel_path = path.relative_to(root_dir)
        listed = ", ".join(matched[:3])
        if len(matched) > 3:
            listed += f", and {len(matched) - 3} more"
        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=(
                    f"Source file references vault record(s): {listed}. "
                    "Code must stand alone: move the linkage into the vault "
                    "document (which cites code by locator) or an opt-in git "
                    "commit trailer."
                ),
                severity=Severity.WARNING,
            )
        )

    return result
