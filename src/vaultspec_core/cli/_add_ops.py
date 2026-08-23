"""Operations backing ``vaultspec-core vault add``.

The ``add`` verb is the single ingress for scaffolding ``.vault/`` records, so
its Typer callback in :mod:`.vault_cmd` carries a wide option surface and a
long validate-resolve-scaffold-emit sequence. This module owns the sequence:
each helper validates or resolves one input, renders its own operator message,
and raises :class:`typer.Exit` on refusal, leaving the callback as the ordered
composition of those steps.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from typing import TYPE_CHECKING, NoReturn, cast

import typer

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence
    from pathlib import Path

    from rich.console import Console

    from vaultspec_core.cli.rendering import OutcomeItem
    from vaultspec_core.plan.parser import Plan, Step
    from vaultspec_core.vaultcore.hydration import (
        DocumentIdentity,
        ParentPlan,
        TemplateFields,
        WritePolicy,
    )
    from vaultspec_core.vaultcore.models import DocType
    from vaultspec_core.vaultcore.query import VaultDocument

#: Plan tiers accepted by ``--tier``.
_PLAN_TIERS = frozenset({"L1", "L2", "L3", "L4"})


def fail(console: Console, message: str) -> NoReturn:
    """Render an operator error and exit with code 1."""
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


def resolve_doc_type(console: Console, doc_type: str) -> DocType:
    """Resolve the positional document-type argument to its enum member."""
    from vaultspec_core.vaultcore.models import DocType

    try:
        dt = DocType(doc_type)
    except ValueError:
        valid = ", ".join(d.value for d in DocType if d is not DocType.INDEX)
        console.print(
            f"[red]Unknown document type '{doc_type}'. Valid types: {valid}[/red]"
        )
        raise typer.Exit(code=1) from None
    if dt is DocType.INDEX:
        console.print(
            "[red]'index' documents are auto-generated. "
            "Use 'vaultspec-core vault feature index' instead of "
            "'vaultspec-core vault add index'.[/red]"
        )
        raise typer.Exit(code=1)
    return dt


def validate_step_flags(
    console: Console,
    dt: DocType,
    *,
    step: str | None,
    all_steps: bool,
    summary: bool,
    phase: str | None,
) -> None:
    """Reject step-aware flag combinations the scaffolder cannot honour."""
    from vaultspec_core.vaultcore.models import DocType

    step_route = step is not None or all_steps or summary
    if step_route and dt is not DocType.EXEC:
        fail(
            console,
            "Error: --step, --all-steps, and --summary options are only "
            "valid when creating 'exec' documents.",
        )
    if step is not None and all_steps:
        fail(console, "Error: --step and --all-steps options are mutually exclusive.")
    if summary and (step is not None or all_steps):
        fail(
            console,
            "Error: --summary cannot be combined with --step or --all-steps.",
        )
    if summary and phase is None:
        fail(
            console,
            "Error: --summary requires --phase <P##> naming the Phase to summarise.",
        )
    if phase is not None and not summary:
        fail(console, "Error: --phase is only valid together with --summary.")


def validate_tier(console: Console, dt: DocType, tier: str) -> None:
    """Reject an out-of-range ``--tier`` value on a plan document."""
    from vaultspec_core.vaultcore.models import DocType

    if dt is DocType.PLAN and tier not in _PLAN_TIERS:
        fail(console, f"Invalid tier '{tier}'. Allowed values: L1, L2, L3, L4.")


def normalize_topic(console: Console, dt: DocType, topic: str | None) -> str | None:
    """Validate the narrative filename infix for the doc types that admit one.

    The topic is held to the same kebab-case discipline as the feature tag.
    """
    from vaultspec_core.vaultcore.models import DocType
    from vaultspec_core.vaultcore.normalize import normalize_feature_tag

    if topic is None:
        return None
    if dt not in (DocType.ADR, DocType.AUDIT, DocType.REFERENCE, DocType.RESEARCH):
        fail(
            console,
            "Error: --topic is only valid for 'adr', 'audit', 'reference', "
            "and 'research' documents.",
        )
    result = normalize_feature_tag(topic, label="topic")
    if not result.ok or result.value is None:
        fail(console, str(result.error))
    return result.value


def normalize_feature(console: Console, feature: str) -> str:
    """Validate the feature tag through the shared vaultcore normalizer.

    The one validator the MCP surface also converges on.
    """
    from vaultspec_core.vaultcore.normalize import normalize_feature_tag

    result = normalize_feature_tag(feature)
    if not result.ok or result.value is None:
        fail(console, str(result.error))
    return result.value


def normalize_extra_tags(console: Console, tags: list[str] | None) -> list[str] | None:
    """Validate additional ``--tags`` through the same shared normalizer."""
    from vaultspec_core.vaultcore.normalize import normalize_feature_tag

    if not tags:
        return None
    extra_tags: list[str] = []
    for tag in tags:
        result = normalize_feature_tag(tag, label="tag")
        if not result.ok:
            fail(console, str(result.error))
        extra_tags.append(f"#{result.value}")
    return extra_tags


def resolve_related(
    console: Console, related: list[str] | None, root_dir: Path
) -> list[str] | None:
    """Resolve ``--related`` inputs to ``[[wiki-link]]`` form."""
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
    )

    if not related:
        return None
    try:
        return resolve_related_inputs(related, root_dir)
    except RelatedResolutionError as exc:
        for failure in exc.failures:
            console.print(f"[red]Cannot resolve related document: '{failure}'[/red]")
        console.print(
            "[dim]Accepted formats: absolute path, relative path, "
            "filename, stem, or [[wiki-link]][/dim]"
        )
        raise typer.Exit(code=1) from None


def report_dependency_diagnostics(
    console: Console,
    root_dir: Path,
    dt: DocType,
    feature: str,
    *,
    json_output: bool,
) -> None:
    """Emit the feature-lifecycle diagnostics and stop on any hard error."""
    from vaultspec_core.vaultcore.resolve import validate_feature_dependencies

    diagnostics = validate_feature_dependencies(root_dir, dt, feature)
    errors = [d for d in diagnostics if d.startswith("ERROR:")]

    if json_output:
        _echo_dependency_json(diagnostics, errors)
    else:
        _print_dependency_text(console, diagnostics)

    if errors:
        raise typer.Exit(code=1)


def _print_dependency_text(console: Console, diagnostics: Sequence[str]) -> None:
    """Print every lifecycle diagnostic, errors in red and advisories in yellow."""
    for diag in diagnostics:
        style = "red" if diag.startswith("ERROR:") else "yellow"
        console.print(f"[{style}]{diag}[/{style}]")


def _echo_dependency_json(diagnostics: Sequence[str], errors: Sequence[str]) -> None:
    """Route advisories to stderr and any errors to the failure envelope."""
    for diag in diagnostics:
        if not diag.startswith("ERROR:"):
            typer.echo(diag, err=True)
    if not errors:
        return

    import json

    from vaultspec_core.cli.rendering import json_envelope

    typer.echo(
        json.dumps(
            json_envelope("vault.add", "failed", {"message": " ".join(errors)}),
            indent=2,
        )
    )


def resolve_parent_plan(
    console: Console,
    root_dir: Path,
    feature: str,
    resolved_related: list[str] | None,
) -> VaultDocument:
    """Resolve the plan document an execution record belongs to.

    An explicit ``--related`` stem wins; otherwise the feature must own
    exactly one plan.
    """
    from vaultspec_core.vaultcore.query import list_documents

    named = _plan_named_by_related(root_dir, resolved_related)
    if named is not None:
        return named

    plan_docs = list_documents(root_dir, doc_type="plan", feature=feature)
    if len(plan_docs) == 1:
        return plan_docs[0]
    if len(plan_docs) > 1:
        names = ", ".join(d.path.name for d in plan_docs)
        fail(
            console,
            f"Multiple plans found for feature '{feature}': {names}. "
            "Specify the parent plan using --related.",
        )
    fail(
        console,
        f"No plan found for feature '{feature}'. "
        "Create a plan document before adding execution records.",
    )


def _plan_named_by_related(
    root_dir: Path, resolved_related: list[str] | None
) -> VaultDocument | None:
    """Return the first plan document named by a resolved wiki-link, if any."""
    from vaultspec_core.vaultcore.query import list_documents

    for rel in resolved_related or []:
        stem = rel.lstrip("[").rstrip("]")
        for doc in list_documents(root_dir, doc_type="plan"):
            if doc.path.stem == stem:
                return doc
    return None


def resolve_step_row(console: Console, plan: Plan, step: str) -> Step:
    """Resolve ``--step`` to one Step row of the parent plan."""
    from vaultspec_core.plan.commands.step_ops import (
        AmbiguousStepError,
        StepNotFoundError,
        find_step,
    )

    try:
        return find_step(plan, step)
    except (StepNotFoundError, AmbiguousStepError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from None


def resolve_phase_display_path(console: Console, plan: Plan, phase: str) -> str:
    """Resolve ``--phase`` to the summarised Phase's display path."""
    from vaultspec_core.plan.commands.phase_ops import PhaseNotFoundError, find_phase

    try:
        return find_phase(plan, phase).display_path
    except PhaseNotFoundError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from None


