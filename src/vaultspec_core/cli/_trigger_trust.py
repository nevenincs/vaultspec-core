"""The operator-facing consent gate for workspace triggers.

:func:`vaultspec_core.triggers.engine.trigger` already refuses to spawn a command
that :mod:`vaultspec_core.triggers.trust` has not matched against a consent record,
so nothing here is what makes the product safe. What this module adds is the
only thing a refusal is missing: a way for the operator to say yes, and an
explanation of what they are saying yes to.

The gate is deliberately a CLI concern rather than an engine one. Asking is an
interactive act at a terminal, and the engine runs in contexts - CI, the MCP
server, ``--json`` pipelines - that have no operator behind them. Keeping the
question here means the enforcement path has no branch that could ever answer it
automatically: when this module cannot reach a human it explains the refusal and
returns, and the triggers simply do not run.

Key exports: :func:`consent_gate`, :func:`describe_trigger`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from vaultspec_core.config import is_unattended

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.triggers import Trigger

__all__ = ["consent_gate", "describe_trigger"]

#: Why a trigger needs approval, in the terms that make the decision answerable:
#: what runs, as whom, and why the repository itself cannot vouch for it. A
#: prompt the operator does not understand is a prompt they click through.
_RATIONALE = (
    "Each of these trigger files ships with this repository and declares a shell "
    "command that would run now, on this machine, as you - with your "
    "environment, your credentials, and this workspace as its working "
    "directory. A repository cannot approve its own triggers, so approval is "
    "recorded outside it and is tied to each file's current contents; editing "
    "a trigger, or pulling a change to one, asks again."
)


def describe_trigger(trig: Trigger, target_dir: Path | None = None) -> list[str]:
    """Render one untrusted trigger as the lines an operator needs to judge it.

    The commands are shown verbatim and unwrapped. An approval prompt that
    summarises or truncates the command is worse than no prompt, because it
    invites a yes to something other than what will run.
    """
    location = trig.source_path
    label = str(location) if location is not None else "<no file>"
    if location is not None and target_dir is not None:
        try:
            label = str(location.relative_to(target_dir))
        except ValueError:
            label = str(location)
    lines = [f"  {trig.name}  ({label})"]
    lines.extend(
        f"    {action.action_type}: {action.command}" for action in trig.actions
    )
    return lines


def consent_gate(
    event: str,
    *,
    json_output: bool = False,
    triggers_dir: Path | None = None,
    home: Path | None = None,
) -> list[str]:
    """Offer the operator the choice to trust the triggers an event would run.

    Loads the workspace's triggers for ``event``, and for any that carry no
    consent record either asks for one (at an interactive terminal) or explains
    why they will be skipped (anywhere else). Granting writes the consent
    record; declining, redirected input, and ``--json`` all leave it unwritten.

    Args:
        event: The lifecycle event whose triggers are about to be considered.
        json_output: Whether the calling command is emitting a JSON envelope.
            A machine-readable run has no operator to ask and must not have its
            stdout disturbed, so it never prompts.
        triggers_dir: The directory whose triggers the caller is about to fire. It
            must be the same directory the firing code will read, which is not
            always the ambient one: ``sync --target`` reads its source content
            from the CWD workspace but fires the *target* workspace's triggers.
            Asking about one workspace's triggers while another's are the ones
            about to run would show the operator commands that will not run and
            withhold the ones that will. Defaults to the ambient context's
            ``triggers_dir``, which is right for every caller with no such split.
        home: Machine-global VaultSpec home holding the consent ledger; tests
            pass their own so they never touch the operator's.

    Returns:
        The names of the triggers that remain untrusted, and will therefore be
        skipped. Empty when every trigger for ``event`` may run.
    """
    from vaultspec_core.core.types import get_context
    from vaultspec_core.triggers import grant, load_triggers, partition_by_trust

    try:
        ctx = get_context()
    except LookupError:
        return []

    source = ctx.triggers_dir if triggers_dir is None else triggers_dir
    candidates = [
        trig for trig in load_triggers(source) if trig.event == event and trig.enabled
    ]
    _, untrusted = partition_by_trust(candidates, home)
    if not untrusted:
        return []

    names = [trig.name for trig in untrusted]
    detail: list[str] = []
    for trig in untrusted:
        detail.extend(describe_trigger(trig, ctx.target_dir))

    if is_unattended(json_output=json_output):
        _explain_refusal(names, detail)
        return names

    typer.echo("")
    typer.echo(f"Untrusted workspace triggers for '{event}':")
    for line in detail:
        typer.echo(line)
    typer.echo("")
    typer.echo(_RATIONALE)
    typer.echo("")
    try:
        approved = typer.confirm(
            "Run these triggers, and remember this approval?", default=False
        )
    except (typer.Abort, EOFError, KeyboardInterrupt):
        # An interrupt or an exhausted stream is not an answer. It reaches here
        # when a stream that claimed to be a terminal turns out not to carry
        # one, which some Windows shells arrange for a redirected run - the
        # exact case that must never be read as consent. Treat it as a refusal
        # and let the caller continue without the triggers, rather than letting an
        # Abort tear down a sync that is otherwise legitimate.
        approved = False
    if not approved:
        typer.echo("", err=True)
        _explain_refusal(names, [])
        return names

    grant([h.source_path for h in untrusted if h.source_path is not None], home)
    return []


def _explain_refusal(names: list[str], detail: list[str]) -> None:
    """State on stderr why triggers were skipped, and how to approve them.

    Written to stderr so a ``--json`` caller's stdout stays a single envelope,
    and phrased as an instruction to the operator rather than to the process,
    because the operator is the only one who can act on it.
    """
    listed = ", ".join(names)
    typer.echo(
        f"Skipped {len(names)} untrusted workspace trigger(s): {listed}",
        err=True,
    )
    for line in detail:
        typer.echo(line, err=True)
    typer.echo(f"  {_RATIONALE}", err=True)
    typer.echo(
        "  Approval cannot be given by a script or a tool call. Review the "
        "files above at a terminal, then run: vaultspec-core spec triggers trust",
        err=True,
    )
