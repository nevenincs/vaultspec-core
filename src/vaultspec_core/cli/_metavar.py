"""Canonical positional-argument metavar rendering for the CLI surface.

The published CLI signature grammar is POSIX-conventional: a positional
argument renders as its uppercased name, bracketed when optional -
``vaultspec-core vault add [OPTIONS] DOC_TYPE``,
``vaultspec-core install [OPTIONS] [PROVIDER]``. Every handbook signature, the
bundled machine-facing reference, and the agent firmware quote that grammar, and
the CLI-language contract tests compare documentation snippets against the live
``Usage:`` line character for character.

Typer derives that metavar itself, and its default rendering is a cosmetic
implementation detail that has changed between releases: 0.27 switched from
``NAME`` / ``[NAME]`` to a lowercase ``{name}`` / ``[name]`` form. A cosmetic
upstream change must not silently rewrite a documented public contract across
several hundred snippets, so the grammar is owned here instead of inherited.

:func:`render_argument_metavar` is the single definition of the grammar.
:class:`CanonicalTyperArgument` applies it to the live ``--help`` surface, and
:mod:`vaultspec_core.cli.reference_gen` renders generated signatures through the
same function, so the live CLI and every generated document cannot diverge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typer.core import TyperArgument

if TYPE_CHECKING:
    from typer._click.core import Context as ClickContext

__all__ = [
    "CanonicalTyperArgument",
    "install_canonical_argument_metavars",
    "render_argument_metavar",
]


def render_argument_metavar(
    param: TyperArgument, ctx: ClickContext | None = None
) -> str:
    """Render one positional argument in the CLI's canonical metavar grammar.

    An explicitly declared ``metavar`` wins verbatim, bracketed only when the
    argument is optional and the declaration did not already bracket itself. An
    inferred metavar is the argument's name uppercased. A parameter type that
    contributes its own metavar appends it after a colon, and a non-unary
    argument gains a trailing ellipsis.

    Args:
        param: The Typer positional argument to render.
        ctx: The Click context the argument is rendered under, used only to ask
            the parameter type for its own metavar contribution.

    Returns:
        The metavar token as it appears in usage lines and signature snippets.
    """
    if param.metavar is not None:
        if param.required or param.metavar.startswith("["):
            return param.metavar
        return f"[{param.metavar}]"

    var = (param.name or "").upper()
    if not param.required:
        var = f"[{var}]"
    if ctx is not None:
        type_var = param.type.get_metavar(param, ctx=ctx)
        if type_var:
            var += f":{type_var}"
    if param.nargs != 1:
        var += "..."
    return var


class CanonicalTyperArgument(TyperArgument):
    """A Typer positional argument that renders the canonical metavar grammar.

    The override is deliberately insensitive to Typer's ``usage`` keyword: the
    same token is published in the ``Usage:`` line, the ``Arguments`` help
    section, and generated signatures, because the documentation contract quotes
    one grammar rather than a per-surface variant.
    """

    def make_metavar(self, ctx: ClickContext | None = None, **_kwargs: Any) -> str:
        """Return the canonical metavar token for this argument.

        Args:
            ctx: The Click context the argument is rendered under.
            **_kwargs: Rendering hints Typer passes per surface (``usage``),
                accepted and ignored so one grammar is published everywhere and
                so the override stays compatible across Typer releases.

        Returns:
            The metavar token, as :func:`render_argument_metavar` defines it.
        """
        return render_argument_metavar(self, ctx)


def install_canonical_argument_metavars() -> None:
    """Route Typer's argument construction through :class:`CanonicalTyperArgument`.

    Typer builds every positional argument in ``typer.main.get_click_param``,
    which names its argument class through a module global and offers no
    per-application hook. Rebinding that global is therefore the only seam;
    it is idempotent and safe to call from every app construction.
    """
    import typer.main

    # The rebinding is deliberately routed through an untyped module alias:
    # the attribute's declared type is the concrete upstream class, so a
    # subclass is not assignable to it under strict checking even though it is
    # exactly what the construction site needs.
    typer_main: Any = typer.main
    if typer_main.TyperArgument is not CanonicalTyperArgument:
        typer_main.TyperArgument = CanonicalTyperArgument
