"""Next-step advisory hints: the ``Next action(s):`` footer.

Split out of :mod:`.rendering`. Re-exported from there so no import site
outside the package needs to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.console import get_console

if TYPE_CHECKING:
    from collections.abc import Sequence

_NEXT_STEP_HINTS: dict[tuple[str, str], tuple[str, str]] = {
    ("vault.add.research", "created"): (
        "vaultspec-core vault add adr --feature {feature} --related {research_stem}",
        "Define an Architecture Decision Record (ADR) for your research",
    ),
    ("vault.add.adr", "created"): (
        "vaultspec-core vault add plan --feature {feature} --related {adr_stem}",
        "Draft an implementation plan based on your ADR",
    ),
    ("vault.add.plan", "created"): (
        "vaultspec-core vault add exec --all-steps --feature {feature} "
        "--related {plan_stem}",
        "Scaffold step-aware execution records for your plan",
    ),
    ("vault.add.exec", "created"): (
        "vaultspec-core vault plan status",
        "Track the progress and verification of your plan",
    ),
    ("vault.add.audit", "created"): (
        "vaultspec-core vault rule promote --from {audit_stem} --as {rule_name}",
        "Promote your audit findings to a team-shared rule",
    ),
    ("vault.check.all", "unchanged"): (
        'git commit -m "Commit changes after successful vault checks"',
        "Your vault is clean. Proceed to commit your changes",
    ),
    ("vault.check.all", "failed"): (
        "vaultspec-core vault repair",
        "Run safe auto-corrections to resolve vault errors",
    ),
    ("install", "created"): (
        "vaultspec-core vault add research --feature {feature_tag}",
        "Framework installed. Start research on your first feature",
    ),
    ("install", "updated"): (
        "vaultspec-core vault add research --feature {feature_tag}",
        "Framework updated. Start research on your first feature",
    ),
    ("vault.feature.archive", "updated"): (
        "vaultspec-core vault check all",
        "Verify your vault remains completely clean after archiving",
    ),
    ("vault.feature.rename", "updated"): (
        "vaultspec-core vault check all",
        "Verify your vault is completely clean after renaming the feature",
    ),
}


class SafeDict(dict):
    """A dictionary that retains unknown string placeholders for formatting."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def hints_suppressed(no_hints: bool = False) -> bool:
    """Report whether next-step hints are suppressed for this invocation.

    Hints are advisory and must be silenceable for scripted contexts, per
    the cli-next-step-hints ADR. They are off when the caller passes
    ``--no-hints`` or the ``VAULTSPEC_NO_HINTS=1`` environment variable is
    set. This is the one predicate every hint surface consults so the
    suppression contract cannot drift per command.
    """
    import os

    return no_hints or os.environ.get("VAULTSPEC_NO_HINTS") == "1"


def render_next_actions(pairs: Sequence[tuple[str, str]]) -> None:
    """Print next-step hints in the one uniform footer form.

    Per the cli-presentation-uniformity ADR every next-step hint, from
    every command, renders identically: a ``Next action:`` header (or
    ``Next actions:`` for more than one) at column 0, then each hint as a
    two-space-indented description with its command indented a further two
    spaces. This mirrors the plain footer of ``vaultspec-rag`` and
    replaces the divergent ``Suggested Next Step:`` forms.

    Args:
        pairs: ``(description, command)`` hints in display order. An empty
            sequence prints nothing.
    """
    from rich.markup import escape

    items = list(pairs)
    if not items:
        return
    console = get_console()
    console.print()
    header = "Next action:" if len(items) == 1 else "Next actions:"
    console.print(f"[bold]{header}[/bold]")
    for description, command in items:
        console.print(f"  {escape(description)}")
        console.print(f"    [cyan]{escape(command)}[/cyan]")


def emit_next_step_hint(
    command: str,
    outcome: str,
    context_vars: dict[str, str] | None = None,
    json_output: bool = False,
    no_hints: bool = False,
) -> dict[str, object] | None:
    """Emit the next-step advisory hint for a command and outcome.

    Checks the VAULTSPEC_NO_HINTS environment variable and the --no-hints
    flag suppression.

    Returns:
        A dict matching {"text": str, "command": str} for JSON, or None.
        Also prints to the console if not json_output.
    """
    if hints_suppressed(no_hints):
        return None

    hint = _NEXT_STEP_HINTS.get((command, outcome))
    if not hint:
        return None

    cmd_template, description = hint
    # Format safely using SafeDict so missing variables remain placeholders
    safe_vars = SafeDict(context_vars or {})
    formatted_command = cmd_template.format_map(safe_vars)

    if not json_output:
        render_next_actions([(description, formatted_command)])

    return {"text": description, "command": formatted_command}
