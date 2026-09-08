"""Resolve user-supplied paths to wiki-link format and validate dependencies.

Handles the many shapes callers might use to reference an existing vault
document - absolute paths, relative paths, filenames with or without ``.md``,
and bare stems - and normalises them to the canonical ``[[stem]]`` wiki-link
format used in ``related:`` frontmatter fields.

Also provides :func:`validate_feature_dependencies` which enforces the
structural dependency at create time: execution records require a plan.
Decision coverage and evidence are assessed through explicit document links.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vaultspec_core.core.exceptions import VaultSpecError

from .models import DocType

__all__ = ["resolve_related_inputs", "validate_feature_dependencies"]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class RelatedResolutionError(VaultSpecError):
    """One or more user-supplied related paths could not be resolved."""

    def __init__(self, failures: list[str]) -> None:
        self.failures = failures
        super().__init__(
            f"Could not resolve related document(s): {'; '.join(failures)}"
        )


def _build_stem_index(root_dir: Path) -> dict[str, Path]:
    """Build a mapping of stem -> path for every vault document.

    Args:
        root_dir: Project root containing the docs directory.

    Returns:
        Dict mapping document stem (lowercase) to its absolute path.
    """
    from .scanner import scan_vault

    index: dict[str, Path] = {}
    for doc_path in scan_vault(root_dir):
        index[doc_path.stem.lower()] = doc_path
    return index


def resolve_related_inputs(
    inputs: list[str],
    root_dir: Path,
) -> list[str]:
    """Resolve a list of user-supplied document references to ``[[wiki-link]]`` strings.

    Accepts any of the following input forms for each entry:

    - Absolute path (``/home/user/project/.vault/adr/2026-03-01-feat-adr.md``)
    - Relative path (``.vault/adr/2026-03-01-feat-adr.md``)
    - Filename with extension (``2026-03-01-feat-adr.md``)
    - Stem without extension (``2026-03-01-feat-adr``)
    - Already-formatted wiki-link (``[[2026-03-01-feat-adr]]``)

    Each input is resolved against the vault document index. If any input
    cannot be matched, a :class:`RelatedResolutionError` is raised with all
    failures listed.

    Args:
        inputs: List of user-supplied strings referencing vault documents.
        root_dir: Project root directory.

    Returns:
        List of ``[[stem]]`` formatted wiki-link strings, deduplicated in
        input order.

    Raises:
        RelatedResolutionError: When one or more inputs cannot be resolved.
    """
    if not inputs:
        return []

    stem_index = _build_stem_index(root_dir)
    resolved: list[str] = []
    seen: set[str] = set()
    failures: list[str] = []

    for raw in inputs:
        stem = _resolve_single(raw, root_dir, stem_index)
        if stem is None:
            failures.append(raw)
        elif stem not in seen:
            seen.add(stem)
            resolved.append(f"[[{stem}]]")

    if failures:
        raise RelatedResolutionError(failures)

    return resolved


def _resolve_single(
    raw: str,
    root_dir: Path,
    stem_index: dict[str, Path],
) -> str | None:
    """Try to resolve a single input string to a document stem.

    Args:
        raw: User-supplied reference string.
        root_dir: Project root directory.
        stem_index: Pre-built mapping of lowercase stems to paths.

    Returns:
        The canonical stem string, or ``None`` if unresolvable.
    """
    cleaned = raw.strip()
    if not cleaned:
        return None

    # Already a wiki-link: [[stem]] or [[stem|display]]
    if cleaned.startswith("[[") and cleaned.endswith("]]"):
        inner = cleaned[2:-2]
        # Handle [[stem|display]] form
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        inner = inner.strip()
        if inner.endswith(".md"):
            inner = inner[:-3]
        match = stem_index.get(inner.lower())
        return match.stem if match is not None else None

    # Strip .md extension if present
    if cleaned.endswith(".md"):
        cleaned = cleaned[:-3]

    for key in _candidate_keys(cleaned, root_dir):
        match = stem_index.get(key)
        if match is not None:
            return match.stem

    return None


def _candidate_keys(cleaned: str, root_dir: Path) -> Iterator[str]:
    """Yield the stem-index lookup keys for one reference, in priority order.

    Args:
        cleaned: The trimmed reference with any ``.md`` extension removed.
        root_dir: Project root directory, the base for relative paths.

    Yields:
        Lowercase stem keys: the bare stem first (the most common case),
        then the stem of the reference read as a path, then its final
        component.
    """
    import pathlib

    # Try as bare stem first (most common case)
    yield cleaned.lower()

    # Try as a path (absolute or relative)
    try:
        candidate = pathlib.Path(cleaned)
        # If it looks like it has directory components, resolve it
        if len(candidate.parts) > 1:
            if candidate.is_absolute():
                yield candidate.stem.lower()
            else:
                # Resolve relative to root_dir
                yield (root_dir / candidate).resolve().stem.lower()
    except (OSError, ValueError):
        pass

    # Try matching just the final component as a stem
    try:
        final = pathlib.Path(cleaned).name
        if final.endswith(".md"):
            final = final[:-3]
        yield final.lower()
    except (OSError, ValueError):
        pass


def validate_feature_dependencies(
    root_dir: Path,
    doc_type: DocType,
    feature: str,
) -> list[str]:
    """Check that prerequisite documents exist for a feature before creating a new one.

    A plan can be decision-free or reuse decisions across features. This feature-only
    check cannot judge semantic coverage or evidence links; the schema checker does
    that against the authored records. Execution still requires a plan.

    Args:
        root_dir: Project root directory.
        doc_type: The type of document about to be created.
        feature: Feature tag (without ``#``).

    Returns:
        Diagnostic strings prefixed with ``ERROR:`` for missing prerequisites.
    """
    from .query import scan_all

    if doc_type != DocType.EXEC:
        return []
    if any(
        doc.feature == feature and doc.doc_type == "plan" for doc in scan_all(root_dir)
    ):
        return []
    return [
        f"ERROR: Cannot create exec for feature '{feature}' - "
        "no plan document exists. Create a plan first."
    ]
