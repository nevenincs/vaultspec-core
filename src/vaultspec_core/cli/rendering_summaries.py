"""Concise post-install/post-uninstall summaries and the sharing-policy banner.

Split out of :mod:`.rendering`. Re-exported from there so no import site
outside the package needs to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.console import get_console

if TYPE_CHECKING:
    from collections.abc import Sequence


def render_install_summary(
    source_counts: dict[str, int],
    *,
    path: str,
    providers: Sequence[str],
    has_mcp: bool = False,
) -> None:
    """Render a concise post-install summary.

    Shows what was found in the vaultspec source (the actual number of
    rules, skills, and agents the user authored) and which providers
    they were synced to.

    Args:
        source_counts: Mapping of resource type to count, e.g.
            ``{"rules": 1, "skills": 2, "agents": 9}``.
        path: Display path of the installation target.
        providers: Provider names that were enabled (e.g. ``["claude"]``).
        has_mcp: Whether the MCP server configuration was installed.
    """
    console = get_console()

    # --- Header (box-free per the output contract) ---
    console.print()
    console.print("[bold green]Installed[/bold green] vaultspec")
    console.print(f"  [dim]Target[/dim] {path}")

    # --- Source resource counts ---
    category_order = ["rules", "skills", "agents"]
    summary_parts: list[str] = []
    for cat in category_order:
        n = source_counts.get(cat, 0)
        if n:
            label = cat if n != 1 else cat.rstrip("s")
            summary_parts.append(f"[bold]{n}[/bold] {label}")

    if summary_parts:
        console.print(f"  Synced {', '.join(summary_parts)}")

    # --- Providers ---
    if providers:
        provider_list = ", ".join(f"[cyan]{p}[/cyan]" for p in providers)
        console.print(f"  Enabled {provider_list}")

    # --- MCP ---
    if has_mcp:
        console.print("  Installed [cyan]MCP server[/cyan]")

    console.print()


def render_sharing_policy() -> None:
    """Print the spec-layer sharing-policy statement.

    Per the cli-spec-gitignore ADR, install and upgrade state the
    team-shared default plainly so an operator knows authored content
    reaches teammates and only runtime by-products stay local.
    """
    console = get_console()
    console.print("[bold]Sharing policy[/bold]")
    console.print(
        "  [dim].vaultspec/[/dim] (rules, skills, agents, system), "
        "[dim]CLAUDE.md[/dim], and [dim].mcp.json[/dim] are committed to git "
        "so teammates inherit your project policy."
    )
    console.print(
        "  Runtime by-products ([dim].vaultspec/_snapshots/[/dim], lock "
        "files, [dim]providers.json[/dim]) stay local."
    )
    console.print()


def render_uninstall_summary(
    removed: Sequence[tuple[str, str]], *, path: str, keep_vault: bool = True
) -> None:
    """Render a concise post-uninstall summary.

    Args:
        removed: ``(path, label)`` tuples for removed items.
        path: Display path of the uninstall target.
        keep_vault: Whether ``.vault/`` was preserved.
    """
    console = get_console()

    # Extract provider names from labels
    known_providers = {"claude", "gemini", "antigravity", "codex"}
    providers: list[str] = []
    seen: set[str] = set()
    for _, label in removed:
        name = label.split("(")[0].strip().lower() if "(" in label else label.lower()
        if name in known_providers and name not in seen:
            seen.add(name)
            providers.append(name)

    # Header (box-free per the output contract).
    console.print()
    console.print("[bold red]Uninstalled[/bold red] vaultspec")
    console.print(f"  [dim]Target[/dim] {path}")

    if providers:
        provider_list = ", ".join(f"[cyan]{p}[/cyan]" for p in providers)
        console.print(f"  Disabled {provider_list}")

    if keep_vault:
        console.print(
            "  [dim].vault/ preserved"
            "  - pass --remove-vault to also remove documentation[/dim]"
        )
