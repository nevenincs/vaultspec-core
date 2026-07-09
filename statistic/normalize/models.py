"""The canonical normalized call record shared across every analysis layer.

:class:`CallRecord` is the single normalization boundary at which the two
divergent transcript schemas (Claude Code project JSONL and Codex rollout
sessions) are resolved into one comparable shape. Every metric family consumes
an iterable of these records, so the schema divergence between the two corpora
is reconciled here exactly once. The model is a Pydantic model rather than a
stdlib dataclass because real transcript lines are frequently malformed, and
validation at the parse boundary keeps coercion and null-handling out of every
adapter.

The record carries only derived and hashed values: the command itself appears
solely as :attr:`CallRecord.command_hash`, a SHA-256 digest of the normalized
command, never as raw text. This keeps the record safe to serialize into the
committed-code-adjacent ``records.jsonl`` output without leaking command
bodies, secrets, or personal paths.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from statistic.normalize.exit_status import ExitStatus


class CallRecord(BaseModel):
    """A single normalized vaultspec-core invocation from either corpus.

    Attributes:
        source: The originating corpus, ``"claude"`` or ``"codex"``.
        session_id: The session identifier within the source corpus.
        timestamp: The activity timestamp of the call, always timezone-aware.
            The 30-day activity window filters on this value, never on file
            mtime.
        project: The project slug or cwd-derived project identifier.
        cwd: The working directory the command ran in.
        git_branch: The active git branch, when the source records it (Claude
            only); ``None`` otherwise.
        verb: The leading vaultspec-core verb, e.g. ``"vault"`` or ``"status"``.
        subcommand: The subcommand path as a tuple of segments, e.g.
            ``("vault", "check", "links")``. The tuple includes the leading
            verb so it is a complete verb path.
        flags: Canonical flag name to value mapping, with short forms folded
            into their long forms. A boolean value marks a presence-only flag;
            a string value carries the flag's argument.
        feature_tag: The value of ``--feature``/``-f`` when present, else
            ``None``.
        command_hash: SHA-256 hex digest of the normalized command. Never the
            raw command text.
        exit_status: The outcome class of the call.
        raw_exit_code: The explicit numeric exit code when the source records
            one (Codex only); ``None`` otherwise.
        token_cost: The approximate token cost attributed to the call, or
            ``None`` when the source does not permit attribution.
        subagent_role: The subagent role that issued the call, when the call
            originated from a subagent session; ``None`` otherwise.
        model: The model identifier that issued the call, when recorded.
        cli_version: The vaultspec-core version in effect, when recorded.
        retry_key: The linkage anchor (Claude ``parentUuid`` or Codex
            ``call_id`` chain anchor) used to sequence records for miss
            detection; ``None`` when no anchor is available.
    """

    model_config = ConfigDict(frozen=True)

    source: Literal["claude", "codex"]
    session_id: str
    timestamp: datetime
    project: str
    cwd: str
    git_branch: str | None = None
    verb: str
    subcommand: tuple[str, ...]
    flags: dict[str, str | bool]
    feature_tag: str | None = None
    command_hash: str
    exit_status: ExitStatus
    raw_exit_code: int | None = None
    token_cost: int | None = None
    subagent_role: str | None = None
    model: str | None = None
    cli_version: str | None = None
    retry_key: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        """Reject naive timestamps so the window filter is unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "timestamp must be timezone-aware"
            raise ValueError(msg)
        return value
