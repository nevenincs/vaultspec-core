"""Manage Architecture Decision Records (ADRs) and their lifecycle relationships."""

from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path

from ..vaultcore import VaultConstants, parse_vault_metadata, refresh_modified_stamp
from . import types as _t
from .enums import AdrStatus
from .exceptions import ResourceNotFoundError, VaultSpecError
from .helpers import atomic_write

logger = logging.getLogger(__name__)


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
    docs_dir = VaultConstants._get_docs_dir()

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

    # Rewrite H1 status line: replace accepted/proposed/etc with superseded
    # Pattern: # `tag` adr: `Title` | (**status:** `accepted`) or similar
    # Using the regex: r"^(#\s+.*\|\s+\(\*\*status:\*\*\s+`?)([^`)]+)(`?\)\s*)$"
    lines_list = old_normalized.split("\n")
    for i, line in enumerate(lines_list):
        if line.startswith("# "):
            match = re.match(
                r"^(#\s+.*\|\s+\(\*\*status:\*\*\s+`?)([^`)]+)(`?\)\s*)$", line
            )
            if match:
                lines_list[i] = (
                    f"{match.group(1)}{AdrStatus.SUPERSEDED.value}{match.group(3)}"
                )
                break

    old_normalized_body = "\n".join(lines_list)
    match = re.match(
        r"^---\s*\n(.*?)\n---\s*\n?(.*)$", old_normalized_body.lstrip(), re.DOTALL
    )
    if not match:
        raise VaultSpecError(f"Could not parse frontmatter of old ADR '{old_file}'.")
    old_yaml_block = match.group(1)
    old_body_content = match.group(2)
    old_leading = old_normalized_body[
        : len(old_normalized_body) - len(old_normalized_body.lstrip())
    ]

    # Rebuild frontmatter keys
    old_fm_lines = ["---"]
    if old_meta.tags:
        old_fm_lines.append("tags:")
        for tag in old_meta.tags:
            old_fm_lines.append(f'  - "{tag}"')
    if old_meta.date:
        old_fm_lines.append(f"date: '{old_meta.date}'")
    if old_meta.related:
        old_fm_lines.append("related:")
        for link in old_meta.related:
            old_fm_lines.append(f'  - "{link}"')
    if old_meta.supersedes:
        old_fm_lines.append("supersedes:")
        for stem in old_meta.supersedes:
            old_fm_lines.append(f"  - '{stem}'")
    if old_meta.superseded_by:
        old_fm_lines.append(f"superseded_by: '{old_meta.superseded_by}'")
    if old_meta.derived_from:
        old_fm_lines.append("derived_from:")
        for stem in old_meta.derived_from:
            old_fm_lines.append(f"  - '{stem}'")
    if old_meta.promoted_to:
        old_fm_lines.append("promoted_to:")
        for rule in old_meta.promoted_to:
            old_fm_lines.append(f"  - '{rule}'")
    if old_meta.archived:
        old_fm_lines.append(f"archived: '{old_meta.archived}'")

    # Preserve unknown keys
    known_keys = {
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
    in_unknown_key = False
    for line in old_yaml_block.split("\n"):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip()
            in_unknown_key = key not in known_keys
            if in_unknown_key:
                old_fm_lines.append(line)
        elif stripped.startswith("-"):
            if in_unknown_key:
                old_fm_lines.append(line)
        else:
            if in_unknown_key and stripped:
                old_fm_lines.append(line)
            in_unknown_key = False

    old_fm_lines.append("---")
    if old_body_content:
        old_fm_lines.append(old_body_content)

    final_old_content = old_leading + "\n".join(old_fm_lines)
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

    match = re.match(
        r"^---\s*\n(.*?)\n---\s*\n?(.*)$", new_normalized.lstrip(), re.DOTALL
    )
    if not match:
        raise VaultSpecError(f"Could not parse frontmatter of new ADR '{new_file}'.")
    new_yaml_block = match.group(1)
    new_body_content = match.group(2)
    new_leading = new_normalized[: len(new_normalized) - len(new_normalized.lstrip())]

    new_fm_lines = ["---"]
    if new_meta.tags:
        new_fm_lines.append("tags:")
        for tag in new_meta.tags:
            new_fm_lines.append(f'  - "{tag}"')
    if new_meta.date:
        new_fm_lines.append(f"date: '{new_meta.date}'")
    if new_meta.related:
        new_fm_lines.append("related:")
        for link in new_meta.related:
            new_fm_lines.append(f'  - "{link}"')
    if new_meta.supersedes:
        new_fm_lines.append("supersedes:")
        for stem in new_meta.supersedes:
            new_fm_lines.append(f"  - '{stem}'")
    if new_meta.superseded_by:
        new_fm_lines.append(f"superseded_by: '{new_meta.superseded_by}'")
    if new_meta.derived_from:
        new_fm_lines.append("derived_from:")
        for stem in new_meta.derived_from:
            new_fm_lines.append(f"  - '{stem}'")
    if new_meta.promoted_to:
        new_fm_lines.append("promoted_to:")
        for rule in new_meta.promoted_to:
            new_fm_lines.append(f"  - '{rule}'")
    if new_meta.archived:
        new_fm_lines.append(f"archived: '{new_meta.archived}'")

    # Preserve unknown keys
    in_unknown_key = False
    for line in new_yaml_block.split("\n"):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip()
            in_unknown_key = key not in known_keys
            if in_unknown_key:
                new_fm_lines.append(line)
        elif stripped.startswith("-"):
            if in_unknown_key:
                new_fm_lines.append(line)
        else:
            if in_unknown_key and stripped:
                new_fm_lines.append(line)
            in_unknown_key = False

    new_fm_lines.append("---")
    if new_body_content:
        new_fm_lines.append(new_body_content)

    final_new_content = new_leading + "\n".join(new_fm_lines)
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
