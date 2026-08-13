"""Tier ``vault plan tier`` commands: show / promote / demote.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.tier_app`. Split out of
:mod:`vaultspec_core.cli.plan_cmd` along the tier-transition seam.
"""

import json
from typing import Annotated

import typer

from vaultspec_core.cli._target import PlanPathArg
from vaultspec_core.cli.plan_cmd_app import tier_app
from vaultspec_core.cli.plan_cmd_shared import (
    render_user_errors,
    save_plan_or_dry_run,
    serialise_plan_mutation,
)

__all__ = ["cmd_tier_demote", "cmd_tier_promote", "cmd_tier_show"]


@tier_app.command("show")
def cmd_tier_show(
    path: PlanPathArg,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the tier as JSON")
    ] = False,
) -> None:
    """Print the plan's declared tier."""
    from vaultspec_core.plan.commands.tier_ops import current_tier
    from vaultspec_core.plan.parser import parse_plan

    plan = parse_plan(path)
    tier = current_tier(plan).value
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope("vault.plan.tier.show", "unchanged", {"tier": tier}),
                indent=2,
            )
        )
        return
    typer.echo(tier)


@tier_app.command("promote")
@render_user_errors
@serialise_plan_mutation
def cmd_tier_promote(
    path: PlanPathArg,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Target tier (L2/L3/L4); defaults to one tier above current",
        ),
    ] = None,
    phase_title: Annotated[
        str | None,
        typer.Option("--phase-title", help="Title for the synthesised P01"),
    ] = None,
    phase_intent: Annotated[
        str | None,
        typer.Option("--phase-intent", help="Intent for the synthesised P01"),
    ] = None,
    wave_title: Annotated[
        str | None,
        typer.Option("--wave-title", help="Title for the synthesised W01"),
    ] = None,
    wave_intent: Annotated[
        str | None,
        typer.Option("--wave-intent", help="Intent for the synthesised W01"),
    ] = None,
    epic_intent: Annotated[
        str | None,
        typer.Option(
            "--epic-intent",
            help="Epic intent paragraph (must declare PM association)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Promote the plan tier transitively (L1 -> ... -> L4).

    Promotion paths that introduce new containers require explicit
    title/intent flags for those containers. L1 -> L2 requires
    ``--phase-title`` and ``--phase-intent``; L2 -> L3 requires
    ``--wave-title`` and ``--wave-intent``; L3 -> L4 requires
    ``--epic-intent``. Transitive promotions (e.g. L1 -> L4) require
    the union of the relevant flag sets. The CLI refuses to write
    ``TODO:`` placeholders into the plan document; the operator must
    supply real values up front.
    """
    from vaultspec_core.console import get_console
    from vaultspec_core.plan.commands.tier_ops import promote_tier
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import parse_plan

    console = get_console()

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    current_tier_value = plan.frontmatter.tier.value
    target_tier = Tier(target) if target is not None else None

    # Determine which transitions will be made and validate the matching
    # flag sets are populated. Refuses to substitute TODO placeholders.
    tier_order = ["L1", "L2", "L3", "L4"]
    if target_tier is None:
        # Default: advance one tier.
        try:
            current_idx = tier_order.index(current_tier_value)
        except ValueError:
            current_idx = 0
        if current_idx + 1 >= len(tier_order):
            target_value = current_tier_value
        else:
            target_value = tier_order[current_idx + 1]
    else:
        target_value = target_tier.value

    # An invalid current tier (e.g. a hand-mangled plan) must not silently
    # empty the transitions list and bypass the mandatory-flag checks:
    # default current_idx to 0 so every container-introducing tier up to
    # the target is still validated. target_value is always a valid tier
    # (derived from tier_order or a validated Tier), so its lookup is not
    # guarded.
    try:
        current_idx = tier_order.index(current_tier_value)
    except ValueError:
        current_idx = 0
    target_idx = tier_order.index(target_value)
    transitions = tier_order[current_idx + 1 : target_idx + 1]

    missing: list[str] = []
    if "L2" in transitions:
        if phase_title is None:
            missing.append("--phase-title")
        if phase_intent is None:
            missing.append("--phase-intent")
    if "L3" in transitions:
        if wave_title is None:
            missing.append("--wave-title")
        if wave_intent is None:
            missing.append("--wave-intent")
    if "L4" in transitions and epic_intent is None:
        missing.append("--epic-intent")

    if missing:
        console.print(
            f"[red]Cannot promote {current_tier_value} -> {target_value} "
            f"without the following flag(s): {', '.join(missing)}.[/red]"
        )
        console.print(
            "[dim]Each promotion path that introduces a new container "
            "requires its title/intent up front; the CLI does not write "
            "TODO placeholders into plan documents.[/dim]"
        )
        raise typer.Exit(code=1)

    new_tier = promote_tier(
        plan,
        target=target_tier,
        phase_title=phase_title,
        phase_intent=phase_intent,
        wave_title=wave_title,
        wave_intent=wave_intent,
        epic_intent=epic_intent,
    )
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Tier promoted to {new_tier.value}.",
        json_output=json_output,
        command="vault.plan.tier.promote",
    )


@tier_app.command("demote")
@render_user_errors
@serialise_plan_mutation
def cmd_tier_demote(
    path: PlanPathArg,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Target tier (L1/L2/L3); defaults to one tier below current",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Override the multi-child collapse refusal; descendant ids retire",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Demote the plan tier; refuses multi-child collapse without ``--force``."""
    from vaultspec_core.plan.commands.tier_ops import demote_tier
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    target_tier = Tier(target) if target is not None else None

    # Calculate expected_retired before we mutate the plan
    expected_retired: set[str] = set()
    current_t = plan.frontmatter.tier
    resolved_target = target_tier
    if resolved_target is None:
        # tier_ops._previous_tier is module-private; the ordering is stable
        # and small enough to mirror locally rather than reach into it.
        tier_order = (Tier.L1, Tier.L2, Tier.L3, Tier.L4)
        current_index = tier_order.index(current_t)
        resolved_target = tier_order[current_index - 1] if current_index > 0 else None

    if resolved_target is not None:
        if current_t in (Tier.L4, Tier.L3) and resolved_target is Tier.L2:
            expected_retired.update(w.canonical_id for w in plan.waves)
        elif current_t in (Tier.L4, Tier.L3, Tier.L2) and resolved_target is Tier.L1:
            expected_retired.update(w.canonical_id for w in plan.waves)
            expected_retired.update(p.canonical_id for p in plan.phases)

    new_tier = demote_tier(plan, target=target_tier, force=force)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Tier demoted to {new_tier.value}.",
        expected_retired=expected_retired,
        json_output=json_output,
        command="vault.plan.tier.demote",
    )
