"""Define the core domain model for `.vault/` documents and metadata.

This module captures document types, frontmatter structure, tag constraints,
filename validation, and related structural rules. It is the semantic heart of
the vault model on which parsing, scanning, verification, and higher-level
analysis depend.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

__all__ = [
    "DocType",
    "DocumentMetadata",
    "VaultConstants",
    "normalize_date",
    "parse_lenient_date",
]

if TYPE_CHECKING:
    from pathlib import Path

#: Canonical vault date form: ``yyyy-mm-dd`` (ISO 8601 calendar date).
_CANONICAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Slash-separated year-first form: ``yyyy/mm/dd``.
_YEAR_FIRST_SLASH_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")

#: Two small components and a four-digit year, ``dd-mm-yyyy`` or
#: ``mm/dd/yyyy`` style, with a consistent ``-`` or ``/`` separator.
_YEAR_LAST_RE = re.compile(r"^(\d{1,2})([-/])(\d{1,2})\2(\d{4})$")


def parse_lenient_date(value: object) -> _dt.date | None:
    """Parse a frontmatter date value leniently into a :class:`datetime.date`.

    This is the single canonical lenient-date helper mandated by the
    vault-orientation ADR (decision D3b). Every consumer of the
    ``date:`` / ``modified:`` stamps (validation, the check/fix
    reconciliation path, the backfill migration, and the status
    rollup's recency sort) parses through this function so hand-edited
    values in common formats survive, while genuinely ambiguous or
    unrecognisable values are rejected rather than guessed at.

    Accepted inputs:

    - :class:`datetime.date` / :class:`datetime.datetime` objects
      (YAML parses unquoted ``yyyy-mm-dd`` scalars into these).
    - Canonical ``yyyy-mm-dd`` strings.
    - ISO 8601 timestamps (``yyyy-mm-ddTHH:MM:SS`` with optional
      fractional seconds and zone offset; a space separator is also
      accepted).
    - Slash-separated year-first dates (``yyyy/mm/dd``).
    - Year-last forms (``dd-mm-yyyy``, ``mm/dd/yyyy``) **only when
      unambiguous**: one of the two leading components must exceed 12
      so day and month are distinguishable. Ambiguous values such as
      ``03-04-2026`` are rejected (return ``None``) rather than
      guessed.

    Surrounding whitespace and stray single/double quotes are stripped
    before parsing.

    Args:
        value: Raw frontmatter value - a string, a
            :class:`datetime.date`, a :class:`datetime.datetime`, or
            any other object (which fails parsing).

    Returns:
        The parsed :class:`datetime.date`, or ``None`` when the value
        is missing, ambiguous, or unrecognisable. Callers must treat
        ``None`` as a finding (per D3b a value no parser recognises is
        flagged, never silently dropped).

    See Also:
        :func:`normalize_date` for the canonical-string companion, and
        :meth:`DocumentMetadata.validate` for the validation policy
        built on this helper.
    """
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip().strip("\"'").strip()
    if not text:
        return None

    if _CANONICAL_DATE_RE.match(text):
        try:
            return _dt.date.fromisoformat(text)
        except ValueError:
            return None

    # ISO 8601 timestamps, optionally zoned ('Z' or offset), with either
    # a 'T' or a space separator (Python 3.11+ fromisoformat handles both).
    try:
        return _dt.datetime.fromisoformat(text).date()
    except ValueError:
        pass

    m = _YEAR_FIRST_SLASH_RE.match(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return _dt.date(year, month, day)
        except ValueError:
            return None

    m = _YEAR_LAST_RE.match(text)
    if m:
        first, second, year = int(m.group(1)), int(m.group(3)), int(m.group(4))
        if first > 12 and 1 <= second <= 12:
            day, month = first, second
        elif second > 12 and 1 <= first <= 12:
            month, day = first, second
        else:
            # Both components could be a month: ambiguous - reject
            # rather than guess (D3b).
            return None
        try:
            return _dt.date(year, month, day)
        except ValueError:
            return None

    return None


def normalize_date(value: object) -> str | None:
    """Normalize a lenient date value to the canonical ``yyyy-mm-dd`` string.

    Companion to :func:`parse_lenient_date`: the check/fix
    reconciliation path and the backfill migration use this to rewrite
    whatever they parsed back to the canonical quoted ``yyyy-mm-dd``
    form mandated by the vault-orientation ADR (decision D3b).

    Args:
        value: Raw frontmatter value accepted by
            :func:`parse_lenient_date`.

    Returns:
        The canonical ``yyyy-mm-dd`` string, or ``None`` when the value
        cannot be parsed.
    """
    parsed = parse_lenient_date(value)
    return parsed.isoformat() if parsed is not None else None


class DocType(StrEnum):
    """Rigidly defined document types corresponding to .vault/ subdirectories."""

    ADR = "adr"
    AUDIT = "audit"
    EXEC = "exec"
    INDEX = "index"
    PLAN = "plan"
    REFERENCE = "reference"
    RESEARCH = "research"

    @property
    def tag(self) -> str:
        """The mandatory directory tag associated with this type.

        Returns:
            Hashtag string such as ``#adr`` or ``#exec``.
        """
        return f"#{self.value}"

    @classmethod
    def from_tag(cls, tag: str) -> DocType | None:
        """Return the DocType that owns the given ``#tag`` string.

        Args:
            tag: Hashtag string such as ``#adr`` or ``#exec``.

        Returns:
            Matching ``DocType``, or ``None`` if the tag is not recognised.
        """
        for dt in cls:
            if dt.tag == tag:
                return dt
        return None


@dataclass
class DocumentMetadata:
    """Rigid representation of YAML frontmatter for all .vault/ files.

    Attributes:
        tags: At least two tags - one directory tag and one feature tag.
            Additional freeform tags are allowed beyond the required pair.
        date: ISO 8601 creation date (``YYYY-MM-DD``).
        modified: CLI-maintained last-modified stamp (``YYYY-MM-DD``, same
            granularity as ``date``). Set equal to ``date`` at scaffold time
            and refreshed by every CLI verb that mutates the document; the
            status rollup reads it as the recency source.
        related: List of Obsidian-style ``[[wiki-link]]`` strings.
        supersedes: List of old ADR/Plan stems.
        superseded_by: Single new ADR/Plan stem.
        derived_from: List of audit/finding references.
        promoted_to: List of rules promoted.
        archived: ISO date (``YYYY-MM-DD``) set on archived documents.
    """

    tags: list[str] = field(default_factory=list)
    date: str | None = None
    modified: str | None = None
    related: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    derived_from: list[str] = field(default_factory=list)
    promoted_to: list[str] = field(default_factory=list)
    archived: str | None = None

    def validate(self) -> list[str]:
        """Validate the metadata against the vault schema rules.

        The ``modified`` stamp follows the lenient policy from the
        vault-orientation ADR (decision D3b): a canonical
        ``yyyy-mm-dd`` value is valid; a value that
        :func:`parse_lenient_date` can parse but is not canonical is
        also accepted here (the ``vault check all --fix``
        reconciliation path normalizes it later rather than validation
        hard-failing on a permitted hand edit); only an unparseable
        value is a violation.

        Returns:
            A list of human-readable violation messages; empty list means valid.
        """
        errors = []

        #  Tags: at least one directory tag and one feature tag (minimum 2)
        if len(self.tags) < 2:
            msg = f"Vault violation: At least 2 tags required, found {len(self.tags)}"
            errors.append(msg)

        #  Directory Tag (Type)
        dir_tags = [t for t in self.tags if DocType.from_tag(t)]
        if len(dir_tags) != 1:
            allowed = ", ".join(sorted(dt.tag for dt in DocType))
            msg = (
                "Vault violation: Exactly one directory tag required "
                f"({allowed}). Found: {dir_tags}"
            )
            errors.append(msg)

        #  Feature Tag (Kind)
        feature_tags = [t for t in self.tags if not DocType.from_tag(t)]
        if len(feature_tags) != 1:
            msg = (
                "Vault violation: Exactly one feature tag (#<feature>) required. "
                f"Found: {feature_tags}"
            )
            errors.append(msg)
        elif feature_tags and not re.match(r"^#[a-z0-9-]+$", feature_tags[0]):
            msg = (
                f"Vault violation: Invalid feature tag format '{feature_tags[0]}'. "
                "Must be kebab-case (e.g., #editor-demo)."
            )
            errors.append(msg)

        #  Date Format
        if not self.date:
            errors.append("Vault violation: 'date' field is required.")
        elif not re.match(r"^\d{4}-\d{2}-\d{2}$", self.date):
            msg = (
                f"Vault violation: Invalid date format '{self.date}'. "
                "Must be YYYY-MM-DD."
            )
            errors.append(msg)

        #  Modified Stamp: canonical ok; lenient-parseable noncanonical ok
        #  (normalized later by the check/fix path); unparseable is a
        #  violation (D3b: flagged, never silently dropped).
        if (
            self.modified
            and not _CANONICAL_DATE_RE.match(self.modified)
            and parse_lenient_date(self.modified) is None
        ):
            msg = (
                f"Vault violation: Unparseable modified date '{self.modified}'. "
                "Must be a date in (or normalizable to) YYYY-MM-DD form."
            )
            errors.append(msg)

        #  Related Wiki-links
        for link in self.related:
            if not (link.startswith("[[") and link.endswith("]]")):
                msg = (
                    f"Vault violation: Invalid related link '{link}'. "
                    "Must be a quoted [[wiki-link]]."
                )
                errors.append(msg)

        #  Archived Date Format
        if self.archived and not re.match(r"^\d{4}-\d{2}-\d{2}$", self.archived):
            msg = (
                f"Vault violation: Invalid archived date format '{self.archived}'. "
                "Must be YYYY-MM-DD."
            )
            errors.append(msg)

        return errors


class VaultConstants:
    """Static configuration and validation helpers for the ``.vault/`` structure.

    Class-level sets (:data:`SUPPORTED_DIRECTORIES`, :data:`SUPPORTED_TAGS`) enumerate
    the valid subdirectory names and their corresponding ``#tags``. Class methods
    validate directory layout, filename conventions, and tag-to-directory mapping.
    """

    @staticmethod
    def _get_docs_dir() -> str:
        """Return the configured docs directory name (e.g. ``.vault``).

        Returns:
            Directory name string such as ``".vault"``.
        """
        from ..config import get_config

        return get_config().docs_dir

    @staticmethod
    def _get_index_dir() -> str:
        """Return the configured index subdirectory name (e.g. ``index``).

        Returns:
            Directory name string such as ``"index"``.
        """
        from ..config import get_config

        return get_config().index_dir

    # Supported directories within .vault/ (one per DocType, including INDEX
    # which now lives in its own subfolder rather than at the vault root).
    SUPPORTED_DIRECTORIES: ClassVar[set[str]] = {dt.value for dt in DocType}

    # Non-document directories that are legitimate .vault/ content
    # (e.g. data stores, log output) but not document types.
    AUXILIARY_DIRECTORIES: ClassVar[set[str]] = {"data", "logs", "_archive"}

    # Supported directory tags (one per DocType, including #index).
    SUPPORTED_TAGS: ClassVar[set[str]] = {dt.tag for dt in DocType}

    @classmethod
    def is_supported_directory(cls, dirname: str) -> bool:
        """Return whether *dirname* is a recognized vault subdirectory.

        Checks both document directories (:data:`SUPPORTED_DIRECTORIES`) and
        non-document auxiliary directories (:data:`AUXILIARY_DIRECTORIES`).

        Args:
            dirname: Bare directory name (e.g. ``"adr"``, ``"data"``).

        Returns:
            ``True`` if the directory is recognized.
        """
        return (
            dirname in cls.SUPPORTED_DIRECTORIES or dirname in cls.AUXILIARY_DIRECTORIES
        )

    @classmethod
    def validate_vault_structure(cls, root_dir: Path) -> list[str]:
        """Ensure the docs directory only contains recognised subdirectories.

        The vault root must contain only the seven canonical document
        subdirectories (one per :class:`DocType`, including the
        :class:`DocType.INDEX` subfolder), the auxiliary data/log
        directories, and an optional ``readme.md``. Files at the docs
        root are violations: ``<feature>.index.md`` files at the root are
        legacy artifacts that should be relocated into the index
        subfolder.

        Args:
            root_dir: Project root containing the docs directory.

        Returns:
            List of violation message strings; empty when the structure is
            valid.
        """
        docs_dir_name = cls._get_docs_dir()
        index_dir_name = cls._get_index_dir()
        docs_dir = root_dir / docs_dir_name
        if not docs_dir.exists():
            return []

        errors = []
        # Check for unsupported directories
        for item in docs_dir.iterdir():
            if item.is_dir():
                if item.name.startswith("."):
                    # Allow internal hidden folders like .obsidian
                    continue
                if not cls.is_supported_directory(item.name):
                    msg = (
                        "Vault violation: Unsupported directory found in "
                        f"{docs_dir_name}/: '{item.name}'"
                    )
                    errors.append(msg)
            elif item.is_file():
                if item.name.lower() == "readme.md":
                    continue
                if item.name.endswith(".index.md"):
                    msg = (
                        f"Vault violation: Legacy feature index '{item.name}' "
                        f"at {docs_dir_name}/ root. Index files now live in "
                        f"{docs_dir_name}/{index_dir_name}/. Run "
                        "'vaultspec-core migrations run' to apply the "
                        "registered schema migration."
                    )
                    errors.append(msg)
                    continue
                msg = (
                    f"Vault violation: File found in {docs_dir_name}/ root: "
                    f"'{item.name}'. Files should be in subdirectories."
                )
                errors.append(msg)

        return errors

    @classmethod
    def validate_filename(
        cls, filename: str, doc_type: DocType | None = None
    ) -> list[str]:
        """Validate a filename against the vault naming convention.

        Expected pattern: ``yyyy-mm-dd-<feature>-<type>.md`` for the six
        authored document types, and ``<feature>.index.md`` (no date
        prefix) for the auto-generated :class:`DocType.INDEX` files.

        Args:
            filename: Bare filename (no directory component) to validate.
            doc_type: When provided, also checks that the filename's type
                suffix matches this ``DocType``.

        Returns:
            List of violation message strings; empty when the filename is valid.
        """
        errors = []

        if not filename.endswith(".md"):
            msg = f"Vault violation: Filename '{filename}' must have .md extension."
            errors.append(msg)
            return errors

        # Index files use a separate naming convention: <feature>.index.md
        # (no date prefix, no document-type suffix).
        if doc_type == DocType.INDEX or filename.endswith(".index.md"):
            index_pattern = r"^[a-z0-9-]+\.index\.md$"
            if not re.match(index_pattern, filename):
                msg = (
                    f"Vault violation: Index filename '{filename}' deviates "
                    "from standard <feature>.index.md pattern."
                )
                errors.append(msg)
            return errors

        # Execution records use the plan-hardening Step Record / Phase Summary
        # naming: uppercase canonical container ids (with an optional lowercase
        # alpha suffix on Wave / Phase) and no '-exec' type token, matching what
        # 'vault add exec --step' scaffolds and what the framework rules
        # document (issue #123). The legacy '...-exec' form is still accepted via
        # the generic pattern below for records authored before the convention.
        if doc_type == DocType.EXEC:
            date_feature = r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+"
            step_record = (
                rf"^{date_feature}-(W\d{{2,}}[a-z]?-)?(P\d{{2,}}[a-z]?-)?"
                r"S\d{2,}\.md$"
            )
            phase_summary = (
                rf"^{date_feature}-(W\d{{2,}}[a-z]?-)?P\d{{2,}}[a-z]?-summary\.md$"
            )
            if re.match(step_record, filename) or re.match(phase_summary, filename):
                return errors

        # Basic pattern: 2026-02-07-feature-name-adr.md
        # Or for exec: 2026-02-07-feature-name-phase1-step1.md
        pattern = (
            r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+-"
            r"(adr|audit|exec|plan|reference|research)(-[a-z0-9-]+)*\.md$"
        )
        if not re.match(pattern, filename):
            msg = (
                f"Vault violation: Filename '{filename}' deviates from "
                "standard yyyy-mm-dd-<feature>-<type>.md pattern."
            )
            errors.append(msg)
            return errors

        # If doc_type is provided, ensure it matches the filename suffix
        if doc_type:
            suffix = f"-{doc_type.value}"
            # Special case for exec records
            if doc_type == DocType.EXEC:
                if f"-{DocType.EXEC.value}" not in filename:
                    msg = (
                        f"Vault violation: Filename '{filename}' does not "
                        "contain expected type suffix '-exec'."
                    )
                    errors.append(msg)
            else:
                if not filename.endswith(f"{suffix}.md"):
                    msg = (
                        f"Vault violation: Filename '{filename}' does not "
                        f"match expected type suffix '{suffix}.md'."
                    )
                    errors.append(msg)

        return errors
