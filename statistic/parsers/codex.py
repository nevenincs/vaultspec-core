"""The Codex rollout-session source adapter.

:class:`CodexSource` implements the
:class:`~statistic.parsers.base.TranscriptSource` protocol over the Codex
corpus - one JSON object per line under
``<root>/sessions/<yyyy>/<mm>/<dd>/rollout-*.jsonl`` and
``<root>/archived_sessions/rollout-*.jsonl``. It owns the Codex-specific schema
quirks entirely, as the ADR mandates: ``function_call`` payloads whose
``arguments`` field is a JSON *string* to be decoded, ``function_call_output``
linkage by ``call_id`` carrying an explicit ``Exit code: N`` line, and token
cost derived from the deltas between the cumulative ``token_count`` snapshots
bracketing a call.

The corpus root is always an injected constructor parameter. Its default honors
the ``CODEX_HOME`` environment variable when set and otherwise falls back to the
operator's ``~/.codex`` directory, so tests point the adapter at a synthetic
fixture tree and never touch a real home directory. The 30-day activity window is
a ``window_days`` parameter resolved against the wall clock at construction,
filtering on per-line activity timestamps rather than file mtime. Command-string
parsing is delegated wholesale to
:func:`~statistic.normalize.extract.extract_records`; this adapter only derives
the surrounding context.
"""

from __future__ import annotations

import json
import os
import re
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

#: The environment variable that overrides the Codex home directory.
_CODEX_HOME_ENV = "CODEX_HOME"

#: The tool name a ``function_call`` payload must carry to be a shell call in
#: current Codex builds.
_SHELL_FUNCTION = "shell_command"

#: Matches the explicit numeric exit code a ``function_call_output`` reports.
_EXIT_CODE_RE = re.compile(r"Exit code:\s*(-?\d+)")


def _default_root() -> Path:
    """Return the Codex home directory.

    The ``CODEX_HOME`` environment variable wins when set; otherwise the path is
    derived from the home directory, so nothing hardcodes a username or drive
    letter. Callers pass an explicit root to point the adapter at a fixture tree.

    Returns:
        The ``CODEX_HOME`` directory when set, else ``~/.codex``.
    """
    override = os.environ.get(_CODEX_HOME_ENV)
    if override:
        return Path(override)
    return Path.home() / ".codex"


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
    """Parse one rollout line into a JSON object, tolerating malformed lines.

    Args:
        line: A single raw rollout line.

    Returns:
        The decoded object when the line is a JSON object, else ``None``.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _project_from_cwd(cwd: str) -> str:
    """Derive a project identifier from a working-directory path.

    The last non-empty path component names the project. Splitting handles both
    POSIX and Windows separators so a synthetic ``/work/proj`` and a real
    backslash path resolve alike.

    Args:
        cwd: The working directory the call ran in.

    Returns:
        The final path component, or the whole value when it has no separator.
    """
    parts = [part for part in re.split(r"[\\/]+", cwd) if part]
    return parts[-1] if parts else cwd


def _is_by_design_nonzero(subcommand: tuple[str, ...]) -> bool:
    """Report whether a verb path exits non-zero by design.

    ``vault check``/``plan check`` findings, ``spec doctor`` warnings/errors, and
    a pending ``migrations status`` all return non-zero as a signal rather than a
    failure, so a non-zero exit under these verbs is a *findings* status, never a
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


