"""Ask the operator before a provider hook is rendered into an agent's config.

The engine already refuses to render a hook that
:mod:`vaultspec_core.triggers.trust` has not matched against a consent record,
so this module is the *asking* half: it runs at the CLI, where a human may be
present, and never inside the renderer, where one may not.

A provider hook is the more dangerous of the two consent surfaces. A lifecycle
trigger runs once, when vaultspec fires its event. A provider hook is written
into ``.claude/settings.json`` and its equivalents, and from then on the agent
runs it in its own session on every matching tool call, with no further sync
and nothing on screen. Approval is therefore recorded per file and per content
digest, and pulling a change to an approved hook asks again.

Separate from :mod:`._trigger_trust`, which asks about ``.vaultspec/triggers/``.
The two grants are independent: approving one directory says nothing about the
other, because the commands, the directories and the blast radius all differ.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from vaultspec_core.config import is_unattended

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.core.provider_hooks import HookSpec

__all__ = ["describe_hook", "hook_consent_gate"]

_RATIONALE = (
    "Each of these hook files ships with this repository and declares a shell "
    "command. Approving one writes it into your agents' own configuration, "
    "where the agent runs it as you - with your environment, your credentials, "
    "and this workspace as its working directory - on every matching tool "
    "call, not once per sync. A repository cannot approve its own hooks, so "
    "approval is recorded outside it and is tied to each file's current "
    "contents; editing a hook, or pulling a change to one, asks again."
)


def describe_hook(spec: HookSpec, target_dir: Path | None = None) -> list[str]:
    """Render one unapproved hook as the lines an operator needs to judge it.

    The command is shown verbatim and unwrapped. An approval prompt that
    summarises or truncates the command is worse than no prompt, because it
    invites a yes to something other than what will run.
    """
    location = spec.source_path
    label = str(location) if location is not None else "<no file>"
    if location is not None and target_dir is not None:
        try:
            label = str(location.relative_to(target_dir))
        except ValueError:
            label = str(location)
    matcher = f" [{spec.matcher}]" if spec.matcher else ""
    return [
        f"  {spec.name}  ({label})",
        f"    on {spec.event.value}{matcher}: {spec.command}",
    ]


def hook_consent_gate(
    *,
    json_output: bool = False,
    hooks_dir: Path | None = None,
    home: Path | None = None,
) -> list[str]:
    """Offer the operator the choice to approve the hooks a sync would render.

    Loads the workspace's hook specs and, for any carrying no consent record,
    either asks for one (at an interactive terminal) or explains why they will
    be skipped (anywhere else). Granting writes the consent record; declining,
    redirected input, and ``--json`` all leave it unwritten.

    Args:
        json_output: Whether the calling command is emitting a JSON envelope.
            A machine-readable run has no operator to ask and must not have its
            stdout disturbed, so it never prompts.
        hooks_dir: The directory whose hooks the caller is about to render. It
            must be the same directory the renderer will read, which is not
            always the ambient one under ``--target``. Defaults to the ambient
            context's ``hooks_dir``.
        home: Machine-global VaultSpec home holding the consent ledger; tests
            pass their own so they never touch the operator's.

    Returns:
        The names of the hooks that remain unapproved, and will therefore be
        skipped. Empty when every hook may be rendered.
    """
    from vaultspec_core.core.provider_hooks import (
        load_provider_hook_specs,
        trusted_specs,
    )
    from vaultspec_core.core.types import get_context
    from vaultspec_core.triggers import grant

    try:
        ctx = get_context()
    except LookupError:
        return []

    specs = load_provider_hook_specs(hooks_dir)
    _trusted, refused = trusted_specs([spec for spec in specs if spec.enabled], home)
    if not refused:
        return []

    names = [spec.name for spec in refused]
    detail: list[str] = []
    for spec in refused:
        detail.extend(describe_hook(spec, ctx.target_dir))

    if is_unattended(json_output=json_output):
        _explain_refusal(names, detail)
        return names

    typer.echo("")
    typer.echo("Unapproved provider hooks in this workspace:")
    for line in detail:
        typer.echo(line)
    typer.echo("")
    typer.echo(_RATIONALE)
    typer.echo("")
    try:
        approved = typer.confirm(
            "Render these hooks into your agents' configs, and remember this approval?",
            default=False,
        )
    except (typer.Abort, EOFError, KeyboardInterrupt):
        # An interrupt or an exhausted stream is not an answer. It reaches here
        # when a stream that claimed to be a terminal turns out not to carry
        # one, which some Windows shells arrange for a redirected run - the
        # exact case that must never be read as consent. Treat it as a refusal
        # and let the sync continue without the hooks.
        approved = False
    if not approved:
        typer.echo("", err=True)
        _explain_refusal(names, [])
        return names

    grant([s.source_path for s in refused if s.source_path is not None], home)
    return []


def _explain_refusal(names: list[str], detail: list[str]) -> None:
    """State on stderr why hooks were skipped, and how to approve them.

    Written to stderr so a ``--json`` caller's stdout stays a single envelope,
    and phrased as an instruction to the operator rather than to the process,
    because the operator is the only one who can act on it.
    """
    listed = ", ".join(names)
    typer.echo(f"Skipped {len(names)} unapproved provider hook(s): {listed}", err=True)
    for line in detail:
        typer.echo(line, err=True)
    typer.echo(f"  {_RATIONALE}", err=True)
    typer.echo(
        "  Approval cannot be given by a script or a tool call. Review the "
        "files above at a terminal, then run: vaultspec-core spec hooks trust",
        err=True,
    )
