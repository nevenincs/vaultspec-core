"""Manage Architecture Decision Records (ADRs) and their lifecycle relationships."""

from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path

from ..config import get_config
from ..vaultcore import (
    DocumentMetadata,
    parse_vault_metadata,
    refresh_modified_stamp,
)
from . import types as _t
from .enums import AdrStatus
from .exceptions import ResourceNotFoundError, VaultSpecError
from .helpers import atomic_write

logger = logging.getLogger(__name__)

#: Frontmatter keys ``adr_supersede`` understands and rebuilds explicitly; any other
#: key in an ADR's frontmatter block is preserved verbatim, in place, by
#: :func:`_preserve_unknown_frontmatter_keys`.
_KNOWN_ADR_FRONTMATTER_KEYS = frozenset(
    {
        "tags",
        "date",
        "related",
        "feature",
        "supersedes",
        "superseded_by",
        "derived_from",
        "promoted_to",
        "archived",
    }
)

_ADR_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_ADR_STATUS_HEADING_RE = re.compile(
    r"^(#\s+.*\|\s+\(\*\*status:\*\*\s+`?)([^`)]+)(`?\)\s*)$"
)


def _preserve_unknown_frontmatter_keys(yaml_block: str) -> list[str]:
    """Return the raw lines of frontmatter keys not covered by known ADR fields.

    Args:
        yaml_block: The original YAML frontmatter block (without the ``---``
            fences).

    Returns:
        The lines belonging to unrecognized top-level keys, verbatim, so the
        frontmatter rebuild in :func:`_rewrite_adr_frontmatter` can append them
        unchanged.
    """
    preserved: list[str] = []
    in_unknown_key = False
    for line in yaml_block.split("\n"):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip()
            in_unknown_key = key not in _KNOWN_ADR_FRONTMATTER_KEYS
            if in_unknown_key:
                preserved.append(line)
            continue
        if stripped.startswith("-"):
            if in_unknown_key:
                preserved.append(line)
            continue
        if in_unknown_key and stripped:
            preserved.append(line)
        in_unknown_key = False
    return preserved


def _rebuild_frontmatter_lines(meta: DocumentMetadata, yaml_block: str) -> list[str]:
    """Rebuild an ADR's frontmatter lines from its known metadata fields.

    Args:
        meta: The parsed (and possibly mutated) document metadata.
        yaml_block: The original YAML frontmatter block, used to recover any
            keys not modeled by :class:`DocumentMetadata`.

    Returns:
        The rebuilt frontmatter lines, opening ``---`` fence included and
        closing fence omitted (the caller appends body content before closing
        the block).
    """
    fm_lines = ["---"]
    if meta.tags:
        fm_lines.append("tags:")
        for tag in meta.tags:
            fm_lines.append(f'  - "{tag}"')
    if meta.date:
        fm_lines.append(f"date: '{meta.date}'")
    if meta.related:
        fm_lines.append("related:")
        for link in meta.related:
            fm_lines.append(f'  - "{link}"')
    if meta.supersedes:
        fm_lines.append("supersedes:")
        for stem in meta.supersedes:
            fm_lines.append(f"  - '{stem}'")
    if meta.superseded_by:
        fm_lines.append(f"superseded_by: '{meta.superseded_by}'")
    if meta.derived_from:
        fm_lines.append("derived_from:")
        for stem in meta.derived_from:
            fm_lines.append(f"  - '{stem}'")
    if meta.promoted_to:
        fm_lines.append("promoted_to:")
        for rule in meta.promoted_to:
            fm_lines.append(f"  - '{rule}'")
    if meta.archived:
        fm_lines.append(f"archived: '{meta.archived}'")

    fm_lines.extend(_preserve_unknown_frontmatter_keys(yaml_block))
    return fm_lines


def _rewrite_adr_frontmatter(
    normalized: str, meta: DocumentMetadata, source_file: Path
) -> str:
    """Rebuild an ADR document's frontmatter block, preserving body and unknown keys.

    Args:
        normalized: The document text, normalized to ``\\n`` line endings.
        meta: The parsed (and possibly mutated) document metadata to render.
        source_file: The document's path, used only for the parse-error message.

    Returns:
        The rebuilt document text (still ``\\n``-normalized).

    Raises:
        VaultSpecError: If ``normalized`` has no parseable frontmatter block.
    """
    match = _ADR_FRONTMATTER_RE.match(normalized.lstrip())
    if not match:
        raise VaultSpecError(f"Could not parse frontmatter of ADR '{source_file}'.")
    yaml_block, body_content = match.group(1), match.group(2)
    leading = normalized[: len(normalized) - len(normalized.lstrip())]

    fm_lines = _rebuild_frontmatter_lines(meta, yaml_block)
    fm_lines.append("---")
    if body_content:
        fm_lines.append(body_content)

    return leading + "\n".join(fm_lines)


