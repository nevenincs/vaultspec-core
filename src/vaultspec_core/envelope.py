"""The ``--json`` envelope, importable without the CLI command tree.

An importing package that only wants to render vaultspec-core's canonical
``--json`` shape - the install/uninstall envelope, an error report, or the
next-step-hint suppression rule - should not have to build the whole Typer
command tree to get it. Importing anything under :mod:`vaultspec_core.cli`
runs that package's ``__init__`` first (Python imports every parent package
before the submodule), which constructs every command group. This module
depends on nothing under :mod:`vaultspec_core.cli` and nothing outside the
standard library plus :mod:`vaultspec_core.config`, so importing it alone
pays only for that.

:mod:`vaultspec_core.cli.json_output` and :mod:`vaultspec_core.cli.rendering_outcomes`
re-export the same names from here for the CLI's own internal call sites, so
neither this module's existence nor its callers' import paths change.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .config import (
    GIT_INDEX_FILE,
    VAULTSPEC_JSON_PRETTY,
    VAULTSPEC_NO_HINTS,
    env_flag,
    env_present,
)
from .core.exceptions import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "error_format_kwargs",
    "hints_suppressed",
    "json_envelope",
    "json_format_kwargs",
    "pretty_enabled",
    "render_envelope",
    "render_error_envelope",
    "render_install_envelope",
]

#: Compact separators: no space after ``,`` or ``:``. ``json.dumps`` defaults
#: to ``", "`` and ``": "``, which adds two bytes per field on top of the
#: indentation itself. Non-ASCII text is written as UTF-8 rather than
#: ``\uXXXX`` escapes; the CLI entry point already makes stdout UTF-8, so the
#: raw form is always writable there.
_COMPACT: dict[str, Any] = {"separators": (",", ":"), "ensure_ascii": False}

#: Indented form, for a human reading a payload directly.
_PRETTY: dict[str, Any] = {"indent": 2, "ensure_ascii": False}


def pretty_enabled() -> bool:
    """Report whether indented JSON was explicitly requested.

    Read per call rather than cached at import so a test or a shell can
    toggle it without reloading the module.

    Returns:
        ``True`` when the environment opts into indentation.

    Raises:
        ConfigurationError: If the switch carries a word the boolean
            vocabulary does not recognise.
    """
    return bool(env_flag(VAULTSPEC_JSON_PRETTY))


def json_format_kwargs() -> dict[str, Any]:
    """Return the ``json.dumps`` formatting keywords for this channel.

    Returns:
        Compact separators by default; indentation when opted in.
    """
    return dict(_PRETTY) if pretty_enabled() else dict(_COMPACT)


def error_format_kwargs() -> dict[str, Any]:
    """Return the formatting keywords for an error report.

    Reporting a failure must not be able to fail: the indentation switch may
    itself be the unusable value being reported, and a refusal raised while
    rendering one would replace the error the operator needs to see. The
    compact form is the answer whenever the switch cannot be read.

    Returns:
        The same keywords as :func:`json_format_kwargs`, or the compact form
        when the switch carries a value it cannot take.
    """
    try:
        return json_format_kwargs()
    except ConfigurationError:
        return dict(_COMPACT)


def hints_suppressed(
    *, no_hints: bool = False, environ: Mapping[str, str] | None = None
) -> bool:
    """Report whether next-step hints are suppressed for this invocation.

    Hints are advisory and must be silenceable for scripted contexts. They
    are off when the caller passes ``--no-hints`` or ``VAULTSPEC_NO_HINTS``
    carries a true word. They are also off inside a git commit hook,
    detected by the ``GIT_INDEX_FILE`` git exports to every commit hook: hook
    output is often acted on without review, so a hook that runs a command
    must not propose a follow-up that rewrites documents the commit never
    touched. Git owns that name and defines it by presence, so it is read by
    presence; the product's own switch is a boolean like every other. This is
    the one predicate every hint surface consults so the suppression contract
    cannot drift per command - in any package, not only this one.

    Args:
        no_hints: Whether the invocation passed ``--no-hints``.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        ``True`` when no hint may be printed.

    Raises:
        ConfigurationError: If the switch carries a word the boolean
            vocabulary does not recognise.
    """
    return (
        no_hints
        or bool(env_flag(VAULTSPEC_NO_HINTS, environ))
        or env_present(GIT_INDEX_FILE, environ)
    )


def json_envelope(
    command: str,
    status: str,
    data: Mapping[str, object],
    *,
    version: int = 1,
    hints: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Wrap a command payload in the canonical ``--json`` envelope.

    Every ``--json`` output shares one shape - ``{schema, status, data,
    hints}`` - so a consumer matches a single pattern across every verb.

    Args:
        command: Dotted command identifier (e.g. ``"sync"``,
            ``"spec.rules.sync"``); forms the ``schema`` string.
        status: The invocation's aggregate canonical outcome word.
        data: The command's own payload, nested unmodified.
        version: Schema version suffix appended to the ``schema`` string
            (e.g. ``1`` yields ``vaultspec.{command}.v1``). Defaults to
            ``1``.
        hints: Optional structured next-step hint; omitted when absent.

    Returns:
        The envelope mapping ``{schema, status, data}`` plus ``hints``
        when supplied.

    Example::

        json_envelope("vault.check", "unchanged", {...})
        # => {"schema": "vaultspec.vault.check.v1", ...}
    """
    envelope: dict[str, object] = {
        "schema": f"vaultspec.{command}.v{version}",
        "status": str(status),
        "data": dict(data),
    }
    if hints is not None:
        envelope["hints"] = dict(hints)
    return envelope