class CodexSource:
    """Stream normalized calls from the Codex rollout-session corpus.

    Args:
        root: The Codex home directory to walk. Defaults to ``CODEX_HOME`` or
            ``~/.codex`` and is injected explicitly by tests to point the adapter
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

    def iter_sessions(self) -> Iterator[Path]:
        """Yield each in-window rollout file across live and archived sessions.

        Discovery globs ``sessions/<yyyy>/<mm>/<dd>/rollout-*.jsonl`` and
        ``archived_sessions/rollout-*.jsonl``, applying a cheap first/last-line
        timestamp probe to skip files whose activity lies wholly before the
        window.

        Returns:
            A lazy iterator over the in-window rollout file paths.
        """
        seen: set[Path] = set()
        for directory in (self._root / "sessions", self._root / "archived_sessions"):
            if not directory.is_dir():
                continue
            for rollout in sorted(directory.glob("**/rollout-*.jsonl")):
                if rollout in seen:
                    continue
                seen.add(rollout)
                if self._probe_in_window(rollout):
                    yield rollout

    def iter_calls(self, session: Path) -> Iterator[CallRecord]:
        """Yield the normalized in-window calls of a single rollout.

        Outputs and cumulative token snapshots are collected first so a
        ``function_call`` can be linked to its ``function_call_output`` by
        ``call_id`` and bracketed by the token snapshots around it. The pass then
        replays the rollout in order, tracking session and turn context, and
        emits a record per parsed command with its explicit exit code mapped onto
        the shared status vocabulary.

        Args:
            session: A rollout path previously yielded by :meth:`iter_sessions`.

        Returns:
            A lazy iterator over the rollout's normalized records, in transcript
            order.
        """
        try:
            text = session.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        raw = text.splitlines()
        objects = [_load_object(line) for line in raw]
        outputs = self._collect_outputs(objects)
        snapshots = self._collect_snapshots(objects)

        session_id = session.stem
        cli_version: str | None = None
        subagent_role: str | None = None
        cwd = ""
        model: str | None = None

        for index, obj in enumerate(objects):
            if obj is None:
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = obj.get("type")
            if kind == "session_meta":
                session_id = self._text_or_none(payload.get("session_id")) or session_id
                version = self._text_or_none(payload.get("cli_version"))
                cli_version = version or cli_version
                cwd = self._text_or_none(payload.get("cwd")) or cwd
                subagent_role = self._subagent_role(payload) or subagent_role
                continue
            if kind == "turn_context":
                cwd = self._text_or_none(payload.get("cwd")) or cwd
                model = self._text_or_none(payload.get("model")) or model
                continue
            if kind != "response_item" or payload.get("type") != "function_call":
                continue
            if payload.get("name") != _SHELL_FUNCTION:
                continue
            yield from self._records_for_call(
                obj,
                payload,
                index,
                outputs,
                snapshots,
                session_id,
                cwd,
                model,
                cli_version,
                subagent_role,
            )

    def _records_for_call(
        self,
        obj: dict[str, Any],
        payload: dict[str, Any],
        index: int,
        outputs: dict[str, int],
        snapshots: list[tuple[int, int]],
        session_id: str,
        cwd: str,
        model: str | None,
        cli_version: str | None,
        subagent_role: str | None,
    ) -> Iterator[CallRecord]:
        """Emit the records for one ``function_call`` shell call.

        Args:
            obj: The enclosing rollout line.
            payload: The line's ``function_call`` payload.
            index: The line's ordinal position, used to bracket token snapshots.
            outputs: The call-id to exit-code map for this rollout.
            snapshots: The ordered ``(index, cumulative-total)`` token snapshots.
            session_id: The current session identifier.
            cwd: The current working directory from session or turn context.
            model: The current turn model.
            cli_version: The Codex CLI version.
            subagent_role: The subagent role when the session is a subagent.

        Returns:
            A lazy iterator over the records the call's command string produces.
        """
        arguments = self._decode_arguments(payload.get("arguments"))
        if arguments is None:
            return
        command = arguments.get("command")
        if not isinstance(command, str) or EXECUTABLE not in command:
            return
        timestamp = _parse_iso(obj.get("timestamp"))
        if timestamp is None or timestamp < self._cutoff:
            return
        call_id = self._text_or_none(payload.get("call_id"))
        exit_code = outputs.get(call_id) if call_id is not None else None
        effective_cwd = cwd or (self._text_or_none(arguments.get("workdir")) or "")
        context = CommandContext(
            source="codex",
            session_id=session_id,
            timestamp=timestamp,
            project=_project_from_cwd(effective_cwd),
            cwd=effective_cwd,
            exit_status=ExitStatus.OK,
            git_branch=None,
            raw_exit_code=exit_code,
            token_cost=self._bracket_delta(index, snapshots),
            subagent_role=subagent_role,
            model=model,
            cli_version=cli_version,
            retry_key=call_id,
        )
        for record in extract_records(command, context, self._inventory):
            status = self._exit_status(exit_code, record.subcommand)
            yield record.model_copy(
                update={"exit_status": status, "raw_exit_code": exit_code}
            )

    @staticmethod
    def _collect_outputs(objects: list[dict[str, Any] | None]) -> dict[str, int]:
        """Build the ``call_id`` to exit-code map for one rollout.

        Args:
            objects: Every parsed rollout line, ``None`` for malformed lines.

        Returns:
            A mapping from ``call_id`` to the numeric exit code parsed from its
            ``function_call_output`` text; entries without a parseable code are
            omitted.
        """
        outputs: dict[str, int] = {}
        for obj in objects:
            if obj is None or obj.get("type") != "response_item":
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "function_call_output":
                continue
            call_id = payload.get("call_id")
            if not isinstance(call_id, str):
                continue
            text = CodexSource._output_text(payload.get("output"))
            match = _EXIT_CODE_RE.search(text)
            if match is not None:
                outputs[call_id] = int(match.group(1))
        return outputs

    @staticmethod
    def _output_text(output: object) -> str:
        """Flatten a ``function_call_output`` output field into text.

        Args:
            output: The ``output`` field, a bare string or a wrapper object.

        Returns:
            The output text carrying the ``Exit code:`` line.
        """
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            content = output.get("content")
            if isinstance(content, str):
                return content
        return ""

    @staticmethod
    def _collect_snapshots(
        objects: list[dict[str, Any] | None],
    ) -> list[tuple[int, int]]:
        """Collect the cumulative token-usage snapshots of one rollout.

        Args:
            objects: Every parsed rollout line, ``None`` for malformed lines.

        Returns:
            The ``(line-index, cumulative-total)`` snapshots in order, read from
            each ``token_count`` event's ``info.total_token_usage.total``.
        """
        snapshots: list[tuple[int, int]] = []
        for index, obj in enumerate(objects):
            if obj is None or obj.get("type") != "event_msg":
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            usage = info.get("total_token_usage")
            if not isinstance(usage, dict):
                continue
            total = usage.get("total")
            if isinstance(total, int):
                snapshots.append((index, total))
        return snapshots

    @staticmethod
    def _bracket_delta(index: int, snapshots: list[tuple[int, int]]) -> int | None:
        """Compute the token cost of a call from the snapshots bracketing it.

        The cost is the difference between the first cumulative snapshot after the
        call and the last one before it. Attribution is best-effort: when the call
        is not bracketed on both sides the cost is left unattributed.

        Args:
            index: The call's line ordinal.
            snapshots: The ordered ``(index, cumulative-total)`` snapshots.

        Returns:
            The bracketed token delta, or ``None`` when no bracketing pair exists.
        """
        before: int | None = None
        after: int | None = None
        for snap_index, total in snapshots:
            if snap_index < index:
                before = total
            elif snap_index > index and after is None:
                after = total
                break
        if before is None or after is None:
            return None
        return after - before

    @staticmethod
    def _decode_arguments(arguments: object) -> dict[str, Any] | None:
        """Decode the JSON-string ``arguments`` field of a shell call.

        Args:
            arguments: The ``arguments`` field, a JSON string in current builds.

        Returns:
            The decoded argument object, or ``None`` when it is absent or not a
            decodable JSON object.
        """
        if not isinstance(arguments, str):
            return None
        try:
            decoded = json.loads(arguments)
        except ValueError:
            return None
        if not isinstance(decoded, dict):
            return None
        return {str(key): value for key, value in decoded.items()}

    @staticmethod
    def _subagent_role(payload: dict[str, Any]) -> str | None:
        """Extract the subagent role from a ``session_meta`` payload.

        Args:
            payload: The ``session_meta`` payload.

        Returns:
            The declared ``agent_role`` when the session is a subagent, else
            ``None``.
        """
        source = payload.get("source")
        is_subagent = payload.get("thread_source") == "subagent" or (
            isinstance(source, dict) and source.get("subagent") is not None
        )
        role = payload.get("agent_role")
        if is_subagent and isinstance(role, str):
            return role
        return role if isinstance(role, str) else None

    @staticmethod
    def _text_or_none(value: object) -> str | None:
        """Return *value* when it is a string, else ``None``."""
        return value if isinstance(value, str) else None

    @staticmethod
    def _exit_status(exit_code: int | None, subcommand: tuple[str, ...]) -> ExitStatus:
        """Map a Codex numeric exit code onto the shared status vocabulary.

        A zero exit is success; a non-zero exit under a by-design non-zero verb is
        a findings status; any other non-zero exit is a genuine error. An absent
        code is unknown.

        Args:
            exit_code: The explicit numeric exit code, or ``None`` when unlinked.
            subcommand: The resolved verb path of the record.

        Returns:
            The mapped :class:`~statistic.normalize.exit_status.ExitStatus`.
        """
        if exit_code is None:
            return ExitStatus.UNKNOWN
        if exit_code == 0:
            return ExitStatus.OK
        if _is_by_design_nonzero(subcommand):
            return ExitStatus.FINDINGS
        return ExitStatus.ERROR

    def _probe_in_window(self, path: Path) -> bool:
        """Cheaply decide whether a rollout may hold in-window activity.

        The first and last non-empty lines are probed for a timestamp; the file
        is skipped only when a timestamp is found and every probed timestamp is
        older than the window. When no timestamp can be read the file is admitted
        for a full parse rather than dropped.

        Args:
            path: The rollout file to probe.

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
