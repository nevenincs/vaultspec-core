"""The ADR corpus as cross-referencing reads it: headers, decision text, fingerprints.

Cross-referencing reads the ADR directory itself rather than building the
whole-vault graph. The question is about one record type, and a cold graph
build over a large vault reads every other type too: seconds to tens of
seconds, against well under a second for the ADR files alone. The read is
bounded by :data:`~vaultspec_core.crossref._questions.MAX_CORPUS`, so its cost
has a ceiling before any file is opened.

Each ADR is seen three ways.

**Header.** The feature, the title, the status from the title's marker, and a
lead: the first prose line of its Problem Statement. This is what an option in
the Choice stage shows, so it is bounded in characters.

**Decision state.** Decision and constraint sections come first, with every
other section retained. Long records share the character budget across
sections; clipping is reported, never mistaken for complete decision input.
A record without sections falls back to its whole body.

**Fingerprint.** The inline code spans of the body, normalised into the
concrete artifacts the decision governs: module and file paths, CLI verbs,
tool names, configuration variables. Two decisions that govern the same
artifact name it the same way, which prose words do not guarantee, so the
fingerprint is what finds a link a title never mentions.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Final

from ..config import get_config
from ..core.adr import adr_status_from_body
from ..graph.algorithms import extract_feature
from ..vaultcore.markdown import (
    HTML_COMMENT_RE,
    INLINE_CODE_RE,
    document_title,
    iter_headings,
    iter_sections,
)
from ..vaultcore.models import DocType
from ..vaultcore.parser import parse_vault_metadata
from ._models import CorpusTooLargeError
from ._questions import (
    DECISION_CHARS,
    DECISION_SECTIONS,
    FINGERPRINT_ENTRY_CHARS,
    LEAD_CHARS,
    MAX_CORPUS,
    TITLE_CHARS,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ..core.enums import AdrStatus

__all__ = [
    "AdrRecord",
    "CorpusTooLargeError",
    "adr_dir",
    "clip",
    "fingerprint",
    "load_adrs",
    "wiki_stem",
    "with_body",
]

logger = logging.getLogger(__name__)

#: A title heading's status marker, removed from the title an option shows.
_STATUS_SUFFIX_RE: Final = re.compile(r"\s*\|\s*\(\*\*status:\*\*.*$")

#: The ``feature`` adr: prefix every scaffolded ADR title carries.
_TITLE_PREFIX_RE: Final = re.compile(r"^`?[a-z0-9-]+`?\s+adr:\s*")

#: A vault record stem: never an artifact, it is a link.
_STEM_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}-")

#: Code spans that name no artifact: status tokens, record types, bare
#: numbers, booleans and all-caps words used as emphasis. An all-caps name with
#: an underscore is a configuration variable, which is an artifact.
_NOT_ARTIFACT_RE: Final = re.compile(
    r"^(?:true|false|none|null|yes|no|"
    r"proposed|accepted|rejected|superseded|deprecated|"
    r"adr|plan|research|audit|reference|exec|index|"
    r"[\d.,%x]+|[A-Z0-9]+)$"
)

#: A trailing call, line locator or line range on a code span.
_CALL_RE: Final = re.compile(r"\(.*\)$")
_LOCATOR_RE: Final = re.compile(r":\d+(?:-\d+)?$")

#: Shortest normalised span that can name an artifact.
_MIN_ARTIFACT_CHARS: Final = 3

#: Wiki-link brackets and an alias, as ``related:`` entries carry them.
_WIKI_RE: Final = re.compile(r"^\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]$")


@dataclass(frozen=True)
class AdrRecord:
    """One ADR as cross-referencing reads it.

    Attributes:
        stem: The file stem, which is also the record's link target.
        rel_path: The path relative to the workspace root, POSIX form.
        feature: The feature tag without ``#``; empty when it has none.
        title: The title without its feature prefix and status marker,
            bounded by :data:`~vaultspec_core.crossref._questions.TITLE_CHARS`.
        status: The status the title's marker declares, or ``None``.
        lead: The first prose line of the Problem Statement, bounded.
        decision: The decision state text, bounded.
        declared: The stems of the ADRs this record's ``related:`` names, in
            the order it names them.
        artifacts: How often each normalised artifact appears in the body.
        input_truncated: Whether the decision state lost text to its bound.
    """

    stem: str
    rel_path: str
    feature: str
    title: str
    status: AdrStatus | None
    lead: str
    decision: str
    declared: tuple[str, ...] = ()
    artifacts: Counter[str] = field(default_factory=Counter)
    input_truncated: bool = False

    def header(self) -> str:
        """The record as one line: ``[feature] title. lead``."""
        head = f"[{self.feature}] {self.title}" if self.feature else self.title
        return f"{head}. {self.lead}" if self.lead else head


def clip(text: str, limit: int) -> str:
    """Cut *text* to at most *limit* characters, at a word boundary where one falls.

    Args:
        text: The text to bound.
        limit: The most characters kept, the ellipsis included.

    Returns:
        *text* unchanged when it fits, else its leading words and ``…``.
    """
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip() + "\N{HORIZONTAL ELLIPSIS}"


def wiki_stem(link: str) -> str | None:
    """Return the stem a ``[[stem]]`` or ``[[stem|alias]]`` entry names."""
    match = _WIKI_RE.match(link.strip())
    return match.group(1).strip() if match else None


def _artifact(span: str) -> str | None:
    """Normalise one inline code span into an artifact name, or ``None``."""
    text = _LOCATOR_RE.sub("", _CALL_RE.sub("", span.strip()))
    text = text.strip().strip("./").lower()
    if len(text) < _MIN_ARTIFACT_CHARS or "\n" in text:
        return None
    if _STEM_RE.match(text) or _NOT_ARTIFACT_RE.match(span.strip()):
        return None
    if text.startswith("vaultspec-core "):
        # A CLI verb: the command path identifies it, its flags do not.
        words = [word for word in text.split() if not word.startswith("-")]
        text = " ".join(words[:4])
    return clip(text, FINGERPRINT_ENTRY_CHARS)


def fingerprint(body: str) -> Counter[str]:
    """Count the artifacts the inline code spans of *body* name.

    Args:
        body: A record body, without frontmatter.

    Returns:
        Each normalised artifact and how many spans named it.
    """
    prose = HTML_COMMENT_RE.sub("", body)
    found = (_artifact(match.group(2)) for match in INLINE_CODE_RE.finditer(prose))
    return Counter(name for name in found if name is not None)


def _plain(text: str) -> str:
    """Drop inline code backticks and emphasis markers from one line of text."""
    return " ".join(text.replace("`", "").replace("**", "").split())


def _title(body: str, stem: str) -> str:
    heading = document_title(body) or stem
    heading = _STATUS_SUFFIX_RE.sub("", heading)
    heading = _TITLE_PREFIX_RE.sub("", _plain(heading))
    return clip(heading.strip("` ") or stem, TITLE_CHARS)


def _decision(body: str) -> tuple[str, str, bool]:
    """Return bounded decision text, its lead, and whether text was clipped."""
    sections = list(iter_sections(body))
    problem = next(
        (s.body for s in sections if s.heading.text.lower() == "problem statement"),
        "",
    )
    first = next((line for line in problem.splitlines() if line.strip()), "")
    lead = clip(_plain(first), LEAD_CHARS)
    if not sections:
        return clip(body, DECISION_CHARS), lead, len(body) > DECISION_CHARS
    priorities = {name.lower(): rank for rank, name in enumerate(DECISION_SECTIONS)}
    ordered = sorted(
        sections, key=lambda s: priorities.get(s.heading.text.lower(), len(priorities))
    )
    parts = [f"## {s.heading.text}\n{s.body.strip()}" for s in ordered]
    title_lines = {h.line for h in iter_headings(body) if h.level == 1}
    preamble = "\n".join(
        line
        for number, line in enumerate(body.splitlines(), 1)
        if number < sections[0].heading.line and number not in title_lines
    ).strip()
    if preamble:
        parts.append(preamble)
    text = "\n\n".join(parts)
    if len(text) <= DECISION_CHARS:
        return text, lead, False
    # Reserve separators, then redistribute short sections' unused shares.
    # Pathological section counts still obey the hard bound and report clipping.
    remaining = DECISION_CHARS - 2 * (len(parts) - 1)
    if remaining < len(parts):
        return clip(text, DECISION_CHARS), lead, True
    allowances = [0] * len(parts)
    for offset, index in enumerate(
        sorted(range(len(parts)), key=lambda i: len(parts[i]))
    ):
        allowance = min(len(parts[index]), remaining // (len(parts) - offset))
        allowances[index] = allowance
        remaining -= allowance
    bounded = "\n\n".join(
        clip(part, size) for part, size in zip(parts, allowances, strict=True)
    )
    return bounded, lead, True


def adr_dir(root: Path) -> Path:
    """Return the directory the vault at *root* keeps its ADRs in."""
    return root / get_config().docs_dir / DocType.ADR.value


def with_body(record: AdrRecord, body: str) -> AdrRecord:
    """Project proposed body prose under an existing ADR's identity and links."""
    from ..core.enums import AdrStatus
    from ._models import InvalidSourceError

    prose = HTML_COMMENT_RE.sub("", body).strip()
    if not prose or prose.startswith("---"):
        raise InvalidSourceError(
            "a draft needs nonempty body prose without frontmatter"
        )
    decision, lead, truncated = _decision(prose)
    return replace(
        record,
        title=_title(prose, record.stem) if document_title(prose) else record.title,
        status=AdrStatus.PROPOSED,
        decision=decision,
        lead=lead,
        artifacts=fingerprint(prose),
        input_truncated=truncated,
    )


