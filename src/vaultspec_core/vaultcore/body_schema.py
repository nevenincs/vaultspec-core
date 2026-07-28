"""Immutable body-section contracts and declared-schema resolution.

The contracts in this module are historical records. A newer schema must be
added under a new identifier; an existing contract is never edited. This lets
validation use the schema a document attests instead of deriving requirements
from the mutable template currently installed in a workspace.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypeGuard

from .models import DocType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .models import DocumentMetadata

__all__ = [
    "BASELINE_RELATIVE_PATH",
    "BODY_SCHEMA_REGISTRY",
    "CURRENT_BODY_SCHEMA",
    "BaselineEntry",
    "BodySchema",
    "BodySchemaResolution",
    "body_schema_baseline_path",
    "resolve_body_schema",
]


CURRENT_BODY_SCHEMA = "body-v1"
BASELINE_RELATIVE_PATH = PurePosixPath(".vaultspec/body-schema-baseline.json")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class BodySchema:
    """One immutable set of required body sections per document shape."""

    schema_id: str
    sections: Mapping[tuple[DocType, bool], tuple[str, ...]]

    def required_sections(
        self, doc_type: DocType, *, summary: bool = False
    ) -> tuple[str, ...]:
        """Return this schema's ordered required sections for a document shape."""
        return self.sections.get((doc_type, summary), ())


@dataclass(frozen=True)
class BaselineEntry:
    """One exact legacy-document attestation from the reviewed ledger."""

    path: str
    body_sha256: str
    body_schema: str


@dataclass(frozen=True)
class BodySchemaResolution:
    """Schema resolution result consumed by body-section validation.

    ``source`` deliberately distinguishes a current direct declaration from
    records which need a later hash-attested baseline. ``"missing"`` means no
    schema was declared and no ledger entry exists: the document makes no
    provenance claim, so a consumer should treat it as silence rather than a
    finding. ``"attestation_required"`` and ``"unknown"`` mean a document or
    the ledger made a claim the evidence contradicts, which a consumer should
    still report.
    """

    required_sections: tuple[str, ...] | None
    schema_id: str | None
    source: Literal[
        "attested", "declared", "attestation_required", "missing", "unknown"
    ]
    diagnostic: str | None = None


_BODY_V1_SECTIONS = MappingProxyType(
    {
        (DocType.ADR, False): (
            "Problem Statement",
            "Considerations",
            "Considered options",
            "Constraints",
            "Implementation",
            "Rationale",
            "Consequences",
        ),
        (DocType.AUDIT, False): ("Scope", "Findings", "Recommendations"),
        (DocType.PLAN, False): (
            "Description",
            "Steps",
            "Parallelization",
            "Verification",
        ),
        (DocType.RESEARCH, False): ("Findings", "Sources"),
        (DocType.REFERENCE, False): ("Summary",),
        (DocType.EXEC, False): ("Description", "Outcome", "Notes"),
        (DocType.EXEC, True): ("Description",),
        # Generated indexes are intentionally excluded by body-section checks,
        # but the contract remains explicit for callers that inspect schemas.
        (DocType.INDEX, False): ("Documents",),
    }
)

