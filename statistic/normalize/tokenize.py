"""Stage one of normalization: turn a raw command string into candidate segments.

The dominant command shape in both corpora is never a bare invocation: a ``cd``
prefix chained with ``uv run --no-sync vaultspec-core``, roughly a third of them
multi-line, shell ``for`` loops firing N logical calls from one physical line,
and heredocs that embed the target string without being calls. This module
resolves that surface before any argv parsing happens, in a fixed pipeline:

#. strip ANSI escape sequences and normalize CRLF to LF,
#. mask heredoc bodies so a ``vaultspec-core`` mention between ``<<TOKEN`` and
   its terminator never counts as a call,
#. unroll a single-line ``for var in A B C; do ... $var ...; done`` into N
   logical segments,
#. split the remainder on shell connectors (``&&``, ``||``, ``;``, ``|``, and
   newline),
#. yield only the segments that actually mention ``vaultspec-core``.

The output is a list of candidate segment strings. Locating the executable argv
within each segment and parsing it is stage two, in
:mod:`statistic.normalize.extract`.
"""

from __future__ import annotations

import re

#: The CLI executable name a candidate segment must mention to be a call.
EXECUTABLE = "vaultspec-core"

#: Matches ANSI escape sequences: CSI colour/cursor codes and OSC strings. The
#: transcript result text is frequently colourised, so this runs before any
#: text matching.
_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")

#: Matches a heredoc introducer: ``<<TOKEN``, ``<<'TOKEN'``, ``<<"TOKEN"``, and
#: the ``<<-TOKEN`` indent-stripping form. Group 2 is the terminator word.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

#: Matches a single-line ``for`` loop. Group 1 is the loop variable, group 2 the
#: whitespace-separated item list, group 3 the loop body.
_FOR_RE = re.compile(
    r"\bfor\s+(\w+)\s+in\s+(.+?)\s*;\s*do\s+(.+?)\s*;?\s*done\b",
    re.DOTALL,
)

#: Splits a command on shell connectors. ``&&`` and ``||`` are matched before
#: their single-character counterparts so a two-character connector is never cut
#: in half; a bare ``|`` separates a pipe tail into its own segment, which then
#: falls out because it never mentions the executable.
_CONNECTOR_RE = re.compile(r"&&|\|\||;|\n|\|")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from *text*.

    Args:
        text: A raw command or result string, possibly colourised.

    Returns:
        The text with every CSI and OSC escape sequence removed.
    """
    return _ANSI_RE.sub("", text)


def normalize_newlines(text: str) -> str:
    """Fold Windows CRLF and lone CR into LF.

    Args:
        text: A raw command string with mixed line endings.

    Returns:
        The text with every ``\\r\\n`` and lone ``\\r`` replaced by ``\\n``.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def mask_heredocs(text: str) -> str:
    """Blank out heredoc bodies so embedded mentions never count as calls.

    A heredoc body runs from the line introducing ``<<TOKEN`` (exclusive) to the
    line whose stripped content equals ``TOKEN`` (inclusive). Both the body and
    the terminator line are dropped; the introducing line is kept, since it
    carries the real command. An unterminated heredoc masks to end of input.

    Args:
        text: A newline-normalized command string.

    Returns:
        The command with every heredoc body and terminator line removed.
    """
    lines = text.split("\n")
    result: list[str] = []
    terminator: str | None = None
    for line in lines:
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        match = _HEREDOC_RE.search(line)
        if match is not None:
            terminator = match.group(2)
        result.append(line)
    return "\n".join(result)


def unroll_for_loops(text: str) -> str:
    """Expand single-line ``for`` loops into one newline-joined segment per item.

    ``for s in A B C; do BODY; done`` becomes three copies of ``BODY`` with every
    ``$s``/``${s}`` reference substituted by ``A``, ``B``, and ``C`` in turn,
    joined by newlines so the connector split downstream separates them. A
    physical line firing N iterations therefore contributes N logical segments.

    Args:
        text: A command string after heredoc masking.

    Returns:
        The command with each recognised ``for`` loop replaced by its expansion.
    """

    def expand(match: re.Match[str]) -> str:
        var, items_raw, body = match.group(1), match.group(2), match.group(3)
        items = items_raw.split()
        reference = re.compile(
            r"\$\{" + re.escape(var) + r"\}|\$" + re.escape(var) + r"\b"
        )
        # Substitute each item with a callable replacement so backslashes in the
        # value (Windows paths in a real loop) are inserted literally rather than
        # parsed as regex replacement escapes.
        return "\n".join(
            reference.sub(lambda _, value=item: value, body) for item in items
        )

    return _FOR_RE.sub(expand, text)


def candidate_segments(command: str) -> list[str]:
    """Reduce a raw command string to the segments that invoke the executable.

    Runs the full stage-one pipeline - ANSI strip, newline normalization,
    heredoc masking, ``for``-loop unrolling, and connector splitting - then keeps
    only the segments that mention :data:`EXECUTABLE`. Each returned segment is
    stripped of surrounding whitespace and ready for argv parsing in stage two.

    Args:
        command: The raw shell command string as recorded in a transcript.

    Returns:
        The candidate segments that mention ``vaultspec-core``, in order. Empty
        when the command invokes the executable nowhere (for example, a mention
        that lives only inside a masked heredoc body).
    """
    text = strip_ansi(command)
    text = normalize_newlines(text)
    text = mask_heredocs(text)
    text = unroll_for_loops(text)
    segments = (segment.strip() for segment in _CONNECTOR_RE.split(text))
    return [segment for segment in segments if EXECUTABLE in segment]
