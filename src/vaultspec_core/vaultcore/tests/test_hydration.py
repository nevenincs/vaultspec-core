"""Tests for vault document template hydration."""

import logging

import pytest

from vaultspec_core.core.exceptions import ResourceExistsError
from vaultspec_core.vaultcore import hydrate_template
from vaultspec_core.vaultcore.hydration import create_vault_doc
from vaultspec_core.vaultcore.models import DocType

pytestmark = [pytest.mark.unit]


def test_hydrate_template_basic():
    """Verify that placeholders in a template are correctly replaced."""
    template = """---
tags: ["#adr", "#{feature}"]
date: {yyyy-mm-dd}
---

# {title}
"""
    result = hydrate_template(template, "my-feature", "2026-03-01", title="My Title")

    assert 'tags: ["#adr", "#my-feature"]' in result
    assert "date: 2026-03-01" in result
    assert "# My Title" in result


def test_hydrate_template_placeholders():
    """Verify supported placeholders and the topic alias are hydrated."""
    template = "{feature} {yyyy-mm-dd} {title} {topic}"
    result = hydrate_template(template, "feat", "2026-02-01", title="Plan Title")
    assert result == "feat 2026-02-01 Plan Title Plan Title"


def test_hydrate_template_leaves_missing_title_and_warns(caplog):
    """Verify unresolved placeholders remain when optional title is omitted."""
    template = "{feature} {title}"
    with caplog.at_level(logging.WARNING):
        result = hydrate_template(template, "adr", "2026-03-01")

    assert result == "adr {title}"
    assert "Potential unhydrated placeholder found in template: {title}" in caplog.text


def test_hydrate_template_skips_placeholders_inside_html_comments(caplog):
    """Tokens inside HTML guidance comments do not raise unhydrated warnings.

    The framework templates carry human-facing guidance like
    ``<!-- Reference {adr}, {research}, {reference} for context -->`` that
    is meant for the author and not for placeholder substitution. The
    warning that flags genuinely unhydrated frontmatter placeholders must
    not fire against tokens inside those comment regions.
    """
    template = (
        "tags: ['#adr', '#{feature}']\n"
        "<!-- Reference {adr}, {research}, {reference} for context.\n"
        "     Multi-line comments must also be skipped. -->\n"
        "body has no genuine placeholders\n"
    )
    with caplog.at_level(logging.WARNING):
        result = hydrate_template(template, "feat", "2026-05-19")
    assert "#feat" in result
    assert "Potential unhydrated placeholder" not in caplog.text


def test_hydrate_template_substitutes_tier_when_passed():
    """Verify the {tier} placeholder is hydrated when tier is supplied."""
    template = "tier: {tier}"
    result = hydrate_template(template, "feat", "2026-05-18", tier="L3")
    assert result == "tier: L3"


def test_hydrate_template_substitutes_mdformat_normalized_tier():
    """Verify mdformat-normalized plan templates still hydrate tier."""
    template = "tier: {tier: null}"
    result = hydrate_template(template, "feat", "2026-05-18", tier="L3")
    assert result == "tier: L3"


def test_hydrate_template_leaves_tier_unhydrated_when_none(caplog):
    """Verify {tier} stays as-is when tier is not provided, with warning."""
    template = "tier: {tier}"
    with caplog.at_level(logging.WARNING):
        result = hydrate_template(template, "feat", "2026-05-18")
    assert result == "tier: {tier}"
    assert "Potential unhydrated placeholder found in template: {tier}" in caplog.text


def test_hydrate_template_warns_on_mdformat_normalized_tier(caplog):
    """Verify mdformat-normalized tier placeholders still emit diagnostics."""
    template = "tier: {tier: null}"
    with caplog.at_level(logging.WARNING):
        result = hydrate_template(template, "feat", "2026-05-18")
    assert result == "tier: {tier: null}"
    assert (
        "Potential unhydrated placeholder found in template: {tier: null}"
        in caplog.text
    )