BODY_SCHEMA_REGISTRY: Mapping[str, BodySchema] = MappingProxyType(
    {
        CURRENT_BODY_SCHEMA: BodySchema(
            schema_id=CURRENT_BODY_SCHEMA,
            sections=_BODY_V1_SECTIONS,
        ),
        # Historical contracts are immutable template records.  They remain
        # distinct even where their headings happen to match ``body-v1``:
        # legacy documents are trusted only through an external body hash.
        "legacy-adr-v1": BodySchema(
            "legacy-adr-v1",
            MappingProxyType(
                {
                    (DocType.ADR, False): (
                        "Problem Statement",
                        "Considerations",
                        "Constraints",
                        "Implementation",
                        "Rationale",
                        "Consequences",
                    )
                }
            ),
        ),
        "legacy-adr-v2": BodySchema(
            "legacy-adr-v2",
            MappingProxyType(
                {
                    (DocType.ADR, False): (
                        "Problem Statement",
                        "Considerations",
                        "Constraints",
                        "Implementation",
                        "Rationale",
                        "Consequences",
                        "Codification candidates",
                    )
                }
            ),
        ),
        "legacy-adr-v3": BodySchema(
            "legacy-adr-v3",
            MappingProxyType(
                {
                    (DocType.ADR, False): (
                        "Problem Statement",
                        "Considerations",
                        "Considered options",
                        "Constraints",
                        "Implementation",
                        "Rationale",
                        "Consequences",
                    )
                }
            ),
        ),
        "legacy-audit-v1": BodySchema(
            "legacy-audit-v1",
            MappingProxyType(
                {(DocType.AUDIT, False): ("Scope", "Findings", "Recommendations")}
            ),
        ),
        "legacy-audit-v2": BodySchema(
            "legacy-audit-v2",
            MappingProxyType(
                {
                    (DocType.AUDIT, False): (
                        "Scope",
                        "Findings",
                        "Recommendations",
                        "Codification candidates",
                    )
                }
            ),
        ),
        "legacy-exec-v1": BodySchema(
            "legacy-exec-v1",
            MappingProxyType(
                {
                    (DocType.EXEC, False): ("Description", "Tests"),
                    (DocType.EXEC, True): ("Description", "Tests"),
                }
            ),
        ),
        "legacy-exec-v2": BodySchema(
            "legacy-exec-v2",
            MappingProxyType({(DocType.EXEC, False): ("Description", "Notes")}),
        ),
        "legacy-exec-v3": BodySchema(
            "legacy-exec-v3",
            MappingProxyType(
                {(DocType.EXEC, False): ("Description", "Outcome", "Notes")}
            ),
        ),
        "legacy-exec-v4": BodySchema(
            "legacy-exec-v4",
            MappingProxyType({(DocType.EXEC, True): ("Description",)}),
        ),
        "legacy-index-v1": BodySchema(
            "legacy-index-v1",
            MappingProxyType({(DocType.INDEX, False): ("Documents",)}),
        ),
        "legacy-plan-v1": BodySchema(
            "legacy-plan-v1",
            MappingProxyType(
                {
                    (DocType.PLAN, False): (
                        "Description",
                        "Steps",
                        "Parallelization",
                        "Verification",
                    )
                }
            ),
        ),
        "legacy-plan-v2": BodySchema(
            "legacy-plan-v2",
            MappingProxyType(
                {
                    (DocType.PLAN, False): (
                        "Proposed Changes",
                        "Steps",
                        "Parallelization",
                        "Verification",
                    )
                }
            ),
        ),
        "legacy-plan-v3": BodySchema(
            "legacy-plan-v3",
            MappingProxyType(
                {
                    (DocType.PLAN, False): (
                        "Proposed Changes",
                        "Tasks",
                        "Parallelization",
                        "Verification",
                    )
                }
            ),
        ),
        "legacy-reference-v1": BodySchema(
            "legacy-reference-v1",
            MappingProxyType({(DocType.REFERENCE, False): ("Summary",)}),
        ),
        "legacy-research-v1": BodySchema(
            "legacy-research-v1",
            MappingProxyType({(DocType.RESEARCH, False): ("Findings",)}),
        ),
        "legacy-research-v2": BodySchema(
            "legacy-research-v2",
            MappingProxyType({(DocType.RESEARCH, False): ("Findings", "Sources")}),
        ),
    }
)


def body_schema_baseline_path(root_dir: Path) -> Path:
    """Return the project-local, reviewable legacy-attestation ledger path."""
    return root_dir.joinpath(*BASELINE_RELATIVE_PATH.parts)


