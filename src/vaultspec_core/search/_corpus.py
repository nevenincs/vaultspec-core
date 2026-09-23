"""The vault as hosted search reads it: records, summary cards and excerpt blocks.

Search reads the records from disk on every query, through the same vault
graph and listing every other surface uses, so there is no index to go stale
and a filter means exactly what it means to ``find``. The explicit filters
(record type, feature, date) are applied here, in code, before any text can
reach a model: the model never sees a record the caller excluded.

Each record is seen two ways.

**Summary card.** The first stage ranks every record from a card: its title,
the opening of its first prose paragraph, and its distinctive section
headings. Headings a record type's body schema requires (``Findings``,
``Constraints``, ``Steps`` and the like) appear in every record of that type,
so they say nothing about this one and are left out; the list comes from the
body-schema registry that validates those sections, so a new schema version
changes both at once. Inline code and emphasis markers are dropped from card
text, which leaves an ADR's status marker reading ``| (status: accepted)``.
Cards are bounded, so a stage-one request's size grows with the record count
alone.

**Blocks.** The second stage reads a shortlisted record in full, as the
fence-aware paragraph blocks of :mod:`vaultspec_core.vaultcore.markdown`. A
block is a verbatim slice of the body, and the body is a run of whole lines
of the file, so a block's lines map to file lines by one offset: the line the
body starts on. Returned excerpts are these blocks, never model text, and
their line ranges address the file a caller opens. The blocks are cut from
one read of the file's bytes, and the blob id is hashed from the same bytes,
so an edit made while a search runs cannot leave the id naming one version
and the line ranges another.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from functools import cache
from typing import TYPE_CHECKING, Final

from ..core.windowing import clip_text
from ..vaultcore.blob_hash import git_blob_oid
from ..vaultcore.body_schema import BODY_SCHEMA_REGISTRY
from ..vaultcore.markdown import (
    HTML_COMMENT_OPEN,
    LineRole,
    iter_headings,
    line_roles,
    paragraph_blocks,
)
from ..vaultcore.parser import split_frontmatter
from ..vaultcore.query_listing import docs_from_graph
from ._questions import RECORD_GROUPS

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    from ..vaultcore.markdown import Block
    from ..vaultcore.models import DocType

__all__ = [
    "CARD_SECTIONS",
    "LEAD_CHARS",
    "SEARCHABLE_TYPES",
    "SECTION_BYTES",
    "TITLE_BYTES",
    "Record",
    "RecordVersion",
    "card_title",
    "load_records",
    "read_version",
    "readable",
    "summary_card",
    "template_headings",
]

logger = logging.getLogger(__name__)

#: The record types search ranks: every type some stage-one group covers.
#: Generated feature indexes are absent, since they only list other records.
SEARCHABLE_TYPES: Final = frozenset(
    doc_type for group in RECORD_GROUPS for doc_type in group
)

#: UTF-8 bytes of a title, on a card and on a hit. Titles are short by
#: convention; the bound only keeps one malformed heading from inflating a
#: stage-one request or a reply.
TITLE_BYTES: Final = 240

#: Characters of the opening paragraph a card carries.
LEAD_CHARS: Final = 240

#: Distinctive headings a card carries, and the UTF-8 bytes kept of each
#: heading, on a card and in an excerpt's section path.
CARD_SECTIONS: Final = 10
SECTION_BYTES: Final = 90

#: Heading levels a card lists. Level one is the title, and below level three
#: headings name details too fine to summarise a record.
_CARD_LEVELS: Final = frozenset({2, 3})

#: Inline markup dropped from card text: code spans and strong emphasis.
_MARKUP: Final = re.compile(r"\*\*|`")

#: Opening characters of a paragraph that is not prose: a table row or a
#: comment left by a template.
_NOT_PROSE: Final = ("|", HTML_COMMENT_OPEN)


@dataclass(frozen=True)
class Record:
    """One searchable vault record, read from disk for this query.

    Attributes:
        name: The file stem.
        path: The absolute file path.
        rel_path: The path relative to the workspace root, POSIX form; unique
            per record, so it also serves as the record's identity.
        doc_type: The record type.
        feature: The feature tag without ``#``; empty when the record has none.
        date: The frontmatter date, or the filename date; empty when neither.
        title: The H1 text with its inline markdown, or the stem when the
            record has no title.
        body: The text after the frontmatter, as whole lines of the file.
        body_line: The 1-based file line the body starts on.
    """

    name: str
    path: Path
    rel_path: str
    doc_type: DocType
    feature: str
    date: str
    title: str
    body: str
    body_line: int


def _relative(path: Path, root: Path) -> str:
    """Return *path* relative to *root* in POSIX form."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        # A graph restored from its cache carries the paths it was built
        # with, which may spell the same root differently.
        return path.resolve().relative_to(root.resolve()).as_posix()


