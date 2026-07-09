"""Stage two of normalization: turn candidate segments into ``CallRecord``s.

Where :mod:`statistic.normalize.tokenize` reduces a raw command string to the
segments that invoke ``vaultspec-core``, this module parses each segment into a
canonical :class:`~statistic.normalize.models.CallRecord`. For every segment it
locates the executable argv (skipping ``cd``, ``uv run --no-sync``, and env
prefixes, and dropping redirect tails), resolves the verb path against the
declared-capability inventory when one is supplied, folds short flags into their
long forms, extracts the ``--feature`` tag, and computes a SHA-256 hash over the
*normalized* command so the raw text is never retained.

The context every record needs beyond the command itself - source, session,
timestamp, cwd, exit status, cost, and linkage - is threaded in by the caller as
a :class:`CommandContext`; the future source adapters own its derivation. A
single physical line firing N loop iterations yields N records; a line invoking
the executable nowhere yields none.
"""

from __future__ import annotations

import hashlib
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from statistic.normalize.exit_status import ExitStatus
from statistic.normalize.models import CallRecord
from statistic.normalize.tokenize import EXECUTABLE, candidate_segments

if TYPE_CHECKING:
    from datetime import datetime

    from statistic.metrics.capability import CapabilityInventory

#: Short flag forms folded into their canonical long forms. Sourced from the
#: declared global and high-signal command-scoped flags of the CLI surface.
_SHORT_TO_LONG: dict[str, str] = {
    "-f": "--feature",
    "-t": "--target",
    "-d": "--debug",
    "-V": "--version",
    "-h": "--help",
}

#: Long-form flags that never take a value. Any other flag consumes the next
#: token as its value when that token is not itself a flag.
_BOOLEAN_FLAGS: frozenset[str] = frozenset(
    {
        "--json",
        "--dry-run",
        "--force",
        "--fix",
        "--all-steps",
        "--debug",
        "--help",
        "--version",
        "--strict",
        "--invalid",
        "--orphaned",
        "--quiet",
        "--verbose",
        "--no-sync",
    }
)


@dataclass(frozen=True)
class ParsedCommand:
    """The canonical shape of one ``vaultspec-core`` invocation.

    Attributes:
        verb: The leading verb, e.g. ``"vault"`` or ``"status"``; empty only for
            a degenerate bare-executable segment.
        subcommand: The resolved verb path as a tuple including the verb, e.g.
            ``("vault", "check", "links")``.
        flags: Canonical flag name to value mapping, short forms folded into long
            forms. A ``True`` value marks a presence-only flag; a string value
            carries the flag's argument.
        feature_tag: The value of ``--feature``/``-f`` when present, else
            ``None``.
        command_hash: SHA-256 hex digest of the normalized command tokens, never
            the raw text.
        unresolved: ``True`` when the segment could not be tokenized under either
            quoting rule and was parsed by the whitespace fallback of last
            resort. The ADR's no-silent-drop contract means such a segment must
            still surface as a record; the caller stamps it
            :attr:`~statistic.normalize.exit_status.ExitStatus.UNKNOWN` rather
            than trusting its inferred context status.
    """

    verb: str
    subcommand: tuple[str, ...]
    flags: dict[str, str | bool]
    feature_tag: str | None
    command_hash: str
    unresolved: bool = False


@dataclass(frozen=True)
class CommandContext:
    """The per-call context threaded in by a source adapter.

    Everything on a :class:`~statistic.normalize.models.CallRecord` that cannot
    be derived from the command string itself is carried here, so this module
    stays a pure string-to-record transform and file discovery lives entirely in
    the adapters.

    Attributes:
        source: The originating corpus, ``"claude"`` or ``"codex"``.
        session_id: The session identifier within the source corpus.
        timestamp: The activity timestamp of the call, timezone-aware.
        project: The project slug or cwd-derived project identifier.
        cwd: The working directory the command ran in.
        exit_status: The outcome class the adapter derived for the call.
        git_branch: The active git branch when the source records it, else
            ``None``.
        raw_exit_code: The explicit numeric exit code (Codex only), else
            ``None``.
        token_cost: The token cost attributed to the call, else ``None``.
        subagent_role: The subagent role that issued the call, else ``None``.
        model: The model identifier that issued the call, when recorded.
        cli_version: The vaultspec-core version in effect, when recorded.
        retry_key: The linkage anchor used to sequence records for miss
            detection, else ``None``.
    """

    source: Literal["claude", "codex"]
    session_id: str
    timestamp: datetime
    project: str
    cwd: str
    exit_status: ExitStatus = ExitStatus.UNKNOWN
    git_branch: str | None = None
    raw_exit_code: int | None = None
    token_cost: int | None = None
    subagent_role: str | None = None
    model: str | None = None
    cli_version: str | None = None
    retry_key: str | None = None


