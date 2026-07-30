"""Contract tests for checked-in vaultspec rule guidance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.builtins import builtins_root

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: The bundled builtins package this module asserts against. Resolved through
#: the package's own accessor rather than by walking to a repository root: the
#: content under test is a sibling of the module that owns it and ships inside
#: the distributed package, so it is addressable package-relatively wherever
#: the package is installed.
BUILTINS_ROOT = builtins_root()


def _existing_markdown_files(root: Path) -> list[Path]:
    assert root.is_dir(), f"Expected checked rule directory to exist: {root}"
    files = sorted(root.rglob("*.md"))
    assert files, f"Expected checked rule directory to contain markdown: {root}"
    return files


def test_top_level_doc_guidance_omits_phase_filename_segment() -> None:
    """Top-level document filenames follow the vault doc naming convention."""
    stale_patterns = (
        "yyyy-mm-dd-{feature}-" + "{phase}-plan.md",
        "yyyy-mm-dd-<feature>-" + "<phase>-plan.md",
        "yyyy-mm-dd-{feature}-" + "{phase}-research.md",
        "yyyy-mm-dd-<feature>-" + "<phase>-research.md",
        "yyyy-mm-dd-{feature}-" + "{phase}-adr.md",
        "yyyy-mm-dd-<feature>-" + "<phase>-adr.md",
    )
    checked_roots = (BUILTINS_ROOT,)

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []


def test_rule_guidance_uses_canonical_file_placeholders() -> None:
    """Vault rule guidance should not use uppercase filename placeholders."""
    stale_patterns = (
        "YYYY-MM-DD-{Feature}",
        "YYYY-MM-DD-<Feature>",
    )
    checked_roots = (
        BUILTINS_ROOT / "skills",
        BUILTINS_ROOT / "agents",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []


def test_code_review_guidance_persists_audit_artifacts() -> None:
    """Code-review reports use the audit template and audit directory."""
    checked_paths = (
        BUILTINS_ROOT / "skills" / "vaultspec-code-review" / "SKILL.md",
        BUILTINS_ROOT / "agents" / "vaultspec-code-reviewer.md",
    )
    stale_patterns = (
        ".vault/exec/yyyy-mm-dd-<feature>/yyyy-mm-dd-<feature>-review.md",
        ".vault/audit/yyyy-mm-dd-{feature}-" + "{review}.md",
        ".vault/audit/YYYY-MM-DD-{feature}-" + "{review}.md",
        "Directory Tag**: Exactly `#exec` (based on location in `.vault/exec/`)",
    )

    offenders: list[str] = []
    for path in checked_paths:
        assert path.is_file(), f"Expected checked rule file to exist: {path}"
        text = path.read_text(encoding="utf-8")
        for pattern in stale_patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []


def test_exec_step_guidance_is_not_l2_only() -> None:
    """Step Record guidance must not hard-code the L2 phase-step shape."""
    stale_patterns = (
        ".vault/exec/yyyy-mm-dd-{feature}/yyyy-mm-dd-{feature}-{phase}-{step}.md",
        ".vault/exec/yyyy-mm-dd-<feature>/yyyy-mm-dd-<feature>-<phase>-<step>.md",
    )
    checked_roots = (
        BUILTINS_ROOT / "skills",
        BUILTINS_ROOT / "agents",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []


def test_curator_guidance_matches_current_frontmatter_contract() -> None:
    """Curator instructions should not reintroduce removed YAML guidance."""
    checked_paths = (
        BUILTINS_ROOT / "skills" / "vaultspec-curate" / "SKILL.md",
        BUILTINS_ROOT / "agents" / "vaultspec-docs-curator.md",
    )
    stale_patterns = (
        "mandatory comment `# ALLOWED TAGS",
        "allowed list (`tags`, `date`, `related`)",
        "Exactly one of `#adr`, `#audit`, `#exec`, `#plan`,",
        'MUST be `- "[[link]]"`',
        ".vault/exec/yyyy-mm-dd-docs-curation/yyyy-mm-dd-docs-curation-audit.md",
    )

    offenders: list[str] = []
    for path in checked_paths:
        assert path.is_file(), f"Expected checked rule file to exist: {path}"
        text = path.read_text(encoding="utf-8")
        for pattern in stale_patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []


def test_rule_guidance_does_not_forbid_template_extra_tags() -> None:
    """Template guidance allows tags beyond the required pair."""
    checked_roots = (
        BUILTINS_ROOT / "skills",
        BUILTINS_ROOT / "agents",
        BUILTINS_ROOT / "rules",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            if "EXACTLY TWO" in text:
                offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: EXACTLY TWO")

    assert offenders == []


def test_rule_guidance_uses_template_quote_style() -> None:
    """Rule examples should match the template single-quote convention."""
    stale_patterns = (
        '"[[wiki-links]]"',
        '"[[related-file]]"',
        'tags: ["#',
    )
    checked_roots = (
        BUILTINS_ROOT / "skills",
        BUILTINS_ROOT / "agents",
        BUILTINS_ROOT / "rules",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(BUILTINS_ROOT)}: {pattern}")

    assert offenders == []