def _read(path: Path, root: Path) -> AdrRecord | None:
    """Read one ADR file, or ``None`` when it cannot be read as text."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.debug("crossref skipped unreadable ADR %s: %s", path.name, exc)
        return None
    metadata, body = parse_vault_metadata(text.replace("\r\n", "\n"))
    body = HTML_COMMENT_RE.sub("", body)
    decision, lead, input_truncated = _decision(body)
    declared = tuple(
        dict.fromkeys(
            stem
            for stem in (wiki_stem(link) for link in metadata.related)
            if stem is not None and stem != path.stem
        )
    )
    return AdrRecord(
        stem=path.stem,
        rel_path=path.relative_to(root).as_posix(),
        feature=extract_feature(set(metadata.tags)) or "",
        title=_title(body, path.stem),
        status=adr_status_from_body(body),
        lead=lead,
        decision=decision,
        declared=declared,
        artifacts=fingerprint(body),
        input_truncated=input_truncated,
    )


def load_adrs(root: Path) -> list[AdrRecord]:
    """Read every ADR of the vault at *root*, in stem order.

    Args:
        root: The workspace root.

    Returns:
        The readable ADRs. ``declared`` keeps only links to ADRs in this list.

    Raises:
        CorpusTooLargeError: If the ADR directory holds more than
            :data:`~vaultspec_core.crossref._questions.MAX_CORPUS` records;
            nothing is read then.
    """
    directory = adr_dir(root)
    if not directory.is_dir():
        return []
    paths = sorted(path for path in directory.glob("*.md") if path.is_file())
    if len(paths) > MAX_CORPUS:
        raise CorpusTooLargeError(len(paths))
    records = [record for path in paths if (record := _read(path, root)) is not None]
    stems = {record.stem for record in records}
    return [
        replace(record, declared=tuple(s for s in record.declared if s in stems))
        for record in records
    ]
