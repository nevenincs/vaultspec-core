"""The Claude Code project-transcript source adapter.

:class:`ClaudeSource` implements the
:class:`~statistic.parsers.base.TranscriptSource` protocol over the Claude Code
corpus - one JSON object per line under ``<root>/<project-slug>/*.jsonl`` plus
subagent transcripts under ``<project-slug>/subagents/agent-*.jsonl``. It owns
the Claude-specific schema quirks entirely, as the ADR mandates: ``tool_use`` to
``tool_result`` linkage by ``tool_use_id``, exit-status inference from the
``is_error`` boolean plus result-text patterns with the recurring
``distutils-precedence.pth`` venv-noise guard, and per-message token-cost
attribution divided across the shell tool calls a single message emits.

The corpus root is always an injected constructor parameter defaulting to the
operator's ``~/.claude/projects`` directory, so tests point the adapter at a
synthetic fixture tree and never touch a real home directory. The 30-day
activity window is a ``window_days`` parameter resolved against the wall clock at
construction, filtering on per-line activity timestamps rather than file mtime.
Command-string parsing is delegated wholesale to
:func:`~statistic.normalize.extract.extract_records`; this adapter only derives
the surrounding context.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from statistic.normalize.exit_status import ExitStatus
from statistic.normalize.extract import CommandContext, extract_records
from statistic.normalize.tokenize import EXECUTABLE

if TYPE_CHECKING:
    from collections.abc import Iterator

    from statistic.metrics.capability import CapabilityInventory
    from statistic.normalize.models import CallRecord

#: Shell tool names whose ``input.command`` may carry a vaultspec-core call.
_SHELL_TOOLS: frozenset[str] = frozenset({"Bash", "PowerShell"})

#: The filename prefix that marks a subagent transcript under ``subagents/``.
_AGENT_PREFIX = "agent-"

#: Result-text substrings that signal a genuine invocation failure once the
#: venv-noise block has been stripped.
_ERROR_PATTERNS: tuple[str, ...] = ("No such command", "Usage:", "Error")

#: The setuptools shim file whose non-fatal traceback ``uv run`` prints to
#: stderr. Its presence must never inflate the miss rate, so the whole traceback
#: block it introduces is stripped before error-text matching.
_VENV_NOISE_MARKER = "distutils-precedence.pth"

#: The trailer setuptools prints to close a ``.pth`` processing error block.
_VENV_NOISE_TRAILER = "Remainder of file ignored"

#: Matches a line that belongs to the venv-noise traceback body: a blank or
#: indented frame line, the ``Traceback`` header, a ``File "..."`` frame, or a
#: terminal exception/warning line. Used to bound the noise block when the
#: setuptools trailer is absent.
_VENV_NOISE_BODY = re.compile(
    r'^(?:\s|Traceback|File "|During handling|\w*(?:Error|Warning|Exception))'
)


@dataclass(frozen=True)
class ClaudeSession:
    """A discovered Claude transcript file and its project attribution.

    Attributes:
        path: The ``.jsonl`` transcript file.
        project: The project slug (the workspace-path directory name).
        subagent_role: The subagent role derived from a
            ``subagents/agent-<role>.jsonl`` filename, or ``None`` for a
            top-level parent-turn transcript.
    """

    path: Path
    project: str
    subagent_role: str | None


@dataclass(frozen=True)
class _Result:
    """A linked ``tool_result`` payload.

    Attributes:
        is_error: The ``is_error`` flag as recorded, defaulting to ``False``.
        text: The flattened result text, ANSI/CRLF still intact; the adapter
            strips venv noise from it during exit-status inference.
    """

    is_error: bool
    text: str


def _default_root() -> Path:
    """Return the operator's Claude projects directory.

    The path is derived from the home directory, so it carries no hardcoded
    username or drive letter. Callers pass an explicit root to point the adapter
    at a fixture tree.

    Returns:
        ``~/.claude/projects``.
    """
    return Path.home() / ".claude" / "projects"


def _parse_iso(value: object) -> datetime | None:
    """Parse an ISO8601 timestamp into a timezone-aware datetime.

    Args:
        value: A candidate timestamp, expected to be an ISO8601 string with a
            trailing ``Z``.

    Returns:
        The parsed timezone-aware datetime, or ``None`` when the value is not a
        parseable timestamp. A naive parse is assumed to be UTC.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _load_object(line: str) -> dict[str, Any] | None:
    """Parse one transcript line into a JSON object, tolerating malformed lines.

    Args:
        line: A single raw transcript line.

    Returns:
        The decoded object when the line is a JSON object, else ``None`` (a
        session-header or otherwise non-conforming line is skipped rather than
        raised on).
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _flatten_content(content: object) -> str:
    """Flatten a ``tool_result`` content value into a single text blob.

    The content is either a bare string or a list of ``{"type":"text",...}``
    fragments; both collapse to one string for pattern matching.

    Args:
        content: The ``content`` field of a ``tool_result`` entry.

    Returns:
        The concatenated result text, empty when nothing textual is present.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _strip_venv_noise(text: str) -> str:
    """Remove the ``distutils-precedence.pth`` traceback block from result text.

    The setuptools shim prints an ``Error processing line ...
    distutils-precedence.pth:`` header followed by a Python traceback. The header
    line carries the marker, so it and every following traceback frame - up to
    and including the ``Remainder of file ignored`` trailer, or to the first line
    that is not part of the traceback body when that trailer is absent - are
    dropped. This keeps the block's incidental ``Error``/``ImportError`` text from
    tripping error-pattern matching while leaving genuine surrounding output
    intact.

    Args:
        text: The flattened result text.

    Returns:
        The text with every venv-noise block removed.
    """
    lines = text.splitlines()
    result: list[str] = []
    index = 0
    while index < len(lines):
        if _VENV_NOISE_MARKER not in lines[index]:
            result.append(lines[index])
            index += 1
            continue
        index += 1
        while index < len(lines):
            line = lines[index]
            if _VENV_NOISE_TRAILER in line:
                index += 1
                break
            if line.strip() == "" or _VENV_NOISE_BODY.match(line):
                index += 1
                continue
            break
    return "\n".join(result)