def _supersede_status_heading(normalized: str) -> str:
    """Rewrite the first ADR H1 status token to ``superseded``.

    Args:
        normalized: The document text, normalized to ``\\n`` line endings.

    Returns:
        The document text with its status token rewritten, or unchanged if no
        H1 heading matches the expected ``|  (**status:** \\`...\\`)`` shape.
    """
    lines_list = normalized.split("\n")
    for i, line in enumerate(lines_list):
        if not line.startswith("# "):
            continue
        match = _ADR_STATUS_HEADING_RE.match(line)
        if not match:
            continue
        lines_list[i] = f"{match.group(1)}{AdrStatus.SUPERSEDED.value}{match.group(3)}"
        break
    return "\n".join(lines_list)


def adr_supersede(
    old_adr: str,
    by_new_adr: str,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Supersede an old ADR with a new ADR.

    Writes ``superseded_by: '<new-adr-stem>'`` on the old ADR's frontmatter and
    adds ``'<old-adr-stem>'`` to the new ADR's ``supersedes`` frontmatter list.
    Optionally rewrites the old ADR's H1 status token from `accepted` to `superseded`.

    Args:
        old_adr: The old ADR stem or filename (e.g. '2026-05-17-cli-memory-lifecycle').
        by_new_adr: The new ADR stem or filename.
        dry_run: If True, preview the actions without modifying the files.

    Returns:
        A tuple of (old_adr_path, new_adr_path).
    """
    target_dir = _t.get_context().target_dir
    docs_dir = get_config().docs_dir

    old_stem = old_adr[:-3] if old_adr.endswith(".md") else old_adr
    new_stem = by_new_adr[:-3] if by_new_adr.endswith(".md") else by_new_adr

    old_file = target_dir / docs_dir / "adr" / f"{old_stem}.md"
    new_file = target_dir / docs_dir / "adr" / f"{new_stem}.md"

    if not old_file.exists():
        raise ResourceNotFoundError(
            f"Old ADR document '{docs_dir}/adr/{old_stem}.md' not found."
        )

    if not new_file.exists():
        raise ResourceNotFoundError(
            f"New ADR document '{docs_dir}/adr/{new_stem}.md' not found."
        )

    # 1. Update the old ADR
    old_bytes = old_file.read_bytes()
    old_content = old_bytes.decode("utf-8")
    old_newline = "\r\n" if "\r\n" in old_content else "\n"
    old_normalized = old_content.replace("\r\n", "\n")

    old_meta, _ = parse_vault_metadata(old_normalized)
    old_meta.superseded_by = new_stem

    old_normalized_body = _supersede_status_heading(old_normalized)
    final_old_content = _rewrite_adr_frontmatter(
        old_normalized_body, old_meta, old_file
    )
    if old_newline == "\r\n":
        final_old_content = final_old_content.replace("\n", "\r\n")

    # 2. Update the new ADR
    new_bytes = new_file.read_bytes()
    new_content = new_bytes.decode("utf-8")
    new_newline = "\r\n" if "\r\n" in new_content else "\n"
    new_normalized = new_content.replace("\r\n", "\n")

    new_meta, _ = parse_vault_metadata(new_normalized)
    if old_stem not in new_meta.supersedes:
        new_meta.supersedes.append(old_stem)

    final_new_content = _rewrite_adr_frontmatter(new_normalized, new_meta, new_file)
    if new_newline == "\r\n":
        final_new_content = final_new_content.replace("\n", "\r\n")

    # Vault-orientation ADR (decision D3): supersession is a lifecycle
    # mutation, so refresh the modified stamp on both the superseded and
    # the superseding document. Applied to the final rendered text (after
    # any CRLF reapplication) so the helper sees the exact bytes about to
    # be written; it preserves the document's line-ending convention.
    today = _dt.date.today()
    final_old_content = refresh_modified_stamp(final_old_content, today)
    final_new_content = refresh_modified_stamp(final_new_content, today)

    if not dry_run:
        atomic_write(old_file, final_old_content)
        atomic_write(new_file, final_new_content)

    return old_file, new_file
