"""``vaultspec-core spec precommit|gitignore|gitattributes`` - git-side policy.

Defines the three sub-groups that record whether vaultspec maintains its
boundary in a git-managed file: :data:`precommit_app` for the prek pre-commit
hooks, and :data:`gitignore_app` and :data:`gitattributes_app` for the managed
block in each of those files. All three are mounted by
:mod:`vaultspec_core.cli.spec_cmd` onto
:data:`~vaultspec_core.cli.spec_cmd_app.spec_app`.

These are git's hooks, not vaultspec's. They have nothing to do with the
agent-runtime hooks in :mod:`vaultspec_core.core.provider_hooks` or the
lifecycle triggers in :mod:`vaultspec_core.triggers`, and they lived beside the
latter only because all three once shared the word. Delegates to
:mod:`vaultspec_core.core` via lazy imports to avoid circular-import issues.
"""

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.spec_cmd_shared import emit_json

# =============================================================================
# Pre-commit boundary (prek)
# =============================================================================

precommit_app = make_app(
    help="Manage whether and where vaultspec's pre-commit hooks are scaffolded.",
    no_args_is_help=True,
)
gitignore_app = make_app(
    help="Manage whether vaultspec maintains its block in .gitignore.",
    no_args_is_help=True,
)

gitattributes_app = make_app(
    help="Manage whether vaultspec maintains its block in .gitattributes.",
    no_args_is_help=True,
)


def _set_precommit_policy(
    *, enabled: bool, json_output: bool, target: Path | None
) -> None:
    """Persist the workspace's pre-commit policy and report the outcome.

    The one implementation behind ``enable`` and ``disable``, which differ only
    by the boolean they persist and the sentence they print. Both are idempotent
    and report an already-satisfied request as success, so a sync script can set
    the policy unconditionally.
    """
    apply_target(target)
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context
    from vaultspec_core.core.workspace_mode import (
        HooksDeclaration,
        read_hooks_declaration,
        write_hooks_declaration,
    )

    root = get_context().target_dir
    try:
        already = read_hooks_declaration(root).pre_commit == enabled
        if not already:
            write_hooks_declaration(root, HooksDeclaration(pre_commit=enabled))
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    status = "unchanged" if already else "updated"
    if json_output:
        emit_json(
            "spec.precommit.enable" if enabled else "spec.precommit.disable",
            status,
            {"pre_commit": enabled, "workspace": str(root)},
        )
        raise typer.Exit(0)

    from vaultspec_core.console import get_console

    console = get_console()
    if enabled:
        console.print(
            f"[green]{status}[/green]: vaultspec-core scaffolds "
            ".pre-commit-config.yaml in this workspace."
        )
    else:
        console.print(
            f"[green]{status}[/green]: vaultspec-core will not scaffold "
            ".pre-commit-config.yaml in this workspace."
        )
        console.print(
            "  [dim]Any existing .pre-commit-config.yaml is left in place; "
            "delete it yourself if you no longer want it.[/dim]"
        )
    raise typer.Exit(0)


@precommit_app.command("disable")
def cmd_precommit_disable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Decline vaultspec-managed .pre-commit-config.yaml scaffolding.

    Records hooks.pre_commit = false in the committed
    .vaultspec/workspace.json, so no later install or sync regenerates the
    file, and the vaultspec-managed .gitignore block starts ignoring it so a
    resurrected copy cannot be committed by accident. For projects that run
    their gates explicitly and forbid a commit hook. Any existing
    .pre-commit-config.yaml is left on disk untouched.
    """
    _set_precommit_policy(enabled=False, json_output=json_output, target=target)


@precommit_app.command("enable")
def cmd_precommit_enable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore vaultspec-managed .pre-commit-config.yaml scaffolding.

    Clears a previously recorded opt-out so the next install or sync scaffolds
    the canonical hooks again. This is the default for a workspace that has
    never declared a preference, so running it there is a no-op.
    """
    _set_precommit_policy(enabled=True, json_output=json_output, target=target)