def load_records(
    root: Path,
    *,
    doc_types: Collection[DocType] | None = None,
    feature: str | None = None,
    date: str | None = None,
) -> list[Record]:
    """Read the searchable records of the vault at *root* that pass the filters.

    The listing is the canonical graph-backed one, so unreadable files,
    phantom link targets and generated indexes never become records.

    Args:
        root: The workspace root.
        doc_types: Keep only these record types; ``None`` keeps every
            searchable type.
        feature: Keep only records of this feature (``#`` optional).
        date: Keep only records with this exact date (``YYYY-MM-DD``).

    Returns:
        The records in path order.
    """
    from ..graph import VaultGraph

    # Selected from the enum set, so a caller's plain type strings still
    # yield enum members.
    wanted = (
        SEARCHABLE_TYPES
        if doc_types is None
        else frozenset(t for t in SEARCHABLE_TYPES if t in doc_types)
    )
    if not wanted:
        return []
    by_value = {doc_type.value: doc_type for doc_type in wanted}
    graph = VaultGraph(root)
    graph.ensure_raw_texts()
    titles = {
        node.path: node.title
        for node in graph.nodes.values()
        if node.path is not None and not node.phantom
    }
    records: list[Record] = []
    for doc in docs_from_graph(graph, feature=feature, date=date):
        doc_type = by_value.get(doc.doc_type)
        raw = graph.raw_texts.get(doc.path)
        if doc_type is None or raw is None:
            continue
        split = split_frontmatter(raw[0])
        records.append(
            Record(
                name=doc.name,
                path=doc.path,
                rel_path=_relative(doc.path, root),
                doc_type=doc_type,
                feature=doc.feature or "",
                date=doc.date or "",
                title=titles.get(doc.path) or doc.name,
                body=split.body,
                body_line=split.body_line,
            )
        )
    records.sort(key=lambda record: record.rel_path)
    return records


# ---------------------------------------------------------------- cards


def readable(text: str) -> str:
    """Return *text* without code-span and emphasis markers, on one line.

    Args:
        text: Markdown text.

    Returns:
        The text with backticks and ``**`` removed and every whitespace run
        collapsed to one space.
    """
    return " ".join(_MARKUP.sub("", text).split())


@cache
def template_headings(doc_type: DocType) -> frozenset[str]:
    """Return every section heading some body schema requires of *doc_type*.

    Args:
        doc_type: The record type.

    Returns:
        The required section titles across every registered schema version,
        for full and summary records alike.
    """
    return frozenset(
        title
        for schema in BODY_SCHEMA_REGISTRY.values()
        for summary in (False, True)
        for title in schema.required_sections(doc_type, summary=summary)
    )


def card_title(record: Record) -> str:
    """Return the title a model reads for *record*.

    Args:
        record: The record.

    Returns:
        The readable title, bounded to :data:`TITLE_BYTES`.
    """
    return clip_text(readable(record.title), TITLE_BYTES)


def _is_prose(block: Block) -> bool:
    first = block.text.split("\n", 1)[0]
    if first.lstrip().startswith(_NOT_PROSE):
        return False
    return line_roles([first])[0] is not LineRole.FENCE_OPEN


def _lead(body: str) -> str:
    """Return the start of the first prose paragraph of *body*."""
    # One block per paragraph: nothing merges below a zero minimum, and
    # nothing splits under a bound the whole body fits.
    for block in paragraph_blocks(body, max_chars=max(len(body), 1), min_chars=0):
        if _is_prose(block):
            text = readable(block.text)
            if text:
                return text[:LEAD_CHARS]
    return ""


def _sections(record: Record) -> list[str]:
    """Return *record*'s distinctive headings, in document order."""
    template = template_headings(record.doc_type)
    sections: list[str] = []
    for heading in iter_headings(record.body):
        if heading.level not in _CARD_LEVELS:
            continue
        text = readable(heading.text)
        if text and text not in template:
            sections.append(clip_text(text, SECTION_BYTES))
            if len(sections) == CARD_SECTIONS:
                break
    return sections


def summary_card(record: Record) -> dict[str, object]:
    """Build the card the first stage ranks *record* by.

    The card is plain record text; a caller placing it in a request applies
    the transport's sanitising map to it.

    Args:
        record: The record.

    Returns:
        ``title``, then ``lead`` and ``sections`` when the record has any.
    """
    card: dict[str, object] = {"title": card_title(record)}
    lead = _lead(record.body)
    if lead:
        card["lead"] = lead
    sections = _sections(record)
    if sections:
        card["sections"] = sections
    return card


# ---------------------------------------------------------------- blocks


@dataclass(frozen=True)
class RecordVersion:
    """One version of a record's file: its blob id and the blocks cut from it.

    Attributes:
        blob_hash: The git blob id of the bytes the blocks were cut from.
        blocks: The body's paragraph blocks, each with ``line_start`` and
            ``line_end`` counted in the file. Each block's text is exactly
            the file's lines in that range, joined by ``\\n``.
    """

    blob_hash: str
    blocks: tuple[Block, ...]


def read_version(record: Record) -> RecordVersion | None:
    """Read *record*'s file once and cut its excerpt blocks from those bytes.

    The bytes are hashed and decoded exactly as the graph decodes a document,
    so the blob id and every block's line range describe one version of the
    file, whatever changed on disk since the records were listed.

    Args:
        record: The record.

    Returns:
        The version, or ``None`` when the file can no longer be read or is no
        longer UTF-8.
    """
    from ..graph.api import decode_document

    try:
        raw = record.path.read_bytes()
        text = decode_document(raw)
    except (OSError, UnicodeDecodeError):
        logger.debug("record file unreadable for its full read: %s", record.rel_path)
        return None
    split = split_frontmatter(text)
    offset = split.body_line - 1
    blocks = tuple(
        replace(
            block,
            line_start=block.line_start + offset,
            line_end=block.line_end + offset,
        )
        for block in paragraph_blocks(split.body)
    )
    return RecordVersion(blob_hash=git_blob_oid(raw), blocks=blocks)
