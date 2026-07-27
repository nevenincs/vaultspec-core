"""Validate a document body against its attested immutable section contract.

Required level-two (``## ``) headings come from the immutable body-schema
registry, never from today's mutable templates. A document either names a
known stamped schema or resolves through the repository's path-and-body-hash
baseline. A document declaring neither is silent: absence of a claim is not a
finding. A document (or the ledger) making a claim the evidence contradicts
is reported; it must not quietly inherit the current template.

For an attested schema, every required section must be present and carry real
authored content. A required section that is absent, or that holds only a
scaffold hint-comment or an unreplaced ``{placeholder}``, is reported: a
scaffolded-but-unauthored document cannot satisfy the contract. Author-added
extra sections are ignored; only the absence or emptiness of a required
section is a finding.

Edge handling:

- Execution records select ``exec-step.md`` or ``exec-summary.md`` by the
  ``-summary`` filename convention.
- Generated feature indexes are out of scope (their body is machine-authored).
- No ``body_schema`` declared and no ledger entry makes no provenance claim,
  so nothing is reported. A declared-but-unattested or ledger-contradicted
  claim (``attestation_required``, ``unknown``) is a finding, not a skip.

The checker is read-only: a section's position, ordering, and content are the
author's, so no safe automatic repair exists. Each finding's ``fix_description``
names the manual remedy.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    extract_feature_tags,
    is_generated_index,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ._base import VaultSnapshot

logger = logging.getLogger(__name__)

__all__ = ["check_body_sections"]

#: A level-two heading line (``## Title``), excluding deeper ``### `` headings.
_H2_RE = re.compile(r"^##[ \t]+(?P<title>\S.*?)\s*$", re.MULTILINE)

#: An HTML comment block, stripped before content-emptiness is judged.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

#: Content consisting only of ``{placeholder}`` tokens and whitespace, treated
#: as empty so an unauthored scaffold section does not satisfy the contract.
_PLACEHOLDER_ONLY_RE = re.compile(r"^(?:\s*\{[^{}]*\}\s*)+$")


def _section_contents(body: str) -> dict[str, str]:
    """Map each ``## `` heading title in *body* to its raw content.

    Content runs from just after the heading line to the next ``## `` heading
    or the end of the document. A later duplicate heading overwrites an earlier
    one; documents do not legitimately repeat a required section.
    """
    contents: dict[str, str] = {}
    matches = list(_H2_RE.finditer(body))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        contents[match.group("title")] = body[start:end]
    return contents


def _is_empty(section_body: str) -> bool:
    """Return ``True`` when a section carries no real authored content.

    A section is empty when, after HTML comments are stripped, nothing but
    whitespace remains, or when the remainder is only ``{placeholder}`` tokens.
    """
    text = _COMMENT_RE.sub("", section_body).strip()
    if not text:
        return True
    return _PLACEHOLDER_ONLY_RE.fullmatch(text) is not None


def check_body_sections(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
) -> CheckResult:
    """Validate every document body carries its attested required sections.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed
            ``(metadata, body)`` tuples.
        feature: Restrict checks to documents carrying this feature tag
            (without ``#``).

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with check
        name ``"body-sections"``. Does not support ``--fix``.
    """
    from ..body_schema import read_baseline, resolve_body_schema
    from ..scanner import get_doc_type

    result = CheckResult(check_name="body-sections", supports_fix=False)

    # The attestation ledger is a workspace-global fact: read once for the
    # whole pass, never per document.
    baseline = read_baseline(root_dir)

    for doc_path, (metadata, body) in sorted(snapshot.items()):
        doc_type = get_doc_type(doc_path, root_dir)
        if doc_type is None:
            continue
        if is_generated_index(doc_path):
            continue
        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        rel_path = doc_path.relative_to(root_dir)
        resolution = resolve_body_schema(
            root_dir, doc_path, metadata, body, baseline=baseline
        )
        required = resolution.required_sections
        if required is None:
            if resolution.source == "missing":
                # No body_schema declared and no ledger entry: the document
                # makes no provenance claim, so there is nothing to
                # contradict. Silence, not a finding.
                continue
            detail = (
                resolution.diagnostic or "no attested body schema was resolved"
            ).rstrip(".")
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=f"Body schema provenance is not attested: {detail}.",
                    severity=Severity.WARNING,
                    fixable=False,
                    fix_description=(
                        "Declare a known immutable body_schema or restore the "
                        "reviewed baseline attestation."
                    ),
                )
            )
            continue

        contents = _section_contents(body)

        for title in required:
            if title not in contents:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Missing required section '## {title}' mandated by "
                            f"attested body schema '{resolution.schema_id}'."
                        ),
                        severity=Severity.WARNING,
                        fixable=False,
                        fix_description=f"Add and fill the '## {title}' section.",
                    )
                )
            elif _is_empty(contents[title]):
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Required section '## {title}' is empty (only "
                            "scaffold comments or placeholders)."
                        ),
                        severity=Severity.WARNING,
                        fixable=False,
                        fix_description=f"Author real content under '## {title}'.",
                    )
                )

    return result