def _read_baseline_file(path: Path) -> tuple[Mapping[str, BaselineEntry], str | None]:
    """Read every validation pass so altered review evidence cannot go stale."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return MappingProxyType({}), f"cannot parse baseline ledger: {exc}"
    return _parse_baseline(raw)


def _read_baseline(root_dir: Path) -> tuple[Mapping[str, BaselineEntry], str | None]:
    path = body_schema_baseline_path(root_dir)
    try:
        exists = path.exists()
    except FileNotFoundError:
        return MappingProxyType({}), None
    except OSError as exc:
        return MappingProxyType({}), f"cannot read baseline ledger: {exc}"
    if not exists:
        return MappingProxyType({}), None
    if not path.is_file():
        return MappingProxyType({}), "baseline ledger is not a regular file"
    return _read_baseline_file(path)


def read_baseline(root_dir: Path) -> tuple[Mapping[str, BaselineEntry], str | None]:
    """Read and parse the legacy-attestation ledger once for a whole run.

    The ledger is a workspace-global fact: a caller validating many
    documents reads it exactly once per command invocation and threads the
    result into every :func:`resolve_body_schema` call, never re-reading it
    per document.  Each *run* still re-reads the ledger from disk (the
    review-evidence freshness guarantee), only the per-document repetition
    within one run is eliminated.

    Returns:
        The ``(entries, error)`` pair :func:`resolve_body_schema` accepts as
        its ``baseline`` argument.
    """
    return _read_baseline(root_dir)


def _parse_baseline(raw: object) -> tuple[Mapping[str, BaselineEntry], str | None]:
    """Parse the version-one ledger exactly; malformed input trusts nothing."""
    if not _is_json_object(raw) or set(raw) != {"version", "entries"}:
        return MappingProxyType({}), "ledger must contain exactly version and entries"
    entries_raw = raw["entries"]
    if raw["version"] != 1 or not isinstance(entries_raw, list):
        return MappingProxyType({}), "ledger must be version 1 with an entries list"

    entries: dict[str, BaselineEntry] = {}
    previous_path: str | None = None
    for index, raw_entry in enumerate(entries_raw):
        entry, entry_error = _parse_baseline_entry(index, raw_entry)
        if entry is None:
            return MappingProxyType({}), entry_error
        order_error = _baseline_order_error(entry.path, entries, previous_path)
        if order_error is not None:
            return MappingProxyType({}), order_error
        entries[entry.path] = entry
        previous_path = entry.path
    return MappingProxyType(entries), None


def _parse_baseline_entry(
    index: int, raw_entry: object
) -> tuple[BaselineEntry | None, str | None]:
    """Validate one ledger entry's shape and values in isolation."""
    if not _is_json_object(raw_entry) or set(raw_entry) != {
        "path",
        "body_sha256",
        "body_schema",
    }:
        return None, f"entry {index} has an invalid shape"
    path = raw_entry["path"]
    digest = raw_entry["body_sha256"]
    schema_id = raw_entry["body_schema"]
    if not isinstance(path, str) or not _is_canonical_vault_path(path):
        return None, f"entry {index} has an unsafe path"
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        return None, f"entry {index} has an invalid body_sha256"
    if (
        not isinstance(schema_id, str)
        or schema_id not in BODY_SCHEMA_REGISTRY
        or schema_id == CURRENT_BODY_SCHEMA
    ):
        return None, f"entry {index} names an invalid legacy body_schema"
    return BaselineEntry(path, digest, schema_id), None


def _baseline_order_error(
    path: str, entries: Mapping[str, BaselineEntry], previous_path: str | None
) -> str | None:
    """Reject a ledger path that repeats or breaks the sorted-path order."""
    if path in entries:
        return f"ledger contains duplicate path {path!r}"
    if previous_path is not None and path <= previous_path:
        return "ledger entries must be sorted by path"
    return None


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Narrow JSON-decoded objects without accepting non-string member names."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _is_canonical_vault_path(value: str) -> bool:
    """Accept only canonical POSIX paths rooted under ``.vault/``."""
    if "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and len(path.parts) >= 3
        and path.parts[0] == ".vault"
        and all(part not in {"", ".", ".."} for part in path.parts)
        and path.as_posix() == value
        and path.suffix == ".md"
    )