@contextmanager
def suppress_logging(*, active: bool) -> Generator[None]:
    """Silence library logging while a machine-readable payload is emitted."""
    import logging

    if not active:
        yield
        return
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)


def scaffold_all_steps(
    steps: Sequence[Step],
    *,
    root_dir: Path,
    identity: DocumentIdentity,
    fields: TemplateFields,
    plan: ParentPlan,
    write: WritePolicy,
    json_output: bool,
) -> int:
    """Scaffold one execution record per Step row and return the exit code."""
    from vaultspec_core.cli.rendering import emit_outcomes

    items: list[OutcomeItem] = []
    with suppress_logging(active=json_output):
        for step in steps:
            items.append(
                _scaffold_step_record(
                    step,
                    root_dir=root_dir,
                    identity=identity,
                    fields=fields,
                    plan=plan,
                    write=write,
                )
            )

    if not write.dry_run and items:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    return emit_outcomes(
        items,
        command="vault.add",
        title="Scaffold Execution Steps",
        json_output=json_output,
    )


def _scaffold_step_record(
    step: Step,
    *,
    root_dir: Path,
    identity: DocumentIdentity,
    fields: TemplateFields,
    plan: ParentPlan,
    write: WritePolicy,
) -> OutcomeItem:
    """Scaffold one Step's execution record and report its outcome."""
    from vaultspec_core.cli.rendering import Outcome, OutcomeItem
    from vaultspec_core.vaultcore.hydration import ExecBinding, create_vault_doc

    binding = ExecBinding(
        plan=plan,
        step_id=step.canonical_id,
        step_display_path=step.display_path,
        step_scope=step.scope,
        step_action=step.action,
    )

    # Resolve the target path first so the outcome can distinguish a fresh
    # record from an overwrite before anything is written.
    target_path = create_vault_doc(
        root_dir,
        identity,
        fields,
        exec_binding=binding,
        write=replace(write, force=True, dry_run=True),
    )
    rel_name = str(target_path.relative_to(root_dir))
    exists = target_path.exists()

    if exists and not write.force:
        return OutcomeItem(
            name=rel_name, outcome=Outcome.SKIPPED, detail="skipped; exists"
        )

    if exists:
        outcome = Outcome.UPDATED
        detail = "overwritten" if not write.dry_run else "would overwrite"
    else:
        outcome = Outcome.CREATED
        detail = "created" if not write.dry_run else "would create"

    if not write.dry_run:
        create_vault_doc(
            root_dir,
            identity,
            fields,
            exec_binding=binding,
            write=write,
        )

    return OutcomeItem(name=rel_name, outcome=outcome, detail=detail)