def _split_segment(segment: str) -> list[str] | None:
    """Tokenize a candidate segment into an argv, tolerating quoting styles.

    Args:
        segment: A single candidate segment that mentions the executable.

    Returns:
        The token list, or ``None`` when the segment cannot be tokenized under
        either POSIX or non-POSIX quoting rules.
    """
    for posix in (True, False):
        try:
            return shlex.split(segment, posix=posix)
        except ValueError:
            continue
    return None


def _locate_executable(tokens: list[str]) -> list[str] | None:
    """Return the argv from the ``vaultspec-core`` token onward.

    This drops every wrapper before the executable - ``cd`` and its argument in a
    prior segment, ``uv run --no-sync``, and ``VAR=value`` env prefixes - because
    the executable token is simply sought positionally.

    Args:
        tokens: The tokenized segment.

    Returns:
        The argv beginning at ``vaultspec-core``, or ``None`` when the token is
        absent (for example, a bare mention inside an unrelated string token).
    """
    for index, token in enumerate(tokens):
        if token == EXECUTABLE:
            return tokens[index:]
    return None


def _strip_redirects(argv: list[str]) -> list[str]:
    """Drop redirect operators and their targets from an argv.

    Handles the self-contained ``2>&1`` form, attached targets such as
    ``2>/dev/null``, and the operator-plus-target pair ``> out.txt``.

    Args:
        argv: The argv from the executable onward.

    Returns:
        The argv with redirect tails removed.
    """
    result: list[str] = []
    skip_next = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token in {">", ">>", "<", "2>", "1>", "&>", "&>>"}:
            skip_next = True
            continue
        if token.startswith(("2>", "1>", "&>", ">", "<")):
            continue
        result.append(token)
    return result


def _resolve_verb_path(
    body: list[str],
    inventory: CapabilityInventory | None,
) -> tuple[str, ...]:
    """Resolve the verb path from an argv body's leading positional tokens.

    The leading run of non-flag tokens is the positional prefix. When an
    *inventory* is supplied, the verb path is the longest prefix of that run the
    inventory declares, so a positional argument (``status feat``, ``vault add
    exec``) is never mistaken for a deeper subcommand. Without an inventory, or
    when no prefix is declared (an undeclared candidate miss), the verb path
    falls back to the leading run of lowercase kebab-case tokens.

    Args:
        body: The argv after the executable token, redirects already stripped.
        inventory: The declared-capability denominator, or ``None``.

    Returns:
        The resolved verb path as a tuple, possibly empty for a bare executable.
    """
    positional: list[str] = []
    for token in body:
        if token.startswith("-"):
            break
        positional.append(token)

    if inventory is not None:
        for length in range(len(positional), 0, -1):
            candidate = tuple(positional[:length])
            if inventory.declares_verb_path(candidate):
                return candidate

    resolved: list[str] = []
    for token in positional:
        if token and token[0].islower() and all(c.islower() or c == "-" for c in token):
            resolved.append(token)
        else:
            break
    return tuple(resolved)


def _canonical_flag(name: str) -> str:
    """Fold a short flag form into its long form, leaving long forms untouched."""
    return _SHORT_TO_LONG.get(name, name)


def _process_remainder(
    tokens: list[str],
) -> tuple[dict[str, str | bool], list[str]]:
    """Parse flags and build canonical tokens from an argv remainder.

    In a single pass this both extracts the canonical flag mapping and emits the
    canonical token sequence used for hashing, so ``-f x``, ``--feature x``, and
    ``--feature=x`` all normalize identically. Positional arguments are preserved
    in the canonical sequence - they distinguish otherwise-identical loop
    iterations - but do not enter the flag mapping.

    Args:
        tokens: The argv tokens after the resolved verb path.

    Returns:
        A pair of the canonical flag mapping and the canonical token list.
    """
    flags: dict[str, str | bool] = {}
    canonical: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            canonical.append(token)
            index += 1
            continue
        name, separator, inline = token.partition("=")
        flag = _canonical_flag(name)
        if separator:
            flags[flag] = inline
            canonical.append(f"{flag}={inline}")
            index += 1
        elif flag in _BOOLEAN_FLAGS:
            flags[flag] = True
            canonical.append(flag)
            index += 1
        elif index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
            value = tokens[index + 1]
            flags[flag] = value
            canonical.append(f"{flag}={value}")
            index += 2
        else:
            flags[flag] = True
            canonical.append(flag)
            index += 1
    return flags, canonical


