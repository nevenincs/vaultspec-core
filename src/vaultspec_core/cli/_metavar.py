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

The grammar is scoped to this CLI's own command tree. :class:`CanonicalTyper`
builds its commands and groups from classes that adopt their positional
arguments into :class:`CanonicalTyperArgument`, so another Typer application
in the same process keeps Typer's own rendering regardless of import order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import typer
from typer.core import TyperArgument, TyperCommand, TyperGroup

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer._click.core import Context as ClickContext
    from typer._click.core import Parameter as ClickParameter
    from typer.models import CommandFunctionType

__all__ = [
    "CanonicalTyper",
    "CanonicalTyperArgument",
    "CanonicalTyperCommand",
    "CanonicalTyperGroup",
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

    @override
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


def _adopt_canonical_arguments(params: list[ClickParameter]) -> None:
    """Re-class each plain Typer positional argument as canonical, in place.

    Typer constructs every argument in ``typer.main.get_click_param`` from a
    module global and offers no per-application hook, so the argument is adopted
    after construction instead. The subclass adds behaviour only, never state,
    which makes the class swap exact; doing it in place keeps the identity the
    command's callback closure already holds. Any other ``TyperArgument``
    subclass is a deliberate choice and is left alone.
    """
    for param in params:
        if type(param) is TyperArgument:
            param.__class__ = CanonicalTyperArgument


class CanonicalTyperCommand(TyperCommand):
    """A Typer command whose positional arguments render the canonical grammar."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _adopt_canonical_arguments(self.params)


class CanonicalTyperGroup(TyperGroup):
    """A Typer group whose positional arguments render the canonical grammar."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _adopt_canonical_arguments(self.params)


class CanonicalTyper(typer.Typer):
    """A Typer application whose own commands and groups render canonical metavars.

    Groups default to :class:`CanonicalTyperGroup` and commands to
    :class:`CanonicalTyperCommand`; an explicit ``cls`` still wins. The grammar
    reaches exactly the command tree built from this application.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("cls", CanonicalTyperGroup)
        super().__init__(**kwargs)

    @override
    def command(
        self,
        name: str | None = None,
        *,
        cls: type[TyperCommand] | None = None,
        **kwargs: Any,
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        """Register a command built as :class:`CanonicalTyperCommand` by default.

        Args:
            name: The command name, derived from the function when omitted.
            cls: An explicit command class, which overrides the default.
            **kwargs: Every other :meth:`typer.Typer.command` keyword, verbatim.

        Returns:
            The registering decorator :meth:`typer.Typer.command` returns.
        """
        return super().command(name, cls=cls or CanonicalTyperCommand, **kwargs)
