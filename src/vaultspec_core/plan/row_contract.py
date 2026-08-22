"""Input validation for the text a plan mutation writes into the row grammar.

The plan document *is* the data structure: a Step's action and scope, and a
Wave or Phase title, are stored as bare text inside a line whose shape carries
structural meaning. That makes a handful of characters load-bearing rather than
cosmetic, and a mutation that writes one of them into the wrong field emits a
line the parser reads back as something other than what was asked for.

Before issue #313 nothing checked for them, so ``--action "Ground x; do y"``
was accepted, serialised, written, and only *then* caught by the post-write
verifier - after the malformed row had already reached the file. The parser is
now anchored on the trailing backticked scope clause, which makes a semicolon
inside an action round-trip cleanly, but the remaining characters below cannot
be made to round-trip by any parser and must be refused at the boundary
instead:

- **Newlines** would split one row across two lines, so the tail becomes loose
  prose and the row loses its scope.
- **A backtick in a scope** closes the scope span early, so the remainder of
  the clause escapes the code fence and the row reads back truncated.
- **A semicolon in a scope** re-opens the action / scope ambiguity from the
  other side.
- **HTML comment delimiters** would comment out the rest of the document, or
  end a comment the document meant to keep - now that the parser correctly
  ignores commented spans, an injected ``<!--`` would make live rows vanish.

Refusing at the boundary is what makes the guarantee "a command that exits
non-zero leaves the plan byte-identical" cheap to keep: the write never starts.
"""

from __future__ import annotations

from vaultspec_core.plan.commands._errors import PlanCommandError

__all__ = [
    "RowContentError",
    "validate_action",
    "validate_intent",
    "validate_scope",
    "validate_title",
]

#: Sequences that would terminate or open an HTML comment mid-document.
_COMMENT_DELIMITERS = ("<!--", "-->")


class RowContentError(PlanCommandError, ValueError):
    """Text supplied to a plan mutation cannot be written to the row grammar.

    Raised *before* any serialisation or write, so a rejected value leaves the
    document byte-identical. Subclasses :class:`PlanCommandError` so the CLI's
    ``render_user_errors`` decorator renders it as a one-line error and the MCP
    tools surface it as an ``isError`` result, exactly like every other typed
    command failure.
    """


def _reject_newlines(value: str, *, field: str) -> None:
    """Refuse *value* when it would break its single line in two."""
    if "\n" in value or "\r" in value:
        msg = (
            f"{field} may not contain a line break: a plan row is a single "
            "line, and a break would split the row so its tail is read as "
            "prose. Supply the text on one line."
        )
        raise RowContentError(msg)


def _reject_comment_delimiters(value: str, *, field: str) -> None:
    """Refuse *value* when it carries an HTML comment delimiter."""
    for delimiter in _COMMENT_DELIMITERS:
        if delimiter in value:
            msg = (
                f"{field} may not contain {delimiter!r}: HTML comment "
                "delimiters change which part of the document is structure "
                "and which is commentary, so writing one would hide or "
                "expose rows the mutation never mentioned."
            )
            raise RowContentError(msg)


def _require_content(value: str, *, field: str) -> str:
    """Return *value* stripped, refusing an empty or whitespace-only field."""
    stripped = value.strip()
    if not stripped:
        msg = f"{field} may not be empty."
        raise RowContentError(msg)
    return stripped


def validate_action(action: str) -> str:
    """Return the normalised Step action, or raise :class:`RowContentError`.

    A semicolon is permitted: the parser anchors the split on the trailing
    backticked scope clause, so an action that contains one survives the round
    trip (issue #313).
    """
    _reject_newlines(action, field="A Step action")
    _reject_comment_delimiters(action, field="A Step action")
    return _require_content(action, field="A Step action")


def validate_scope(scope: str) -> str:
    """Return the normalised Step scope, or raise :class:`RowContentError`.

    The scope is emitted inside a backtick span terminated by ``;``-separated
    row grammar, so neither character can appear in the value itself.
    """
    _reject_newlines(scope, field="A Step scope")
    _reject_comment_delimiters(scope, field="A Step scope")
    normalised = _require_content(scope.strip().strip("`"), field="A Step scope")
    for character, reason in (
        ("`", "closes the scope's code span early"),
        (";", "re-opens the action / scope split"),
    ):
        if character in normalised:
            msg = (
                f"A Step scope may not contain {character!r}: it {reason}, so "
                "the row would read back as something other than what was "
                "written. Name the file or area without it."
            )
            raise RowContentError(msg)
    return normalised


def validate_title(title: str, *, container: str) -> str:
    """Return the normalised Wave or Phase title, or raise.

    *container* names the container kind (``"Wave"`` / ``"Phase"``) for the
    error message.
    """
    field = f"A {container} title"
    _reject_newlines(title, field=field)
    _reject_comment_delimiters(title, field=field)
    return _require_content(title, field=field)


def validate_intent(intent: str, *, container: str) -> str:
    """Return the normalised intent paragraph, or raise.

    Intent prose is multi-line by nature, so line breaks are allowed; only the
    comment delimiters are refused.
    """
    field = f"A {container} intent"
    _reject_comment_delimiters(intent, field=field)
    return _require_content(intent, field=field)