def test_create_vault_doc_plan_substitutes_tier(tmp_path):
    """End-to-end: vault add plan with tier writes the supplied tier value."""
    from vaultspec_core.builtins import seed_builtins

    rules_dir = tmp_path / ".vaultspec" / "rules"
    rules_dir.mkdir(parents=True)
    seed_builtins(rules_dir, force=True)
    for dt in DocType:
        (tmp_path / ".vault" / dt.value).mkdir(parents=True, exist_ok=True)

    path = create_vault_doc(
        tmp_path,
        DocType.PLAN,
        "tier-test",
        "2026-05-18",
        title="Tier test",
        tier="L3",
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "tier: L3" in content
    assert "tier: L{#}" not in content
    assert "tier: {tier}" not in content


def test_emit_time_validator_rejects_invalid_plan_tier(tmp_path):
    """A plan template that hydrates to an invalid tier value must refuse to write.

    Exercises the scaffolder-integrity invariant: scaffolders never write
    content the framework's own validator would reject. Closes umbrella
    plan W01.P03.S07.
    """
    from vaultspec_core.builtins import seed_builtins
    from vaultspec_core.vaultcore.hydration import (
        ScaffoldValidationError,
        _assert_scaffolded_content_valid,
    )

    rules_dir = tmp_path / ".vaultspec" / "rules"
    rules_dir.mkdir(parents=True)
    seed_builtins(rules_dir, force=True)

    # Hand-craft a hydrated plan body whose frontmatter would crash the
    # parse path. This is exactly the B2-shape antipattern.
    invalid_plan = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-tier'\n"
        "date: '2026-05-19'\n"
        "tier: L{#}\n"
        "related: []\n"
        "---\n"
        "# `bad-tier` plan\n"
    )
    with pytest.raises(ScaffoldValidationError, match="frontmatter validator"):
        _assert_scaffolded_content_valid(invalid_plan, DocType.PLAN)


def test_emit_time_validator_accepts_valid_plan(tmp_path):
    """A well-formed plan passes the emit-time validator without raising."""
    from vaultspec_core.vaultcore.hydration import _assert_scaffolded_content_valid

    valid_plan = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#good-tier'\n"
        "date: '2026-05-19'\n"
        "tier: L1\n"
        "related: []\n"
        "---\n"
        "# `good-tier` plan\n"
    )
    # Should not raise.
    _assert_scaffolded_content_valid(valid_plan, DocType.PLAN)


def test_create_vault_doc_plan_default_tier_l1(tmp_path):
    """Plan scaffolded without explicit tier still hydrates cleanly when L1 passed."""
    from vaultspec_core.builtins import seed_builtins

    rules_dir = tmp_path / ".vaultspec" / "rules"
    rules_dir.mkdir(parents=True)
    seed_builtins(rules_dir, force=True)
    for dt in DocType:
        (tmp_path / ".vault" / dt.value).mkdir(parents=True, exist_ok=True)

    path = create_vault_doc(
        tmp_path,
        DocType.PLAN,
        "tier-default",
        "2026-05-18",
        title="Default tier",
        tier="L1",
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "tier: L1" in content


class TestCreateVaultDocStemCollision:
    """Ensure vault add rejects files whose stem collides with an existing doc."""

    @pytest.fixture()
    def vault_project(self, tmp_path):
        """Scaffold a minimal vault with one existing doc and real templates.

        Uses seed_builtins to copy real templates - never shadows them.
        """
        from vaultspec_core.builtins import seed_builtins

        rules_dir = tmp_path / ".vaultspec" / "rules"
        rules_dir.mkdir(parents=True)
        seed_builtins(rules_dir, force=True)

        # Create vault type directories
        for dt in DocType:
            (tmp_path / ".vault" / dt.value).mkdir(parents=True, exist_ok=True)

        # Create an existing vault document with a known stem
        (tmp_path / ".vault" / "adr" / "2026-03-17-my-feat-adr.md").write_text(
            "---\ntags:\n  - '#adr'\n  - '#my-feat'\n"
            "date: '2026-03-17'\nrelated: []\n---\n# Existing\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_exact_path_collision_rejected(self, vault_project):
        """Re-creating the same file raises ResourceExistsError."""
        with pytest.raises(ResourceExistsError, match="already exists"):
            create_vault_doc(
                vault_project,
                DocType.ADR,
                "my-feat",
                "2026-03-17",
                title="Duplicate",
            )

    def test_cross_type_stem_collision_rejected(self, vault_project):
        """A different type dir but same stem is rejected."""
        # Manually place a file in research/ with the same stem as
        # the ADR we're about to create
        research_dir = vault_project / ".vault" / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        (research_dir / "2026-03-18-new-feat-research.md").write_text(
            "---\ntags: ['#research', '#new-feat']\n---\n",
            encoding="utf-8",
        )

        # Place a file with stem "2026-03-20-collide-adr" in research/
        (research_dir / "2026-03-20-collide-adr.md").write_text(
            "---\ntags: ['#research']\n---\n",
            encoding="utf-8",
        )

        # Now create an ADR that generates stem "2026-03-20-collide-adr"
        with pytest.raises(ResourceExistsError, match=r"stem.*already exists"):
            create_vault_doc(
                vault_project,
                DocType.ADR,
                "collide",
                "2026-03-20",
                title="Collision",
            )

    def test_unique_stem_succeeds(self, vault_project):
        """A truly unique stem creates the file without error."""
        path = create_vault_doc(
            vault_project,
            DocType.ADR,
            "unique-feat",
            "2026-03-20",
            title="Unique",
        )
        assert path.exists()
        assert path.stem == "2026-03-20-unique-feat-adr"
