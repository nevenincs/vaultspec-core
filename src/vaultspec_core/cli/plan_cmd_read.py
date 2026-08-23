"""Read-only ``vault plan`` commands: ``status``, ``check``, ``query``.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.plan_app`. Split out of
:mod:`vaultspec_core.cli.plan_cmd` as the seam between read-only inspection
commands (no typed-error decorator, no plan mutation) and the container-level
mutating verbs, which each live in their own sibling module.
"""

import json
import sys
from typing import Annotated

import typer

from vaultspec_core.cli._target import PlanPathArg, TargetOption
from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.cli.plan_cmd_app import plan_app

__all__ = ["cmd_check", "cmd_query", "cmd_status"]


@plan_app.command("status")
def cmd_status(
    path: PlanPathArg,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON instead of human form")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Report plan health, structure, and completion."""
    from vaultspec_core.cli._target import apply_target

    apply_target(target)

    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.status import collect_status, status_to_json_dict

    plan = parse_plan(path)
    status = collect_status(plan, root_dir=_get_ctx().target_dir)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        envelope = json_envelope(
            "vault.plan.status", "unchanged", status_to_json_dict(status)
        )
        typer.echo(json.dumps(envelope, **json_format_kwargs()))
        return

    typer.echo(f"Plan: {path}")
    typer.echo(f"Tier: {status.tier.value}")
    if status.legacy_tier_default:
        typer.echo(
            "  (legacy plan; tier defaulted to L2 - run a writer to add the field)"
        )
    typer.echo(
        f"Counts: {status.wave_count} Waves, {status.phase_count} Phases, "
        f"{status.step_count} Steps"
    )
    typer.echo(
        f"Completion: {status.steps_completed} of {status.step_count} "
        f"({status.completion_percent}%)"
    )
    if status.exec_missing_ids:
        missing_ids_str = ", ".join(status.exec_missing_ids)
        hint = typer.style(
            f"! exec-missing: checked steps lacking execution records: "
            f"{missing_ids_str}",
            fg=typer.colors.YELLOW,
        )
        typer.echo(hint)


@plan_app.command("check")
def cmd_check(
    path: PlanPathArg,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Apply autofixable transformations idempotently"),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit findings as JSON")
    ] = False,
) -> None:
    """Validate convention compliance; with ``--fix``, apply autofixes."""
    from vaultspec_core.core.helpers import atomic_write
    from vaultspec_core.plan.checks import collect_all, has_errors
    from vaultspec_core.plan.fixes import apply_all_fixes
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.vaultcore import refresh_modified_stamp, vault_today

    text = path.read_text(encoding="utf-8")

    if fix:
        repaired = apply_all_fixes(text)
        if repaired != text:
            # An autofix is a mutation, so it carries the same provenance
            # obligation as every other mutating verb (vault-orientation ADR
            # decision D3): refresh ``modified:`` and re-attest ``body_hash:``
            # from the repaired text. Without this the repair would land a
            # body the stored fingerprint no longer describes, and the
            # document would immediately read as hand-edited to the
            # modified-stamp reconciliation check.
            repaired = refresh_modified_stamp(repaired, vault_today())
            # Routed through atomic_write, not Path.write_text, for two
            # reasons. It writes the encoded bytes verbatim, where text mode
            # would translate every ``\n`` into ``\r\n`` on Windows and leave
            # the repaired document failing the project's LF-only markdown
            # format gate. And it replaces the file atomically, so a repair
            # interrupted mid-write leaves the previous document intact
            # rather than a truncated plan - the same guarantee every other
            # plan write path already carries (issue #296).
            atomic_write(path, repaired)
        text = repaired

    plan = parse_plan(text)
    findings = collect_all(plan, text)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        findings_data = [
            {
                "code": f.code,
                "severity": f.severity.value,
                "message": f.message,
                "line": f.line_number,
                "fix_hint": f.fix_hint,
                "autofixable": f.autofixable,
            }
            for f in findings
        ]
        status = "failed" if has_errors(findings) else "unchanged"
        envelope = json_envelope(
            "vault.plan.check", status, {"findings": findings_data}
        )
        typer.echo(json.dumps(envelope, **json_format_kwargs()))
    else:
        for finding in findings:
            typer.echo(
                f"[{finding.severity.value}] {finding.code} "
                f"line {finding.line_number}: {finding.message}"
            )
            # Surface the fix hint in the text output too - it used to be
            # reachable only via --json - and label whether --fix can
            # apply it or the operator must act manually.
            if finding.fix_hint:
                tag = "autofix" if finding.autofixable else "manual"
                typer.echo(f"  fix ({tag}): {finding.fix_hint}")

    if has_errors(findings):
        sys.exit(1)


@plan_app.command("query")
def cmd_query(
    path: PlanPathArg,
    open_only: Annotated[
        bool, typer.Option("--open", help="Only Steps with [ ] checkbox")
    ] = False,
    closed_only: Annotated[
        bool, typer.Option("--closed", help="Only Steps with [x] checkbox")
    ] = False,
    in_phase: Annotated[
        str | None, typer.Option("--phase", help="Restrict to Phase P##")
    ] = None,
    in_wave: Annotated[
        str | None, typer.Option("--wave", help="Restrict to Wave W##")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit matched Steps as JSON")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Filter Step rows by container scope and open/closed predicate."""
    from vaultspec_core.cli._target import apply_target
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.query import QueryFilter, query_steps

    apply_target(target)

    plan = parse_plan(path)
    result = query_steps(
        plan,
        QueryFilter(
            scope_phase=in_phase,
            scope_wave=in_wave,
            only_open=open_only,
            only_closed=closed_only,
        ),
    )
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        payload = {
            "matched": len(result.matched),
            "total": result.total,
            "steps": [
                {
                    "display_path": step.display_path,
                    "checked": step.checked,
                    "action": step.action,
                    "scope": step.scope,
                }
                for step in result.matched
            ],
        }
        typer.echo(
            json.dumps(
                json_envelope("vault.plan.query", "unchanged", payload),
                **json_format_kwargs(),
            )
        )
        return
    typer.echo(f"Matched {len(result.matched)} of {result.total} Steps:")
    for step in result.matched:
        state = "x" if step.checked else " "
        typer.echo(
            f"- [{state}] `{step.display_path}` - {step.action}; `{step.scope}`."
        )