def render_envelope(
    command: str,
    status: str,
    data: Mapping[str, object],
    *,
    version: int = 1,
    hints: Mapping[str, object] | None = None,
) -> str:
    """Render the canonical envelope as the one JSON line a caller prints.

    :func:`json_envelope` builds the shape; this renders it on the wire, in
    the channel's own formatting. Every package that reports through the
    envelope calls this rather than dumping its own, so a payload cannot
    arrive compact from one command and indented from another.

    Args:
        command: Dotted command identifier; forms the ``schema`` string.
        status: The invocation's aggregate canonical outcome word.
        data: The command's own payload.
        version: Schema version suffix.
        hints: Optional structured next-step hint; omitted when absent.

    Returns:
        The serialised envelope, without a trailing newline.
    """
    return json.dumps(
        json_envelope(command, status, data, version=version, hints=hints),
        **json_format_kwargs(),
        default=str,
    )


def render_install_envelope(
    schema: str,
    status: str,
    data: Mapping[str, object],
    *,
    hints: Mapping[str, object] | None = None,
) -> str:
    """Render an install or uninstall report as the canonical JSON line.

    The report shape every package's install surface shares: the verb's own
    schema, one canonical status word, the package's payload, and the same
    structured next-step hint every other envelope carries - the mapping a
    next-step-hint helper returns, passed straight through. There is exactly
    one hint shape in the envelope; an install surface does not get a second
    one. A caller with nothing to advise passes ``None``.

    This is the function core's own install and uninstall commands render
    their ``--json`` output through, so an importing package's install
    surface matches core's by construction rather than by convention.

    Args:
        schema: The verb, ``install`` or ``uninstall``, forming the schema.
        status: The canonical outcome word for the run.
        data: The verb's own payload.
        hints: The structured next-step hint, or ``None``.

    Returns:
        The serialised envelope, without a trailing newline.
    """
    return render_envelope(schema, status, data, hints=hints)


def render_error_envelope(message: str, *, hint: str | None = None) -> str:
    """Render a failure as the canonical ``vaultspec.error.v1`` JSON line.

    The counterpart of :func:`render_install_envelope` for the run that did
    not get that far, so a ``--json`` consumer parses failures rather than
    inferring them from an exit code. It formats through the error-safe
    keywords: the indentation switch may itself be what failed, and a second
    refusal raised while reporting the first would replace it.

    Args:
        message: What went wrong, as the operator needs to read it.
        hint: Optional guidance; omitted when absent.

    Returns:
        The serialised envelope, without a trailing newline.
    """
    data: dict[str, object] = {"message": message}
    if hint:
        data["hint"] = hint
    return json.dumps(
        json_envelope("error", "failed", data), **error_format_kwargs(), default=str
    )
