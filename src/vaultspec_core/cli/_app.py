"""Single sanctioned Typer constructor for the vaultspec-core CLI.

Every Typer app in the CLI is built through :func:`make_app` so that
plain-Click help (``rich_markup_mode=None``) is enforced in one place, and
so that every command renders the canonical positional-argument metavar
grammar defined in :mod:`vaultspec_core.cli._metavar`.
``--help`` renders as bog-standard ``Usage`` / ``Arguments`` / ``Options`` /
``Commands`` sections that wrap to the terminal width - matching
``vaultspec-rag`` and ``glow`` - never as Rich-drawn bordered panels. Routing
every app through this factory means a new sub-app cannot silently reintroduce
a panel, or a divergent usage grammar, by calling :class:`typer.Typer`
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vaultspec_core.cli._metavar import CanonicalTyper

if TYPE_CHECKING:
    import typer

#: The command names this distribution installs, as ``[project.scripts]``
#: declares them. They are stated here because Click cannot discover them:
#: the release binaries launch through ``python -m`` and ``python -c``, so
#: ``sys.argv[0]`` names the launcher rather than the command a user typed.
#: ``dev/guards`` asserts these against ``pyproject.toml``.
CLI_PROG_NAME = "vaultspec-core"
MCP_PROG_NAME = "vaultspec-core-mcp"

__all__ = ["CLI_PROG_NAME", "MCP_PROG_NAME", "make_app"]


def make_app(**kwargs: Any) -> typer.Typer:
    """Construct a :class:`typer.Typer` with plain-Click help and shared defaults.

    Forces ``rich_markup_mode=None`` so Typer falls back to Click's
    standard help formatter instead of its Rich panel renderer, builds the
    app as a :class:`~vaultspec_core.cli._metavar.CanonicalTyper` so its
    commands render the canonical positional-argument metavar grammar, and
    defaults ``no_args_is_help`` and ``add_completion`` to the values the CLI
    uses everywhere. Any default may be overridden by passing the
    keyword explicitly; ``rich_markup_mode`` is fixed and not overridable,
    because the plain-help guarantee is the whole point of the factory.

    Args:
        **kwargs: Keyword arguments forwarded to :class:`typer.Typer`
            (for example ``help`` and ``name``).

    Returns:
        A configured :class:`typer.Typer` instance.
    """
    kwargs.setdefault("no_args_is_help", True)
    kwargs.setdefault("add_completion", False)
    kwargs.pop("rich_markup_mode", None)
    return CanonicalTyper(rich_markup_mode=None, **kwargs)