def _hash_command(verb_path: tuple[str, ...], canonical_remainder: list[str]) -> str:
    """Compute the SHA-256 digest of the normalized command tokens.

    Args:
        verb_path: The resolved verb path.
        canonical_remainder: The canonical flag-and-argument tokens.

    Returns:
        The hex digest of ``vaultspec-core <verb path> <remainder>``.
    """
    normalized = " ".join([EXECUTABLE, *verb_path, *canonical_remainder])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _build_parsed(
    tokens: list[str],
    inventory: CapabilityInventory | None,
    *,
    unresolved: bool,
) -> ParsedCommand | None:
    """Assemble a :class:`ParsedCommand` from a located token list.

    Args:
        tokens: The tokenized (or whitespace-split) segment.
        inventory: The declared-capability denominator, or ``None``.
        unresolved: Whether these tokens came from the whitespace fallback rather
            than a clean ``shlex`` tokenization.

    Returns:
        The parsed command, or ``None`` when no executable argv is locatable or
        the segment resolves to a bare executable mention with neither a verb nor
        a flag.
    """
    argv = _locate_executable(tokens)
    if argv is None:
        return None
    body = _strip_redirects(argv[1:])
    verb_path = _resolve_verb_path(body, inventory)
    flags, canonical = _process_remainder(body[len(verb_path) :])
    if not verb_path and not flags:
        return None
    feature = flags.get("--feature")
    feature_tag = feature if isinstance(feature, str) else None
    return ParsedCommand(
        verb=verb_path[0] if verb_path else "",
        subcommand=verb_path,
        flags=flags,
        feature_tag=feature_tag,
        command_hash=_hash_command(verb_path, canonical),
        unresolved=unresolved,
    )


def _parse_segment(
    segment: str,
    inventory: CapabilityInventory | None,
) -> ParsedCommand | None:
    """Parse one candidate segment into a :class:`ParsedCommand`.

    When the segment tokenizes cleanly the parse is exact. When it cannot be
    tokenized under either quoting rule - a pathological quoting shape - the
    segment is not dropped: a whitespace fallback locates the executable and
    resolves a best-effort verb of last resort, flagged ``unresolved`` so the
    caller records it as ``UNKNOWN`` instead of silently discarding it, honoring
    the ADR's no-silent-drop contract.

    Args:
        segment: A candidate segment mentioning the executable.
        inventory: The declared-capability denominator, or ``None``.

    Returns:
        The parsed command, or ``None`` when the segment holds no locatable
        executable argv or resolves to a bare executable mention with neither a
        verb nor a flag (for example, the word appearing as an argument to
        another command).
    """
    tokens = _split_segment(segment)
    if tokens is not None:
        return _build_parsed(tokens, inventory, unresolved=False)
    return _build_parsed(segment.split(), inventory, unresolved=True)


def parse_command(
    command: str,
    inventory: CapabilityInventory | None = None,
) -> list[ParsedCommand]:
    """Parse a raw command string into zero or more canonical commands.

    Runs stage one (:func:`~statistic.normalize.tokenize.candidate_segments`) to
    obtain the executable-bearing segments, then parses each into a
    :class:`ParsedCommand`. A ``for`` loop firing N iterations yields N commands;
    a command invoking the executable nowhere yields an empty list.

    Args:
        command: The raw shell command string from a transcript.
        inventory: The declared-capability denominator used to resolve verb-path
            depth. When ``None``, verb paths fall back to a leading kebab-case
            heuristic.

    Returns:
        The parsed commands in order. A segment that cannot be tokenized is
        recovered by the whitespace fallback and flagged ``unresolved`` rather
        than dropped; only a segment holding no locatable executable argv (or a
        bare mention with neither verb nor flag) yields nothing.
    """
    parsed: list[ParsedCommand] = []
    for segment in candidate_segments(command):
        command_parse = _parse_segment(segment, inventory)
        if command_parse is not None:
            parsed.append(command_parse)
    return parsed


def extract_records(
    command: str,
    context: CommandContext,
    inventory: CapabilityInventory | None = None,
) -> list[CallRecord]:
    """Transform a raw command string into normalized ``CallRecord``s.

    Each parsed command is combined with the shared *context* into a validated
    :class:`~statistic.normalize.models.CallRecord`. The command itself survives
    only as :attr:`~statistic.normalize.models.CallRecord.command_hash`; no raw
    text is retained on the record.

    Args:
        command: The raw shell command string from a transcript.
        context: The per-call context the source adapter derived.
        inventory: The declared-capability denominator for verb-path resolution,
            or ``None`` for the heuristic fallback.

    Returns:
        The normalized records, one per parsed invocation, in order.
    """
    return [
        CallRecord(
            source=context.source,
            session_id=context.session_id,
            timestamp=context.timestamp,
            project=context.project,
            cwd=context.cwd,
            git_branch=context.git_branch,
            verb=parsed.verb,
            subcommand=parsed.subcommand,
            flags=parsed.flags,
            feature_tag=parsed.feature_tag,
            command_hash=parsed.command_hash,
            exit_status=(
                ExitStatus.UNKNOWN if parsed.unresolved else context.exit_status
            ),
            raw_exit_code=context.raw_exit_code,
            token_cost=context.token_cost,
            subagent_role=context.subagent_role,
            model=context.model,
            cli_version=context.cli_version,
            retry_key=context.retry_key,
        )
        for parsed in parse_command(command, inventory)
    ]
