"""Manage Architecture Decision Records (ADRs) and their lifecycle relationships."""

from __future__ import annotations

import logging
import re
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from ..config import get_config
from ..vaultcore import (
    DocumentMetadata,
    parse_vault_metadata,
    refresh_modified_stamp,
    vault_today,
)
from ..vaultcore.markdown import iter_headings
from ..vaultcore.parser import split_frontmatter
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

#: The status marker that ends an ADR's H1, ``| (**status:** `accepted`)``,
#: with the backtick quoting optional so a bare token is still read (and can
#: be reported and repaired) rather than mistaken for no status at all.
_ADR_STATUS_MARKER_RE = re.compile(
    r"\|\s+\(\*\*status:\*\*\s+(?P<open>`?)(?P<token>[^`)]+?)(?P<close>`?)\)\s*$"
)


@dataclass(frozen=True)
class AdrStatusMarker:
    """The status token on an ADR's title heading, located for reading or rewriting.

    Attributes:
        line: The title heading's 1-based line within the scanned body.
        token: The raw status token, stripped, not yet validated against
            :class:`~vaultspec_core.core.enums.AdrStatus`.
        quoted: Whether the token is wrapped in backticks on both sides.
        start: Column where the token begins, opening backtick included.
        end: Column after the token ends, closing backtick included.
    """

    line: int
    token: str
    quoted: bool
    start: int
    end: int

    def rewrite(self, heading_line: str, token: str, *, quoted: bool) -> str:
        """Return *heading_line* with this marker's token replaced by *token*."""
        value = f"`{token}`" if quoted else token
        return heading_line[: self.start] + value + heading_line[self.end :]


def adr_status_marker(body: str) -> AdrStatusMarker | None:
    """Locate the status marker on the first H1 of an ADR *body*.

    Decision authority lives on the title line alone: a title without a
    marker means "no parseable status", never a deferral to some later
    heading - an example H1 in a code sample included - that happens to
    carry one.

    Args:
        body: The ADR body, without frontmatter.

    Returns:
        The marker, or ``None`` when the body has no H1 or its first H1
        carries no status marker.
    """
    title = next((h for h in iter_headings(body) if h.level == 1), None)
    if title is None:
        return None
    heading_line = body.split("\n")[title.line - 1]
    match = _ADR_STATUS_MARKER_RE.search(heading_line)
    if match is None:
        return None
    return AdrStatusMarker(
        line=title.line,
        token=match.group("token").strip(),
        quoted=bool(match.group("open")) and bool(match.group("close")),
        start=match.start("open"),
        end=match.end("close"),
    )


def rewrite_adr_status(
    document: str, token: str, *, quoted: bool | None = None
) -> str | None:
    """Return the full ADR *document* with its status token replaced.

    Every byte outside the token is preserved, frontmatter included.

    Args:
        document: The full ADR text, frontmatter included, ``\\n`` line
            endings.
        token: The status value to write.
        quoted: Whether to wrap *token* in backticks; ``None`` keeps the
            existing marker's quoting.

    Returns:
        The rewritten document, or ``None`` when its body carries no status
        marker to rewrite.
    """
    _yaml_block, body = split_frontmatter(document)
    marker = adr_status_marker(body)
    if marker is None:
        return None
    lines = body.split("\n")
    lines[marker.line - 1] = marker.rewrite(
        lines[marker.line - 1],
        token,
        quoted=marker.quoted if quoted is None else quoted,
    )
    # split_frontmatter only ever removes a prefix, so the body is the
    # document's tail and everything before it is kept verbatim.
    return document[: len(document) - len(body)] + "\n".join(lines)


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
    from ..vaultcore.edit_engine import document_write_lock

    target_dir = _t.get_context().target_dir
    docs_dir = get_config().docs_dir

    old_stem = old_adr[:-3] if old_adr.endswith(".md") else old_adr
    new_stem = by_new_adr[:-3] if by_new_adr.endswith(".md") else by_new_adr

    if any(
        Path(stem).name != stem or "\\" in stem or "/" in stem
        for stem in (old_stem, new_stem)
    ):
        raise VaultSpecError("ADR names must be document stems, not paths.")

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

    if old_file.resolve() == new_file.resolve():
        raise VaultSpecError("An ADR cannot supersede itself.")

    with ExitStack() as locks:
        for path in sorted((old_file, new_file)):
            locks.enter_context(document_write_lock(path, target_dir))
        return _apply_supersession(old_file, new_file, dry_run=dry_run)


def _apply_supersession(
    old_file: Path, new_file: Path, *, dry_run: bool
) -> tuple[Path, Path]:
    """Validate and render both records while holding their document locks."""
    old_stem, new_stem = old_file.stem, new_file.stem
    # Validate both records before rendering or writing either transition.
    new_content = new_file.read_text(encoding="utf-8")
    new_meta, new_body = parse_vault_metadata(new_content)
    old_meta, old_body = parse_vault_metadata(old_file.read_text(encoding="utf-8"))
    if adr_status_from_body(new_body) != AdrStatus.ACCEPTED or new_meta.superseded_by:
        raise VaultSpecError("The successor ADR must be accepted before supersession.")
    if old_meta.superseded_by and old_meta.superseded_by != new_stem:
        raise VaultSpecError("The old ADR already has a different successor.")
    old_status = adr_status_from_body(old_body)
    replay = old_status == AdrStatus.SUPERSEDED and old_meta.superseded_by == new_stem
    if old_status != AdrStatus.ACCEPTED and not replay:
        raise VaultSpecError(
            "The old ADR must be accepted or already superseded by this successor."
        )
    _reject_ancestor_cycle(old_file, old_meta.supersedes, new_stem)
    if replay and old_stem in new_meta.supersedes:
        return old_file, new_file

    # 1. Update the old ADR
    old_bytes = old_file.read_bytes()
    old_content = old_bytes.decode("utf-8")
    old_newline = "\r\n" if "\r\n" in old_content else "\n"
    old_normalized = old_content.replace("\r\n", "\n")

    old_meta, _ = parse_vault_metadata(old_normalized)
    old_meta.superseded_by = new_stem

    old_normalized_body = (
        rewrite_adr_status(old_normalized, AdrStatus.SUPERSEDED.value) or old_normalized
    )
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

    # Stamp the rendered bytes so both attestations preserve their newline convention.
    today = vault_today()
    final_old_content = refresh_modified_stamp(final_old_content, today)
    final_new_content = refresh_modified_stamp(final_new_content, today)

    if not dry_run:
        atomic_write(old_file, final_old_content)
        atomic_write(new_file, final_new_content)

    return old_file, new_file


def adr_status_from_body(body: str) -> AdrStatus | None:
    """Read decision authority from the first H1, never a later example heading."""
    marker = adr_status_marker(body)
    return AdrStatus.from_token(marker.token) if marker is not None else None


def _reject_ancestor_cycle(
    old_file: Path, ancestors: list[str], successor: str
) -> None:
    """Reject a successor already present in the predecessor's recorded ancestry."""
    pending = list(ancestors)
    visited = {old_file.stem}
    while pending:
        stem = pending.pop()
        if stem == successor:
            raise VaultSpecError("Supersession would create a cycle.")
        if stem in visited:
            continue
        visited.add(stem)
        if Path(stem).name != stem or "\\" in stem or "/" in stem:
            raise VaultSpecError("Invalid document stem in supersession ancestry.")
        path = old_file.parent / f"{stem}.md"
        if path.is_file():
            metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
            pending.extend(metadata.supersedes)