@precommit_app.command("migrate")
def cmd_precommit_migrate(
    remove_yaml: Annotated[
        bool,
        typer.Option(
            "--remove-yaml",
            help=(
                "Also delete the superseded .pre-commit-config.yaml once the "
                "canonical hooks are verifiably present in prek.toml"
            ),
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Transplant the canonical vaultspec hooks into prek.toml.

    When prek.toml owns the hook boundary, sync no longer scaffolds
    .pre-commit-config.yaml and prek silently ignores it. This command
    renders the canonical hook set into a vaultspec-managed block inside
    prek.toml. Idempotent: re-running with the hooks already present is a
    no-op. The superseded YAML config is never deleted unless
    --remove-yaml is passed and the hooks are verified present.
    """
    apply_target(target)
    from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek
    from vaultspec_core.core.types import get_context

    ctx = get_context()
    result = migrate_hooks_to_prek(
        ctx.target_dir, dry_run=dry_run, remove_yaml=remove_yaml
    )

    ok = result.status in ("migrated", "unchanged")
    if json_output:
        emit_json(
            "spec.precommit.migrate",
            result.status if ok else "failed",
            {
                "status": result.status,
                "detail": result.detail,
                "yaml_removed": result.yaml_removed,
                "dry_run": dry_run,
            },
        )
        raise typer.Exit(0 if ok else 1)

    from vaultspec_core.console import get_console

    console = get_console()
    prefix = "[dim](dry-run)[/dim] " if dry_run else ""
    if ok:
        style = "green" if result.status == "migrated" else "dim"
        console.print(f"{prefix}[{style}]{result.status}[/{style}]: {result.detail}")
        raise typer.Exit(0)
    console.print(f"{prefix}[red]{result.status}[/red]: {result.detail}")
    raise typer.Exit(1)


def _set_block_policy(
    *, block: str, enabled: bool, json_output: bool, target: Path | None
) -> None:
    """Persist the workspace's policy for one managed git block.

    The one implementation behind all four verbs, which differ only by the
    block they name, the boolean they persist, and the sentence they print.
    Idempotent, and an already-satisfied request reports success, so a
    provisioning script can set the policy unconditionally.

    This is the only writer of the committed ``blocks`` key outside the two
    gestures that mean "manage this workspace again" - a fresh install and
    ``--upgrade --force``. Deleting a block stands the per-machine echo down
    and says so; it does not reach the declaration, because an inference about
    intent must not modify a file the whole team shares.
    """
    apply_target(target)
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context
    from vaultspec_core.core.workspace_mode import (
        read_blocks_declaration,
        write_blocks_declaration,
    )

    root = get_context().target_dir
    try:
        current = read_blocks_declaration(root)
        already = getattr(current, block) == enabled
        if not already:
            write_blocks_declaration(root, replace(current, **{block: enabled}))
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    filename = f".{block}"
    status = "unchanged" if already else "updated"
    if json_output:
        emit_json(
            f"spec.{block}.enable" if enabled else f"spec.{block}.disable",
            status,
            {block: enabled, "workspace": str(root)},
        )
        raise typer.Exit(0)

    from vaultspec_core.console import get_console

    console = get_console()
    if enabled:
        console.print(
            f"[green]{status}[/green]: vaultspec-core maintains its managed "
            f"block in {filename} for this project."
        )
    else:
        console.print(
            f"[green]{status}[/green]: vaultspec-core will not maintain its "
            f"managed block in {filename} for this project."
        )
        console.print(
            f"  [dim]The declaration is committed, so every clone honours it. "
            f"Any existing {filename} is left in place.[/dim]"
        )
    raise typer.Exit(0)


@gitignore_app.command("disable")
def cmd_gitignore_disable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Decline the vaultspec-managed .gitignore block for the whole project.

    Records blocks.gitignore = false in the committed
    .vaultspec/workspace.json, so no later install, upgrade or sync writes the
    block, on any machine. Deleting the block by hand stands the current
    machine down but cannot travel: the manifest that would record it is
    itself inside the block. Any existing .gitignore is left on disk untouched.
    """
    _set_block_policy(
        block="gitignore", enabled=False, json_output=json_output, target=target
    )


@gitignore_app.command("enable")
def cmd_gitignore_enable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore the vaultspec-managed .gitignore block for the whole project.

    Clears a recorded decline so the next install, upgrade or sync writes the
    block again. This is the default for a workspace that has never declared a
    preference, so running it there is a no-op.
    """
    _set_block_policy(
        block="gitignore", enabled=True, json_output=json_output, target=target
    )


@gitattributes_app.command("disable")
def cmd_gitattributes_disable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Decline the vaultspec-managed .gitattributes block for the whole project.

    Records blocks.gitattributes = false in the committed
    .vaultspec/workspace.json. The block's default entries normalise line
    endings for every clone, so declining it is a team-wide statement and
    belongs in a committed file rather than on one machine.
    """
    _set_block_policy(
        block="gitattributes", enabled=False, json_output=json_output, target=target
    )


@gitattributes_app.command("enable")
def cmd_gitattributes_enable(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore the vaultspec-managed .gitattributes block for the whole project.

    Clears a recorded decline so the next install, upgrade or sync writes the
    block again. This is the default, so running it on a workspace that has
    never declared a preference is a no-op.
    """
    _set_block_policy(
        block="gitattributes", enabled=True, json_output=json_output, target=target
    )
