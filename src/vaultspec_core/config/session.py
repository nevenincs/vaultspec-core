"""Whether anybody is watching this run.

One rule, for every package and every prompt: a run is unattended when the
session says so, when its standard streams are not a terminal, or when its
output is a machine envelope. An unattended run never prompts - a question
nobody sees is a question nobody answered - and a step it skips for want of
consent is reported as skipped rather than assumed.

The rule lives here rather than in the CLI package because the packages that
must agree on it do not all have one: a library, a daemon and a server decide
the same question, and a second implementation of it is how the answers drift
apart.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from .config import CI, VAULTSPEC_NON_INTERACTIVE, env_flag, env_present

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["is_unattended", "unattended_declared"]


def _not_a_terminal(stream: TextIO | None, fallback: TextIO) -> bool:
    """Return whether *stream* is something other than a terminal."""
    actual = fallback if stream is None else stream
    try:
        return not actual.isatty()
    except (AttributeError, ValueError):
        # A closed or replaced stream cannot be interrogated, and a stream
        # nobody can ask about is not one a person is reading.
        return True


def unattended_declared(
    environ: Mapping[str, str] | None = None,
) -> bool | None:
    """Return what the session environment declares, or ``None`` if nothing.

    ``CI`` is the near-universal convention, owned by the systems that set it
    and defined by presence. ``VAULTSPEC_NON_INTERACTIVE`` is the product's
    own, and it outranks ``CI`` in both directions: a variable set
    deliberately for this tool is a later word than the environment the tool
    happens to be running in, so a wrapper script running under CI with
    somebody watching can say so.

    Args:
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        ``True`` when the session declares nobody is watching, ``False`` when
        it declares somebody is, ``None`` when it says nothing either way.

    Raises:
        ConfigurationError: If the product marker carries a word the boolean
            vocabulary does not recognise.
    """
    declared = env_flag(VAULTSPEC_NON_INTERACTIVE, environ)
    if declared is not None:
        return declared
    return True if env_present(CI, environ) else None


def is_unattended(
    *,
    json_output: bool = False,
    environ: Mapping[str, str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> bool:
    """Return whether this run has nobody to answer a prompt.

    A run is unattended when its output is a machine envelope, when the
    session declares it (see :func:`unattended_declared`), or when either
    standard stream is not a terminal - the answer has to be read from one
    and the question shown on the other.

    Declaring an operator present does not conjure one: the streams still
    decide, so ``VAULTSPEC_NON_INTERACTIVE=0`` in a pipeline is still
    unattended.

    Args:
        json_output: Whether this invocation emits a machine envelope.
        environ: The environment to read; ``None`` reads the process's own.
        stdin: The stream an answer would be read from; ``None`` uses the
            process's own.
        stdout: The stream a question would be shown on; ``None`` uses the
            process's own.

    Returns:
        ``True`` when no prompt may be issued.

    Raises:
        ConfigurationError: If the product marker carries a word the boolean
            vocabulary does not recognise.
    """
    if json_output:
        return True
    if unattended_declared(environ) is True:
        return True
    return _not_a_terminal(stdin, sys.stdin) or _not_a_terminal(stdout, sys.stdout)