def _is_by_design_nonzero(subcommand: tuple[str, ...]) -> bool:
    """Report whether a verb path exits non-zero by design.

    ``vault check``/``plan check`` findings, ``spec doctor`` warnings/errors, and
    a pending ``migrations status`` all return non-zero as a signal rather than a
    failure, so an error signal under these verbs is a *findings* status, never a
    miss.

    Args:
        subcommand: The resolved verb path of a record.

    Returns:
        ``True`` when the verb path is a documented by-design non-zero exit.
    """
    if subcommand[:2] == ("vault", "check"):
        return True
    if subcommand == ("vault", "plan", "check"):
        return True
    if subcommand in {("doctor",), ("spec", "doctor")}:
        return True
    return subcommand == ("migrations", "status")


class ClaudeSource:
    """Stream normalized calls from the Claude Code project-transcript corpus.

    Args:
        root: The Claude projects directory to walk. Defaults to the operator's
            ``~/.claude/projects`` and is injected explicitly by tests to point
            at a fixture tree.
        window_days: The activity-window width in days. Records whose activity
            timestamp is older than ``now - window_days`` are excluded.
        inventory: The declared-capability denominator used for verb-path
            resolution, or ``None`` for the heuristic fallback.
    """

    def __init__(
        self,
        root: Path | None = None,
        window_days: int = 30,
        inventory: CapabilityInventory | None = None,
    ) -> None:
        self._root = root if root is not None else _default_root()
        self._cutoff = datetime.now(tz=UTC) - timedelta(days=window_days)
        self._inventory = inventory

    def iter_sessions(self) -> Iterator[ClaudeSession]:
        """Yield each in-window transcript file across every project slug.

        Discovery walks each project-slug directory for its top-level ``*.jsonl``
        transcripts and its ``subagents/agent-*.jsonl`` files, applying a cheap
        first/last-line timestamp probe to skip files whose activity lies wholly
        before the window.

        Returns:
            A lazy iterator over the in-window :class:`ClaudeSession` handles.
        """
        if not self._root.is_dir():
            return
        for project_dir in sorted(self._root.iterdir()):
            if not project_dir.is_dir():
                continue
            slug = project_dir.name
            for transcript in sorted(project_dir.glob("*.jsonl")):
                if self._probe_in_window(transcript):
                    yield ClaudeSession(transcript, slug, None)
            subagents = project_dir / "subagents"
            if subagents.is_dir():
                for transcript in sorted(subagents.glob(f"{_AGENT_PREFIX}*.jsonl")):
                    role = transcript.stem[len(_AGENT_PREFIX) :]
                    if self._probe_in_window(transcript):
                        yield ClaudeSession(transcript, slug, role)

    def iter_calls(self, session: ClaudeSession) -> Iterator[CallRecord]:
        """Yield the normalized in-window calls of a single transcript.

        Results are collected first so a ``tool_use`` can be linked to its
        ``tool_result`` regardless of line order, then each assistant line's
        shell tool calls are parsed. Per-message token cost is divided across the
        vaultspec-core shell calls the message emits, and the exit status is
        inferred per record so a by-design non-zero verb never reads as a miss.

        Args:
            session: A handle previously yielded by :meth:`iter_sessions`.

        Returns:
            A lazy iterator over the session's normalized records, in transcript
            order.
        """
        try:
            text = session.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        lines = text.splitlines()
        results = self._collect_results(lines)
        for line in lines:
            obj = _load_object(line)
            if obj is None or obj.get("type") != "assistant":
                continue
            timestamp = _parse_iso(obj.get("timestamp"))
            if timestamp is None or timestamp < self._cutoff:
                continue
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            calls = self._shell_calls(message)
            if not calls:
                continue
            per_call_cost = self._per_call_cost(message, len(calls))
            for entry in calls:
                yield from self._records_for_call(
                    entry, obj, message, timestamp, per_call_cost, results, session
                )

    def _records_for_call(
        self,
        entry: dict[str, Any],
        obj: dict[str, Any],
        message: dict[str, Any],
        timestamp: datetime,
        token_cost: int | None,
        results: dict[str, _Result],
        session: ClaudeSession,
    ) -> Iterator[CallRecord]:
        """Emit the records for one ``tool_use`` shell call.

        Args:
            entry: The ``tool_use`` content entry.
            obj: The enclosing assistant line.
            message: The line's ``message`` object.
            timestamp: The parsed in-window activity timestamp.
            token_cost: The per-call token cost already divided across the
                message's shell calls.
            results: The tool-use-id to result map for this session.
            session: The owning session handle.

        Returns:
            A lazy iterator over the records the call's command string produces.
        """
        command = self._command_of(entry)
        if command is None:
            return
        parent = obj.get("parentUuid")
        session_id = self._text_or_none(obj.get("sessionId")) or session.path.stem
        context = CommandContext(
            source="claude",
            session_id=session_id,
            timestamp=timestamp,
            project=session.project,
            cwd=self._text_or_none(obj.get("cwd")) or "",
            exit_status=ExitStatus.OK,
            git_branch=self._text_or_none(obj.get("gitBranch")),
            token_cost=token_cost,
            subagent_role=session.subagent_role,
            model=self._text_or_none(message.get("model")),
            cli_version=self._text_or_none(obj.get("version")),
            retry_key=self._text_or_none(parent) or session_id,
        )
        result = results.get(self._text_or_none(entry.get("id")) or "")
        for record in extract_records(command, context, self._inventory):
            status = self._exit_status(result, record.subcommand)
            yield record.model_copy(update={"exit_status": status})

    def _collect_results(self, lines: list[str]) -> dict[str, _Result]:
        """Build the ``tool_use_id`` to result map for one transcript.

        Args:
            lines: Every raw line of the transcript.

        Returns:
            A mapping from ``tool_use_id`` to its linked :class:`_Result`.
        """
        results: dict[str, _Result] = {}
        for line in lines:
            obj = _load_object(line)
            if obj is None or obj.get("type") != "user":
                continue
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_result":
                    continue
                tool_use_id = self._text_or_none(item.get("tool_use_id"))
                if tool_use_id is None:
                    continue
                results[tool_use_id] = _Result(
                    is_error=bool(item.get("is_error", False)),
                    text=_flatten_content(item.get("content")),
                )
        return results

    def _shell_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the vaultspec-core shell ``tool_use`` entries of a message.

        Args:
            message: An assistant line's ``message`` object.

        Returns:
            The ``tool_use`` entries whose tool is a shell tool and whose command
            mentions the executable, in order.
        """
        content = message.get("content")
        if not isinstance(content, list):
            return []
        calls: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            if item.get("name") not in _SHELL_TOOLS:
                continue
            command = self._command_of(item)
            if command is not None and EXECUTABLE in command:
                calls.append(item)
        return calls

    @staticmethod
    def _command_of(entry: dict[str, Any]) -> str | None:
        """Extract the ``input.command`` string of a ``tool_use`` entry."""
        payload = entry.get("input")
        if not isinstance(payload, dict):
            return None
        command = payload.get("command")
        return command if isinstance(command, str) else None

    @staticmethod
    def _text_or_none(value: object) -> str | None:
        """Return *value* when it is a string, else ``None``."""
        return value if isinstance(value, str) else None

    @staticmethod
    def _per_call_cost(message: dict[str, Any], call_count: int) -> int | None:
        """Divide a message's total token usage across its shell calls.

        The Claude ``message.usage`` object is per assistant message, so when one
        message emits several tool calls the cost is split evenly across them.

        Args:
            message: The assistant line's ``message`` object.
            call_count: The number of vaultspec-core shell calls in the message.

        Returns:
            The per-call token cost, or ``None`` when no usage is recorded.
        """
        usage = message.get("usage")
        if not isinstance(usage, dict) or call_count <= 0:
            return None
        total = 0
        found = False
        for field in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            value = usage.get(field)
            if isinstance(value, int):
                total += value
                found = True
        if not found:
            return None
        return total // call_count

    @staticmethod
    def _exit_status(result: _Result | None, subcommand: tuple[str, ...]) -> ExitStatus:
        """Infer the exit status of a Claude call from its linked result.

        With no linked result the status is unknown. Otherwise venv noise is
        stripped, an error signal is taken from the ``is_error`` flag or the
        surviving error-text patterns, and any error signal under a by-design
        non-zero verb is reclassified as findings rather than a miss.

        Args:
            result: The linked result, or ``None`` when the call is unterminated.
            subcommand: The resolved verb path of the record.

        Returns:
            The inferred :class:`~statistic.normalize.exit_status.ExitStatus`.
        """
        if result is None:
            return ExitStatus.UNKNOWN
        cleaned = _strip_venv_noise(result.text)
        errored = result.is_error or any(
            pattern in cleaned for pattern in _ERROR_PATTERNS
        )
        if not errored:
            return ExitStatus.OK
        if _is_by_design_nonzero(subcommand):
            return ExitStatus.FINDINGS
        return ExitStatus.ERROR

    def _probe_in_window(self, path: Path) -> bool:
        """Cheaply decide whether a transcript may hold in-window activity.

        The first and last non-empty lines are probed for a timestamp; the file
        is skipped only when a timestamp is found and every probed timestamp is
        older than the window. When no timestamp can be read the file is admitted
        for a full parse rather than dropped.

        Args:
            path: The transcript file to probe.

        Returns:
            ``True`` when the file may contain in-window records.
        """
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return False
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return False
        probes = {non_empty[0], non_empty[-1]}
        seen = False
        for line in probes:
            obj = _load_object(line)
            if obj is None:
                continue
            timestamp = _parse_iso(obj.get("timestamp"))
            if timestamp is None:
                continue
            seen = True
            if timestamp >= self._cutoff:
                return True
        return not seen