def resolve_body_schema(
    root_dir: Path,
    doc_path: Path,
    metadata: DocumentMetadata,
    body: str,
    *,
    baseline: tuple[Mapping[str, BaselineEntry], str | None] | None = None,
) -> BodySchemaResolution:
    """Resolve a document's declared immutable body schema.

    Only ``body-v1`` frontmatter is a direct declaration. Historical documents
    must match a path, body SHA-256, and historical contract in the reviewed
    project ledger; no mutable installed template is consulted.

    Args:
        root_dir: Project root directory.
        doc_path: The document being resolved.
        metadata: The document's parsed frontmatter metadata.
        body: The document's body text.
        baseline: The ledger read from :func:`read_baseline`.  Callers
            resolving many documents in one run read the ledger once and
            pass it here; when omitted the ledger is read for this call.
    """
    schema_id = metadata.body_schema
    if schema_id == CURRENT_BODY_SCHEMA:
        schema = BODY_SCHEMA_REGISTRY[CURRENT_BODY_SCHEMA]
        is_summary = doc_path.stem.endswith("-summary")
        doc_type = DocType.EXEC if is_summary else _document_type(metadata)
        return BodySchemaResolution(
            required_sections=schema.required_sections(doc_type, summary=is_summary),
            schema_id=schema_id,
            source="declared",
        )

    if schema_id and not schema_id.startswith("legacy-"):
        return BodySchemaResolution(
            required_sections=None,
            schema_id=schema_id,
            source="unknown",
            diagnostic=(f"{doc_path.name} declares unknown body_schema {schema_id!r}."),
        )

    entries, ledger_error = (
        baseline if baseline is not None else _read_baseline(root_dir)
    )
    if ledger_error is not None:
        return BodySchemaResolution(
            required_sections=None,
            schema_id=schema_id,
            source="attestation_required",
            diagnostic=f"baseline ledger is invalid: {ledger_error}",
        )
    relative_path = _relative_vault_path(root_dir, doc_path)
    entry = entries.get(relative_path) if relative_path is not None else None
    if entry is None:
        if schema_id:
            descriptor = f"declares legacy body_schema {schema_id!r}"
            requirement = "requires a hash-attested baseline entry"
        else:
            descriptor = "does not declare a body_schema"
            requirement = "requires a hash-attested legacy baseline entry"
        return BodySchemaResolution(
            required_sections=None,
            schema_id=schema_id,
            source="missing" if schema_id is None else "attestation_required",
            diagnostic=(f"{doc_path.name} {descriptor}; it {requirement}."),
        )
    return _resolve_attested(doc_path, metadata, body, schema_id, entry)


def _resolve_attested(
    doc_path: Path,
    metadata: DocumentMetadata,
    body: str,
    schema_id: str | None,
    entry: BaselineEntry,
) -> BodySchemaResolution:
    """Resolve a document against the ledger entry attesting its legacy body."""
    if schema_id is not None and schema_id != entry.body_schema:
        return BodySchemaResolution(
            required_sections=None,
            schema_id=schema_id,
            source="attestation_required",
            diagnostic=(
                f"{doc_path.name} declares legacy body_schema {schema_id!r}, "
                f"which conflicts with its attested schema {entry.body_schema!r}."
            ),
        )
    actual_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual_digest != entry.body_sha256:
        return BodySchemaResolution(
            required_sections=None,
            schema_id=entry.body_schema,
            source="attestation_required",
            diagnostic=(
                f"{doc_path.name} body SHA-256 does not match its attested "
                "legacy baseline."
            ),
        )
    schema = BODY_SCHEMA_REGISTRY[entry.body_schema]
    is_summary = doc_path.stem.endswith("-summary")
    doc_type = DocType.EXEC if is_summary else _document_type(metadata)
    required_sections = schema.required_sections(doc_type, summary=is_summary)
    if not required_sections:
        return BodySchemaResolution(
            required_sections=None,
            schema_id=entry.body_schema,
            source="attestation_required",
            diagnostic=(
                f"{doc_path.name} attests schema {entry.body_schema!r}, which "
                "does not apply to this document shape."
            ),
        )
    return BodySchemaResolution(
        required_sections=required_sections,
        schema_id=entry.body_schema,
        source="attested",
    )


def _relative_vault_path(root_dir: Path, doc_path: Path) -> str | None:
    """Return a canonical rooted path or reject documents outside the workspace.

    Scanned document paths are constructed under *root_dir*, so the plain
    lexical ``relative_to`` succeeds without touching the filesystem; the
    ``resolve``-based form (which opens a handle per call on Windows) is
    kept only as the fallback for callers passing paths rooted elsewhere.
    """
    try:
        return doc_path.relative_to(root_dir).as_posix()
    except ValueError:
        pass
    try:
        return doc_path.resolve().relative_to(root_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _document_type(metadata: DocumentMetadata) -> DocType:
    """Resolve document type from the single required directory tag."""
    for tag in metadata.tags:
        doc_type = DocType.from_tag(tag)
        if doc_type is not None:
            return doc_type
    # The frontmatter checker diagnoses this independently. Returning INDEX
    # keeps this resolver total for malformed documents and avoids a crash.
    return DocType.INDEX
