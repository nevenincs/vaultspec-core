"""Contract tests for checked-in vaultspec rule guidance."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[4]


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
    checked_roots = (PROJECT_ROOT / ".vaultspec" / "rules",)

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []


def test_rule_guidance_uses_canonical_file_placeholders() -> None:
    """Vault rule guidance should not use uppercase filename placeholders."""
    stale_patterns = (
        "YYYY-MM-DD-{Feature}",
        "YYYY-MM-DD-<Feature>",
    )
    checked_roots = (
        PROJECT_ROOT / ".vaultspec" / "rules" / "skills",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []


def test_code_review_guidance_persists_audit_artifacts() -> None:
    """Code-review reports use the audit template and audit directory."""
    checked_paths = (
        PROJECT_ROOT
        / ".vaultspec"
        / "rules"
        / "skills"
        / "vaultspec-code-review"
        / "SKILL.md",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents" / "vaultspec-code-reviewer.md",
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
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []


def test_exec_step_guidance_is_not_l2_only() -> None:
    """Step Record guidance must not hard-code the L2 phase-step shape."""
    stale_patterns = (
        ".vault/exec/yyyy-mm-dd-{feature}/yyyy-mm-dd-{feature}-{phase}-{step}.md",
        ".vault/exec/yyyy-mm-dd-<feature>/yyyy-mm-dd-<feature>-<phase>-<step>.md",
    )
    checked_roots = (
        PROJECT_ROOT / ".vaultspec" / "rules" / "skills",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []


def test_curator_guidance_matches_current_frontmatter_contract() -> None:
    """Curator instructions should not reintroduce removed YAML guidance."""
    checked_paths = (
        PROJECT_ROOT
        / ".vaultspec"
        / "rules"
        / "skills"
        / "vaultspec-curate"
        / "SKILL.md",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents" / "vaultspec-docs-curator.md",
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
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []


def test_rule_guidance_does_not_forbid_template_extra_tags() -> None:
    """Template guidance allows tags beyond the required pair."""
    checked_roots = (
        PROJECT_ROOT / ".vaultspec" / "rules" / "skills",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents",
        PROJECT_ROOT / ".vaultspec" / "rules" / "rules",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            if "EXACTLY TWO" in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: EXACTLY TWO")

    assert offenders == []


def test_rule_guidance_uses_template_quote_style() -> None:
    """Rule examples should match the template single-quote convention."""
    stale_patterns = (
        '"[[wiki-links]]"',
        '"[[related-file]]"',
        'tags: ["#',
    )
    checked_roots = (
        PROJECT_ROOT / ".vaultspec" / "rules" / "skills",
        PROJECT_ROOT / ".vaultspec" / "rules" / "agents",
        PROJECT_ROOT / ".vaultspec" / "rules" / "rules",
    )

    offenders: list[str] = []
    for root in checked_roots:
        for path in _existing_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in stale_patterns:
                if pattern in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert offenders == []
