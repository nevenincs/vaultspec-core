"""Tests for immutable declared body-section contracts and legacy attestations."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from ..body_schema import (
    BODY_SCHEMA_REGISTRY,
    CURRENT_BODY_SCHEMA,
    body_schema_baseline_path,
    resolve_body_schema,
)
from ..models import DocType, DocumentMetadata
from ..parser import parse_vault_metadata

pytestmark = [pytest.mark.unit]


def _metadata(doc_type: DocType, body_schema: str | None) -> DocumentMetadata:
    return DocumentMetadata(
        tags=[doc_type.tag, "#schema-provenance"],
        date="2026-07-27",
        body_schema=body_schema,
    )


def _write_baseline(root: Path, entries: list[dict[str, str]]) -> None:
    """Write a real version-one ledger into the test workspace."""
    path = body_schema_baseline_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "entries": entries}, indent=2) + "\n",
        encoding="utf-8",
    )


def _entry(path: str, body: str, schema: str) -> dict[str, str]:
    return {
        "path": path,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "body_schema": schema,
    }


def test_current_contract_is_immutable_and_has_exec_shape_variants() -> None:
    schema = BODY_SCHEMA_REGISTRY[CURRENT_BODY_SCHEMA]

    assert schema.required_sections(DocType.RESEARCH) == ("Findings", "Sources")
    assert schema.required_sections(DocType.EXEC) == ("Description", "Outcome", "Notes")
    assert schema.required_sections(DocType.EXEC, summary=True) == ("Description",)

    # The registry and its section maps are read-only Mappings statically, so
    # a write is expressed through a cast rather than a checker suppression:
    # the point of the assertion is that the runtime object rejects it too.
    with pytest.raises(TypeError):
        cast("dict[str, Any]", BODY_SCHEMA_REGISTRY)["future-v1"] = schema
    with pytest.raises(TypeError):
        cast("dict[tuple[DocType, bool], Any]", schema.sections)[
            (DocType.RESEARCH, False)
        ] = ("Findings",)


def test_registry_preserves_all_sixteen_historical_template_contracts() -> None:
    legacy_ids = {key for key in BODY_SCHEMA_REGISTRY if key.startswith("legacy-")}

    assert len(legacy_ids) == 16
    assert "legacy-plan-v2" in legacy_ids
    assert "legacy-exec-v1" in legacy_ids


def test_resolver_uses_declared_contract_not_workspace_templates(
    tmp_path: Path,
) -> None:
    doc_path = tmp_path / ".vault" / "research" / "2026-07-27-demo-research.md"

    resolution = resolve_body_schema(
        tmp_path,
        doc_path,
        _metadata(DocType.RESEARCH, CURRENT_BODY_SCHEMA),
        "# demo\n\n## Findings\n\nEvidence.\n",
    )

    assert resolution.source == "declared"
    assert resolution.schema_id == CURRENT_BODY_SCHEMA
    assert resolution.required_sections == ("Findings", "Sources")
    assert resolution.diagnostic is None


def test_resolver_rejects_forged_legacy_schema_without_attestation(
    tmp_path: Path,
) -> None:
    resolution = resolve_body_schema(
        tmp_path,
        tmp_path / ".vault" / "adr" / "2026-07-27-demo-adr.md",
        _metadata(DocType.ADR, "legacy-adr-v1"),
        "# demo\n",
    )

    assert resolution.required_sections is None
    assert resolution.source == "attestation_required"
    assert resolution.diagnostic is not None
    assert "hash-attested baseline" in resolution.diagnostic


@pytest.mark.parametrize(
    ("body_schema", "source", "message"),
    [
        (None, "missing", "requires a hash-attested legacy baseline"),
        ("body-v999", "unknown", "unknown body_schema"),
    ],
)
def test_resolver_reports_unattested_or_unknown_provenance(
    tmp_path: Path,
    body_schema: str | None,
    source: str,
    message: str,
) -> None:
    resolution = resolve_body_schema(
        tmp_path,
        tmp_path / ".vault" / "adr" / "2026-07-27-demo-adr.md",
        _metadata(DocType.ADR, body_schema),
        "# demo\n",
    )

    assert resolution.required_sections is None
    assert resolution.source == source
    assert resolution.diagnostic is not None
    assert message in resolution.diagnostic


def test_resolver_accepts_real_hash_attested_legacy_fixture(tmp_path: Path) -> None:
    body = (
        "# Legacy ADR\n\n## Problem Statement\n\nWhy.\n\n"
        "## Considerations\n\nTrade-offs.\n\n## Constraints\n\nLimits.\n\n"
        "## Implementation\n\nWork.\n\n## Rationale\n\nReason.\n\n"
        "## Consequences\n\nEffects.\n"
    )
    doc_path = tmp_path / ".vault" / "adr" / "2026-01-01-legacy-adr.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text(
        "---\ntags:\n  - '#adr'\n  - '#legacy'\ndate: '2026-01-01'\n---\n" + body,
        encoding="utf-8",
    )
    metadata, parsed_body = parse_vault_metadata(doc_path.read_text(encoding="utf-8"))
    _write_baseline(
        tmp_path,
        [
            _entry(
                ".vault/adr/2026-01-01-legacy-adr.md",
                parsed_body,
                "legacy-adr-v1",
            )
        ],
    )

    resolution = resolve_body_schema(tmp_path, doc_path, metadata, parsed_body)

    assert resolution.source == "attested"
    assert resolution.schema_id == "legacy-adr-v1"
    assert resolution.required_sections == (
        "Problem Statement",
        "Considerations",
        "Constraints",
        "Implementation",
        "Rationale",
        "Consequences",
    )


def test_resolver_is_stable_across_a_frontmatter_only_modified_stamp_refresh(
    tmp_path: Path,
) -> None:
    """A ``modified:`` stamp refresh must never move the attested body digest.

    ``body_sha256`` is computed from the parsed body only, which begins after
    the closing frontmatter fence, so a frontmatter-only mutation - the
    ``modified:`` stamp refresh every mutating verb performs - must leave the
    digest, and therefore the attestation, unchanged.
    """
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    rel_path = ".vault/research/2026-01-01-legacy-research.md"
    doc_path = tmp_path / rel_path
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text(
        "---\ntags:\n  - '#research'\n  - '#legacy'\n"
        "date: '2026-01-01'\nmodified: '2026-01-01'\n---\n" + body,
        encoding="utf-8",
    )
    _write_baseline(tmp_path, [_entry(rel_path, body, "legacy-research-v1")])

    metadata, parsed_body = parse_vault_metadata(doc_path.read_text(encoding="utf-8"))
    before = resolve_body_schema(tmp_path, doc_path, metadata, parsed_body)
    assert before.source == "attested"

    # Simulate a mutating verb's stamp refresh: only the frontmatter changes.
    doc_path.write_text(
        "---\ntags:\n  - '#research'\n  - '#legacy'\n"
        "date: '2026-01-01'\nmodified: '2026-07-29'\n---\n" + body,
        encoding="utf-8",
    )
    metadata, parsed_body = parse_vault_metadata(doc_path.read_text(encoding="utf-8"))
    after = resolve_body_schema(tmp_path, doc_path, metadata, parsed_body)

    assert after.source == "attested"
    assert after.required_sections == before.required_sections


def test_resolver_digest_is_invariant_to_source_newline_convention(
    tmp_path: Path,
) -> None:
    """A CRLF-saved document must attest identically to its LF equivalent.

    ``resolve_body_schema`` is always handed a body produced by universal-
    newline text reads (``Path.read_text`` and the graph's byte-level mirror
    of it), so the same logical content attests the same way regardless of
    whether the file on disk uses ``\\n`` or ``\\r\\n`` line endings. The
    ledger entry is computed from the LF-normalized body - the only form the
    application ever hashes - so a CRLF source must still match it.
    """
    lf_body = "# Legacy\n\n## Findings\n\nEvidence held in the record.\n"
    rel_path = ".vault/research/2026-01-01-crlf-legacy-research.md"
    doc_path = tmp_path / rel_path
    doc_path.parent.mkdir(parents=True)
    crlf_document = (
        "---\r\ntags:\r\n  - '#research'\r\n  - '#legacy'\r\n"
        "date: '2026-01-01'\r\n---\r\n" + lf_body.replace("\n", "\r\n")
    )
    doc_path.write_bytes(crlf_document.encode("utf-8"))
    assert b"\r\n" in doc_path.read_bytes()

    # The ledger attests the LF-normalized body, exactly as any populator
    # must, since that is the only form ``resolve_body_schema`` ever hashes.
    _write_baseline(tmp_path, [_entry(rel_path, lf_body, "legacy-research-v1")])

    # ``read_text`` performs universal-newline translation on read, so the
    # parsed body is LF-only even though the file on disk is CRLF.
    metadata, parsed_body = parse_vault_metadata(doc_path.read_text(encoding="utf-8"))
    assert parsed_body == lf_body

    resolution = resolve_body_schema(tmp_path, doc_path, metadata, parsed_body)

    assert resolution.source == "attested"
    assert resolution.schema_id == "legacy-research-v1"
    assert resolution.required_sections == ("Findings",)


def test_resolver_rejects_tampered_legacy_body(tmp_path: Path) -> None:
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    doc_path = tmp_path / ".vault" / "research" / "2026-01-01-legacy-research.md"
    _write_baseline(
        tmp_path,
        [
            _entry(
                ".vault/research/2026-01-01-legacy-research.md",
                body,
                "legacy-research-v1",
            )
        ],
    )

    resolution = resolve_body_schema(
        tmp_path, doc_path, _metadata(DocType.RESEARCH, None), body + "Changed.\n"
    )

    assert resolution.required_sections is None
    assert resolution.source == "attestation_required"
    assert resolution.diagnostic is not None
    assert "SHA-256" in resolution.diagnostic


def test_resolver_rejects_path_escape_in_ledger(tmp_path: Path) -> None:
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    _write_baseline(
        tmp_path,
        [_entry(".vault/adr/../../outside.md", body, "legacy-research-v1")],
    )

    resolution = resolve_body_schema(
        tmp_path,
        tmp_path / ".vault" / "research" / "2026-01-01-legacy-research.md",
        _metadata(DocType.RESEARCH, None),
        body,
    )

    assert resolution.required_sections is None
    assert resolution.diagnostic is not None
    assert "unsafe path" in resolution.diagnostic


def test_resolver_rejects_duplicate_ledger_entries(tmp_path: Path) -> None:
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    entry = _entry(
        ".vault/research/2026-01-01-legacy-research.md", body, "legacy-research-v1"
    )
    _write_baseline(tmp_path, [entry, entry])

    resolution = resolve_body_schema(
        tmp_path,
        tmp_path / ".vault" / "research" / "2026-01-01-legacy-research.md",
        _metadata(DocType.RESEARCH, None),
        body,
    )

    assert resolution.required_sections is None
    assert resolution.diagnostic is not None
    assert "duplicate path" in resolution.diagnostic


def test_resolver_reloads_ledger_when_tampering_preserves_metadata(
    tmp_path: Path,
) -> None:
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    path = ".vault/research/2026-01-01-legacy-research.md"
    document = tmp_path / path
    _write_baseline(tmp_path, [_entry(path, body, "legacy-research-v1")])
    initial = resolve_body_schema(
        tmp_path, document, _metadata(DocType.RESEARCH, None), body
    )
    assert initial.source == "attested"

    ledger = body_schema_baseline_path(tmp_path)
    before = ledger.stat()
    _write_baseline(
        tmp_path,
        [
            {
                "path": path,
                "body_sha256": "0" * 64,
                "body_schema": "legacy-research-v1",
            }
        ],
    )
    os.utime(ledger, ns=(before.st_atime_ns, before.st_mtime_ns))

    resolution = resolve_body_schema(
        tmp_path, document, _metadata(DocType.RESEARCH, None), body
    )

    assert resolution.required_sections is None
    assert resolution.source == "attestation_required"
    assert resolution.diagnostic is not None
    assert "SHA-256" in resolution.diagnostic


def test_resolver_rejects_non_string_ledger_schema(tmp_path: Path) -> None:
    body = "# Legacy\n\n## Findings\n\nEvidence.\n"
    path = ".vault/research/2026-01-01-legacy-research.md"
    ledger = body_schema_baseline_path(tmp_path)
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "path": path,
                        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        "body_schema": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolution = resolve_body_schema(
        tmp_path, tmp_path / path, _metadata(DocType.RESEARCH, None), body
    )

    assert resolution.required_sections is None
    assert resolution.source == "attestation_required"
    assert resolution.diagnostic is not None
    assert "invalid legacy body_schema" in resolution.diagnostic


def test_resolver_rejects_forged_declared_legacy_schema(tmp_path: Path) -> None:
    body = "# Legacy ADR\n\n## Problem Statement\n\nWhy.\n"
    doc_path = tmp_path / ".vault" / "adr" / "2026-01-01-legacy-adr.md"
    _write_baseline(
        tmp_path,
        [_entry(".vault/adr/2026-01-01-legacy-adr.md", body, "legacy-adr-v1")],
    )

    resolution = resolve_body_schema(
        tmp_path, doc_path, _metadata(DocType.ADR, "legacy-adr-v2"), body
    )

    assert resolution.required_sections is None
    assert resolution.source == "attestation_required"
    assert resolution.diagnostic is not None
    assert "conflicts" in resolution.diagnostic