def emit_add_result(
    console: Console,
    path: Path,
    doc_type: str,
    *,
    json_output: bool,
    dry_run: bool = False,
    hints: Mapping[str, object] | None = None,
) -> None:
    """Emit the created (or previewed) document as text or the JSON envelope."""
    if not json_output:
        label = "[dim]Would create:[/dim]" if dry_run else "[green]Created:[/green]"
        console.print(f"{label} {path}")
        return

    import json

    from vaultspec_core.cli.rendering import json_envelope

    data: dict[str, object] = {
        "path": str(path),
        "type": doc_type,
        "name": path.stem,
    }
    if dry_run:
        data["dry_run"] = True
    typer.echo(
        json.dumps(
            json_envelope("vault.add", "created", data, hints=hints),
            indent=2,
        )
    )


def parse_row_specs(
    console: Console, specs: Sequence[str]
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Validate ``--row`` specs into ledger row cells.

    Each spec is ``OP:path`` (``A``, ``M``, ``D``) or ``R:old->new``. The
    scaffolder never infers an operation from disk state: an executor knows
    what it did, and guessing would record evidence nobody produced.

    Args:
        console: Console for the refusal message.
        specs: Raw ``--row`` values.

    Returns:
        The parsed ``(op, paths)`` pairs.

    Raises:
        typer.Exit: On a malformed spec, an unknown operation, or a rename
            missing one of its two paths.
    """
    parsed: list[tuple[str, tuple[str, ...]]] = []
    for spec in specs:
        op, separator, remainder = spec.partition(":")
        op = op.strip().upper()
        if not separator or not remainder.strip():
            _refuse_row(console, spec, "expected 'OP:path'")
        if op not in {"A", "M", "D", "R"}:
            _refuse_row(console, spec, f"unknown operation {op!r}; use A, M, D, or R")
        if op == "R":
            old, arrow, new = remainder.partition("->")
            if not arrow or not old.strip() or not new.strip():
                _refuse_row(console, spec, "a rename needs 'R:old->new'")
            parsed.append((op, (old.strip(), new.strip())))
        else:
            parsed.append((op, (remainder.strip(),)))
    return tuple(parsed)


def _refuse_row(console: Console, spec: str, reason: str) -> NoReturn:
    """Refuse a malformed ``--row`` spec with an actionable message."""
    console.print(f"[red]Error:[/red] invalid --row {spec!r}: {reason}.")
    raise typer.Exit(code=1)


def log_ledger_rows(
    console: Console,
    *,
    root_dir: Path,
    feature: str,
    plan_stem: str,
    step: str,
    rows: Sequence[tuple[str, tuple[str, ...]]],
    dry_run: bool,
    json_output: bool,
) -> Path:
    """Create the plan's ledger if absent, then append *step*'s rows to it.

    Creating and appending are one operation because the ledger is
    append-only: an executor logging its first Step must not have to know
    whether the document already exists. The append routes through
    :func:`~vaultspec_core.vaultcore.models.refresh_modified_stamp`, the
    mandated mutator helper, so the ``modified:`` stamp and the
    ``body_hash:`` re-attestation stay paired.

    Args:
        console: Console for operator messages.
        root_dir: Project root directory.
        feature: Feature tag, with or without a leading ``#``.
        plan_stem: Stem of the parent plan the ledger records.
        step: Canonical Step identifier or display path being logged.
        rows: Parsed ``(op, paths)`` pairs from :func:`parse_row_specs`.
        dry_run: Resolve and report the target without writing.
        json_output: Suppress the human-readable confirmation line.

    Returns:
        The ledger's path.
    """
    import datetime as _dt

    from vaultspec_core.core.helpers import atomic_write
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.vaultcore.exec_ledger import append_rows, format_row
    from vaultspec_core.vaultcore.hydration import (
        DocumentIdentity,
        ExecBinding,
        ParentPlan,
        TemplateFields,
        WritePolicy,
        create_vault_doc,
    )
    from vaultspec_core.vaultcore.models import (
        DocType,
        refresh_modified_stamp,
    )

    feat = normalize_feature(console, feature)
    plan_doc = resolve_parent_plan(console, root_dir, feat, [plan_stem])
    parsed_plan = parse_plan(plan_doc.path)
    target_step = resolve_step_row(console, parsed_plan, step)

    plan = ParentPlan(
        date=plan_doc.date or plan_doc.path.stem[:10], stem=plan_doc.path.stem
    )
    identity = DocumentIdentity(
        doc_type=DocType.EXEC, feature=feat, date=plan.date or ""
    )
    binding = ExecBinding(plan=plan, ledger=True)
    fields = TemplateFields()

    # Resolve the path without writing so an existing ledger is appended to,
    # never overwritten - a rewrite would discard other Steps' history.
    ledger_path = create_vault_doc(
        root_dir,
        identity,
        fields,
        exec_binding=binding,
        write=WritePolicy(force=True, dry_run=True),
    )
    if dry_run:
        if not json_output:
            console.print(f"[dim]Would log {len(rows)} row(s) to:[/dim] {ledger_path}")
        return ledger_path

    if not ledger_path.exists():
        create_vault_doc(
            root_dir,
            identity,
            fields,
            exec_binding=binding,
            write=WritePolicy(force=False, dry_run=False),
        )

    if not rows:
        return ledger_path

    text = ledger_path.read_text(encoding="utf-8")
    rendered = [format_row(target_step.canonical_id, op, *paths) for op, paths in rows]
    # Appended against the whole document, not a split-off body: frontmatter is
    # YAML and can never carry a '## Changes' heading, so the section match is
    # unambiguous and no fragile head/body reassembly is needed.
    try:
        updated = append_rows(text, rendered)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}.")
        raise typer.Exit(code=1) from exc

    if updated != text:
        atomic_write(ledger_path, refresh_modified_stamp(updated, _dt.date.today()))

    if not json_output:
        console.print(
            f"[green]Logged:[/green] {len(rendered)} row(s) for "
            f"{target_step.canonical_id} -> {ledger_path.name}"
        )
    return ledger_path


def fold_exec_records(
    console: Console,
    *,
    root_dir: Path,
    feature: str,
    dry_run: bool,
    force: bool,
    json_output: bool,
) -> tuple[Path | None, object]:
    """Fold one feature's per-Step execution records into a single ledger.

    The fold is destructive - it removes the records whose content the
    ledger now carries - so it refuses to write without ``--force``, and
    reports exactly what it would do instead. What a dry run prints and what
    a forced run applies come from one planner, so the preview is the plan.

    Args:
        console: Console for operator messages.
        root_dir: Project root directory.
        feature: Feature tag, with or without a leading ``#``.
        dry_run: Report the plan without writing.
        force: Required to apply a destructive fold.
        json_output: Suppress human-readable lines.

    Returns:
        The ``(ledger_path, plan)`` pair; ``ledger_path`` is ``None`` when
        nothing was folded.

    Raises:
        typer.Exit: When the feature has no execution folder, or when a
            non-dry run was requested without ``--force``.
    """
    import datetime as _dt

    from vaultspec_core.config import get_config
    from vaultspec_core.core.helpers import atomic_write
    from vaultspec_core.vaultcore.checks.exec_mapping import link_stem
    from vaultspec_core.vaultcore.exec_fold import plan_fold, sources_from, summarize
    from vaultspec_core.vaultcore.exec_ledger import append_rows
    from vaultspec_core.vaultcore.hydration import (
        DocumentIdentity,
        ExecBinding,
        ParentPlan,
        TemplateFields,
        WritePolicy,
        create_vault_doc,
    )
    from vaultspec_core.vaultcore.models import DocType, refresh_modified_stamp
    from vaultspec_core.vaultcore.parser import parse_frontmatter

    feat = normalize_feature(console, feature)
    exec_root = root_dir / get_config().docs_dir / "exec"
    folders = sorted(p for p in exec_root.glob(f"*-{feat}") if p.is_dir())
    if not folders:
        console.print(
            f"[red]Error:[/red] no execution folder found for feature {feat!r}."
        )
        raise typer.Exit(code=1)

    folder = folders[0]
    records: list[tuple[Path, str | None, str]] = []
    plan_stems: list[str] = []
    for path in sorted(folder.glob("*.md")):
        try:
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        raw = meta.get("step_id")
        step_id = str(raw).strip() if raw else None
        records.append((path, step_id, body))
        # Frontmatter is untyped JSON-ish data, so the related list is
        # narrowed explicitly rather than iterated as Any.
        raw_related: object = meta.get("related")
        related: tuple[object, ...] = (
            tuple(cast("list[object]", raw_related))
            if isinstance(raw_related, list)
            else ()
        )
        for link in related:
            stem = link_stem(str(link))
            if stem and stem.endswith("-plan"):
                plan_stems.append(stem)

    plan = plan_fold(sources_from(records))
    if not json_output:
        console.print(summarize(plan, folder.name))
        for skip in plan.skipped:
            console.print(f"  [dim]skip[/dim] {skip.path.name} - {skip.reason}")

    if plan.is_empty:
        return None, plan

    if not force:
        console.print(
            "[yellow]Refusing to fold without --force:[/yellow] this removes "
            f"{len(plan.folded)} record(s). Re-run with --force to apply, or "
            "--dry-run to silence this."
        )
        raise typer.Exit(code=1)

    plan_stem = plan_stems[0] if plan_stems else f"{folder.name}-plan"
    folder_date = folder.name[:10]
    parent = ParentPlan(date=folder_date, stem=plan_stem)
    identity = DocumentIdentity(doc_type=DocType.EXEC, feature=feat, date=folder_date)
    binding = ExecBinding(plan=parent, ledger=True)
    fields = TemplateFields()

    ledger_path = create_vault_doc(
        root_dir,
        identity,
        fields,
        exec_binding=binding,
        write=WritePolicy(force=True, dry_run=True),
    )
    if dry_run:
        if not json_output:
            console.print(f"[dim]Would write:[/dim] {ledger_path}")
        return ledger_path, plan

    if not ledger_path.exists():
        create_vault_doc(
            root_dir,
            identity,
            fields,
            exec_binding=binding,
            write=WritePolicy(force=False, dry_run=False),
        )

    text = ledger_path.read_text(encoding="utf-8")
    updated = append_rows(text, plan.rows)
    if updated != text:
        atomic_write(ledger_path, refresh_modified_stamp(updated, _dt.date.today()))

    # Remove folded records only after the ledger carrying their content is
    # durably on disk, so an interruption leaves duplication rather than loss.
    for path in plan.folded:
        if path != ledger_path:
            path.unlink(missing_ok=True)

    if not json_output:
        console.print(
            f"[green]Folded:[/green] {len(plan.folded)} record(s) into "
            f"{ledger_path.name}"
        )
    return ledger_path, plan
