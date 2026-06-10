"""Hydrate templates and scaffold new `.vault/` documents.

This module is the write-side complement to parsing and scanning. It locates
templates, substitutes placeholders, and creates new vault records with the
expected structure and metadata shape.

Usage:
    Use `hydrate_template(...)` to render template content and
    `create_vault_doc(...)` to create a fully scaffolded vault document.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ..core.exceptions import ResourceExistsError
from .models import DocType

__all__ = ["get_template_path", "hydrate_template"]

logger = logging.getLogger(__name__)

_KNOWN_PLACEHOLDERS = (
    "{yyyy-mm-dd-*}",
    "[[{yyyy-mm-dd-*}]]",
    "{proposed|accepted|rejected|deprecated}",
)

# Prior on-disk filenames for templates that have since been renamed in the
# source tree. A deployed mirror that predates the rename still ships the old
# filename; :func:`get_template_path` falls back to these so the scaffolder
# keeps working on a not-yet-upgraded workspace.
#
# TODO(remove after the release following the first published release that
# ships reference.md): drop the ref-audit.md legacy fallback. The
# `ref-audit.md` -> `reference.md` rename has not shipped in a release yet
# (current version 0.1.26), so the grace path must survive one upgrade cycle
# before removal. See REVIEW-005 in the firmware-wording-review audit.
_LEGACY_TEMPLATE_NAMES = {
    DocType.REFERENCE: "ref-audit.md",
}

if TYPE_CHECKING:
    import pathlib


def hydrate_template(
    template_content: str,
    feature: str,
    date: str,
    title: str | None = None,
    *,
    related: list[str] | None = None,
    extra_tags: list[str] | None = None,
    tier: str | None = None,
    step_id: str | None = None,
    step_scope: str | None = None,
    step_action: str | None = None,
    plan_stem: str | None = None,
) -> str:
    """Replace placeholders in a template string with actual values.

    Supports both ``{key}`` and ``<key>`` placeholder styles.  Logs a
    warning for any placeholder that remains unresolved after substitution.

    When *related* is provided, the template's placeholder ``related:``
    entries are replaced with the resolved wiki-link list. When
    *extra_tags* is provided, those tags are appended to the ``tags:``
    block in frontmatter. When *tier* is provided, the template's
    ``{tier}`` placeholder is substituted; otherwise the placeholder
    is left as-is for the caller to fill.

    Args:
        template_content: Raw template text containing placeholder tokens.
        feature: Feature name in kebab-case (e.g. ``editor-demo``).
        date: ISO 8601 date string (e.g. ``2026-02-06``).
        title: Optional title that maps to the ``{title}`` and ``{topic}``
            placeholders.
        related: Pre-resolved ``[[wiki-link]]`` strings to inject into
            the ``related:`` frontmatter field.
        extra_tags: Additional ``#tag`` strings to append to the ``tags:``
            frontmatter field (beyond the directory and feature tags).
        tier: Optional plan tier value (``L1``..``L4``) substituted into
            the ``{tier}`` placeholder for plan templates.
        step_id: Optional step canonical identifier (e.g. ``S01``).
        step_scope: Optional file or area scope of the step.
        step_action: Optional verbatim action of the step.
        plan_stem: Optional parent plan stem used in wiki-links.

    Returns:
        The fully-hydrated document string.
    """
    hydrated = template_content

    # Normalize placeholders map
    placeholders = {
        "feature": feature,
        "yyyy-mm-dd": date,
        "date": date,
    }
    if title:
        placeholders["title"] = title
        placeholders["topic"] = title  # alias used in research template
        placeholders["phase"] = title  # alias used in plan/exec templates
        placeholders["step"] = title  # alias used in exec template
    if tier:
        placeholders["tier"] = tier

    # Perform replacements for both styles
    for key, value in placeholders.items():
        patterns = [f"{{{key}}}", f"<{key}>"]
        if key == "tier":
            # The plan template quotes the placeholder (`tier: '{tier}'`) so
            # YAML and mdformat treat it as a string; the quotes are stripped
            # on substitution to keep the scaffolded scalar unquoted. mdformat
            # parses a legacy unquoted `{tier}` YAML placeholder as an inline
            # map and normalizes it to `{tier: null}`.
            patterns.insert(0, "'{tier}'")
            patterns.append("{tier: null}")
        for pattern in patterns:
            if pattern in hydrated:
                logger.debug("Replacing '%s' with '%s'", pattern, value)
                hydrated = hydrated.replace(pattern, value)

    # Hydrate step-aware placeholders
    val_step_id = step_id if step_id is not None else "{S##}"
    val_plan_stem = plan_stem if plan_stem is not None else "{yyyy-mm-dd-*-plan}"

    if title is not None:
        val_heading = title
    elif step_action is not None:
        val_heading = step_action
    else:
        val_heading = f"{feature} <display-path>"

    val_scope_block = ""
    if step_scope:
        scopes = [
            s.strip().strip("`") for s in re.split(r"[,;]+", step_scope) if s.strip()
        ]
        if scopes:
            lines = ["## Scope", ""]
            for s in scopes:
                lines.append(f"- `{s}`")
            val_scope_block = "\n".join(lines)

    hydrated = hydrated.replace("{step_id}", val_step_id)
    hydrated = hydrated.replace("{plan_stem}", val_plan_stem)
    hydrated = hydrated.replace("{heading}", val_heading)
    hydrated = hydrated.replace("{scope_block}", val_scope_block)

    # Inject resolved related links into frontmatter
    if related is not None:
        hydrated = _inject_related(hydrated, related)

    # Inject extra tags into frontmatter
    if extra_tags:
        hydrated = _inject_extra_tags(hydrated, extra_tags)

    # Check for remaining placeholders that might have been missed.
    # Pattern matches {key} or <key> where key is alphanumeric with hyphens.
    # Strip HTML comment regions (<!-- ... -->) first: tokens inside those
    # are intentional template guidance for the human author, not
    # frontmatter placeholders. Without this, every freshly scaffolded
    # adr/plan/exec doc emits warnings about {adr}, {research},
    # {reference}, <display-path> etc. that live inside the template's
    # own guidance comments.
    scan_target = re.sub(r"<!--.*?-->", "", hydrated, flags=re.DOTALL)
    remaining = re.findall(r"[{<][a-z0-9\-_*]+[}>]", scan_target)
    if "{tier: null}" in scan_target:
        remaining.append("{tier: null}")
    if remaining:
        for placeholder in set(remaining):
            if placeholder in _KNOWN_PLACEHOLDERS:
                continue
            logger.warning(
                "Potential unhydrated placeholder found in template: %s",
                placeholder,
            )

    logger.debug("Successfully hydrated template (feature=%s)", feature)
    return hydrated


def _inject_related(content: str, related: list[str]) -> str:
    """Replace the ``related:`` block in YAML frontmatter with resolved links.

    Args:
        content: Full document text with YAML frontmatter.
        related: List of ``[[wiki-link]]`` strings.

    Returns:
        Document text with the ``related:`` field updated.
    """
    if not related:
        # Empty list - set related to empty
        new_block = "related: []"
    else:
        lines = ["related:"]
        for link in related:
            lines.append(f'  - "{link}"')
        new_block = "\n".join(lines)

    # Match the related: field and all its list items or inline empty list
    pattern = re.compile(
        r"^related:(?:[ \t]*\[\]|(?:\n[ \t]+- .*)*)",
        re.MULTILINE,
    )
    result = pattern.sub(new_block, content, count=1)
    return result


def _inject_extra_tags(content: str, extra_tags: list[str]) -> str:
    """Append additional tags to the ``tags:`` block in YAML frontmatter.

    Args:
        content: Full document text with YAML frontmatter.
        extra_tags: List of ``#tag`` strings to append.

    Returns:
        Document text with extra tags appended to the ``tags:`` field.
    """
    # Find the last tag entry line in the tags block
    # Tags block looks like:
    #   tags:
    #     - "#adr"
    #     - "#feature"
    # We want to insert after the last - "..." line in the tags block
    tag_lines = []
    for tag in extra_tags:
        normalized = tag if tag.startswith("#") else f"#{tag}"
        tag_lines.append(f'  - "{normalized}"')

    insertion = "\n".join(tag_lines)

    # Find the tags block and append after the last entry
    pattern = re.compile(
        r"(tags:\s*\n(?:\s+-\s+.*\n)*\s+-\s+.*)",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if match:
        return content[: match.end()] + "\n" + insertion + content[match.end() :]

    return content


def create_vault_doc(
    root_dir: pathlib.Path,
    doc_type: DocType,
    feature: str,
    date_str: str,
    title: str | None = None,
    *,
    related: list[str] | None = None,
    extra_tags: list[str] | None = None,
    content_root: pathlib.Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    tier: str | None = None,
    step_id: str | None = None,
    step_display_path: str | None = None,
    step_scope: str | None = None,
    step_action: str | None = None,
    plan_date: str | None = None,
    plan_stem: str | None = None,
) -> pathlib.Path:
    """Scaffold a new vault document from the appropriate template.

    Args:
        root_dir: Project root (output_root from workspace layout).
        doc_type: The type of vault document to create.
        feature: Feature name in kebab-case (leading ``#`` stripped).
        date_str: ISO 8601 date string (e.g. ``2026-02-06``).
        title: Optional document title.
        related: Pre-resolved ``[[wiki-link]]`` strings for the
            ``related:`` frontmatter field.
        extra_tags: Additional ``#tag`` strings to append to ``tags:``.
        content_root: Explicit content root for template lookup.
        force: If ``True``, overwrite an existing document.
        dry_run: If ``True``, return the target path without writing.
        tier: Plan tier value (``L1``..``L4``) substituted into the plan
            template's ``{tier}`` placeholder. Ignored for non-plan
            doc types whose templates do not carry the placeholder.
        step_id: Optional step canonical identifier (e.g. ``S01``).
        step_display_path: Optional display path of the step.
        step_scope: Optional file or area scope of the step.
        step_action: Optional verbatim action of the step.
        plan_date: Optional parent plan date.
        plan_stem: Optional parent plan stem used in wiki-links.

    Returns:
        Path to the newly created (or would-be-created) document.

    Raises:
        FileNotFoundError: If no template exists for the given ``doc_type``.
        ResourceExistsError: If the target file already exists and
            *force* is ``False``.
    """
    from ..config import get_config

    template_path = get_template_path(root_dir, doc_type, content_root=content_root)
    if template_path is None:
        raise FileNotFoundError(
            f"No template found for type '{doc_type.value}'. The deployed "
            "template mirror is missing or stale; run "
            "`vaultspec-core install --upgrade` to refresh it."
        )

    content = template_path.read_text(encoding="utf-8")

    # Default to empty related list so created documents pass validation
    # instead of keeping template placeholder entries like [[{yyyy-mm-dd-*}]]
    effective_related = list(related) if related is not None else []
    if plan_stem:
        plan_link = f"[[{plan_stem}]]"
        if plan_link not in effective_related:
            effective_related.insert(0, plan_link)

    hydrated = hydrate_template(
        content,
        feature,
        date_str,
        title,
        related=effective_related,
        extra_tags=extra_tags,
        tier=tier,
        step_id=step_id,
        step_scope=step_scope,
        step_action=step_action,
        plan_stem=plan_stem,
    )

    if doc_type is DocType.EXEC and step_id is not None:
        suffix = step_display_path.replace(".", "-") if step_display_path else "S01"
        filename = f"{plan_date or date_str}-{feature}-{suffix}.md"
        target_dir = (
            root_dir
            / get_config().docs_dir
            / doc_type.value
            / f"{plan_date or date_str}-{feature}"
        )
    else:
        filename = f"{date_str}-{feature}-{doc_type.value}.md"
        target_dir = root_dir / get_config().docs_dir / doc_type.value

    target_path = target_dir / filename

    if not force:
        if target_path.exists():
            raise ResourceExistsError(
                f"File already exists at {target_path}",
                hint="Use --force to overwrite",
            )

        # Guard against stem collisions  - a file with the same stem in a
        # different type directory would cause silent overwrites in the
        # graph (nodes are keyed by stem).
        stem = target_path.stem
        docs_dir = root_dir / get_config().docs_dir
        if docs_dir.exists():
            for existing in docs_dir.rglob("*.md"):
                if existing.stem == stem and existing != target_path:
                    raise ResourceExistsError(
                        f"A file with stem '{stem}' already exists at "
                        f"{existing.relative_to(root_dir)}. "
                        f"Choose a different name to avoid graph key collisions.",
                        hint="Use --force to overwrite",
                    )

    # Emit-time validator: refuse to write content the framework's own
    # validators would reject on the next read. Closes the
    # scaffolder-integrity invariant prescribed by the
    # cli-scaffolder-integrity ADR.
    _assert_scaffolded_content_valid(hydrated, doc_type)

    if dry_run:
        return target_path

    from ..core.helpers import atomic_write

    target_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(target_path, hydrated)
    logger.info("Created %s", target_path)
    return target_path


class ScaffoldValidationError(ValueError):
    """Raised when a scaffolded document would fail its own validator.

    The scaffolder must never write a document the framework's read-path
    validators would reject. When this exception fires, the failure is
    in the template + hydration pipeline, not in the operator's input.
    """


def _assert_scaffolded_content_valid(content: str, doc_type: DocType) -> None:
    """Validate hydrated scaffolder output before the write hits disk.

    Scope is deliberately narrow: this is the emit-time guard against
    the B2/B5-shape antipattern where a scaffolder writes content the
    next read-path command crashes on with an uncaught exception. It
    is not a general lint pass -- soft frontmatter advisories (extra
    tags, missing related entries) remain post-creation warnings via
    :func:`vaultspec_core.cli.vault_cmd._validate_created_doc` and are
    not blocking here.

    For plan documents the frontmatter is parsed with the same parser
    the read path uses; a failure (e.g. an invalid ``tier`` value)
    raises :class:`ScaffoldValidationError` and the scaffolder must
    not write. Other document types have no crash-on-parse frontmatter
    field today, so they pass through.
    """
    if doc_type is DocType.PLAN:
        try:
            from ..plan.frontmatter import parse_plan_frontmatter
        except ImportError:
            return
        try:
            parse_plan_frontmatter(content)
        except Exception as exc:
            msg = (
                "Scaffolded plan failed the framework's own frontmatter "
                f"validator: {exc}. The template + hydration pipeline "
                "produced content the next vault plan command would "
                "reject. This is a scaffolder bug; do not edit the file "
                "by hand."
            )
            raise ScaffoldValidationError(msg) from exc


def get_template_path(
    root_dir: pathlib.Path,
    doc_type: DocType,
    *,
    content_root: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """Return the filesystem path of the template file for a given DocType.

    Args:
        root_dir: Project root used to derive the framework directory when
            ``content_root`` is not provided.
        doc_type: The vault document type whose template is requested.
        content_root: Explicit content root (e.g. ``.vaultspec/``). Templates
            live in the content tree. When ``None``, falls back to
            ``root_dir / framework_dir``.

    Returns:
        Path to the template file, or ``None`` if the type has no mapping or
        the file does not exist on disk.
    """
    from ..config import get_config

    mapping = {
        DocType.ADR: "adr.md",
        DocType.AUDIT: "audit.md",
        DocType.PLAN: "plan.md",
        DocType.RESEARCH: "research.md",
        DocType.REFERENCE: "reference.md",
        DocType.EXEC: "exec-step.md",
        DocType.INDEX: "index.md",
    }

    name = mapping.get(doc_type)
    if not name:
        return None

    if content_root is not None:
        base = content_root
    else:
        cfg = get_config()
        base = root_dir / cfg.framework_dir

    templates_dir = base / "rules" / "templates"
    path = templates_dir / name
    if path.exists():
        return path

    # Legacy-filename fallback for renamed templates. A workspace whose
    # deployed mirror predates a template rename (for example a stale
    # `.vaultspec/rules/` that still ships `ref-audit.md` after the source
    # renamed it to `reference.md`) would otherwise resolve to a missing
    # file. Fall back to the prior filename so the verb keeps working on a
    # not-yet-upgraded workspace until the operator re-runs
    # `vaultspec-core install --upgrade`. See REVIEW-005 in the
    # firmware-wording-review audit.
    #
    # TODO(remove after the release following the first published release that
    # ships reference.md): drop this ref-audit.md legacy fallback branch.
    legacy_name = _LEGACY_TEMPLATE_NAMES.get(doc_type)
    if legacy_name is not None:
        legacy_path = templates_dir / legacy_name
        if legacy_path.exists():
            logger.warning(
                "Template '%s' for type '%s' is missing; falling back to the "
                "legacy filename '%s'. Run `vaultspec-core install --upgrade` "
                "to refresh the deployed mirror.",
                name,
                doc_type.value,
                legacy_name,
            )
            return legacy_path

    return None
