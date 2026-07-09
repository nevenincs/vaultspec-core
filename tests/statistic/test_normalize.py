"""Tests for the two-stage command normalizer.

These assert the exact records the normalizer yields from synthetic command
strings covering every documented command shape: ``cd``/``uv run`` wrappers,
multi-line connector chaining, single-line ``for``-loop unrolling, heredoc false
positives, redirect and pipe tails, short-flag canonicalization, boolean flags,
ANSI/CRLF noise, and command hashing. Every input is a synthetic string with no
usernames, absolute machine paths, or operator dates; where a working directory
is needed an abstract ``/work/proj`` placeholder stands in, and the per-call
timestamp is taken from the wall clock since no assertion depends on it.

Verb-path depth is resolved against the committed, redacted capability fixture
that P02 already asserts, so ``status feat`` resolves to the ``status`` verb and
``vault plan step check PLAN S01`` to the four-segment path with its trailing
tokens carried only into the command hash.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from statistic.metrics.capability import (
    CapabilityInventory,
    parse_capability_inventory,
)
from statistic.normalize.exit_status import ExitStatus
from statistic.normalize.extract import (
    CommandContext,
    extract_records,
    parse_command,
)
from statistic.normalize.tokenize import candidate_segments

_FIXTURE = Path(__file__).parent / "fixtures" / "cli_reference.md"


def _inventory() -> CapabilityInventory:
    """Parse the committed capability fixture into an inventory."""
    return parse_capability_inventory(_FIXTURE)


def _context() -> CommandContext:
    """A synthetic per-call context with no operator-specific state."""
    return CommandContext(
        source="claude",
        session_id="synthetic-session",
        timestamp=datetime.now(tz=UTC),
        project="proj",
        cwd="/work/proj",
        exit_status=ExitStatus.OK,
    )


def test_cd_and_uv_run_wrappers_yield_one_status_record() -> None:
    """A cd-prefixed, uv-run-wrapped invocation yields one record, verb status."""
    command = 'cd "/work/proj" && uv run --no-sync vaultspec-core status feat'
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].verb == "status"
    assert parsed[0].subcommand == ("status",)
    assert parsed[0].flags == {}


def test_multiline_connector_chain_yields_two_records() -> None:
    """Two executable calls chained across lines yield two distinct records."""
    command = (
        "uv run --no-sync vaultspec-core status\n"
        "&& uv run --no-sync vaultspec-core sync"
    )
    parsed = parse_command(command, _inventory())
    assert [p.subcommand for p in parsed] == [("status",), ("sync",)]


def test_for_loop_unrolls_into_three_records_with_distinct_args() -> None:
    """A single-line for loop over three items yields three distinct records."""
    command = (
        "for s in S01 S02 S03; do "
        "uv run --no-sync vaultspec-core vault plan step check PLAN $s; done"
    )
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 3
    assert all(p.subcommand == ("vault", "plan", "step", "check") for p in parsed)
    hashes = {p.command_hash for p in parsed}
    assert len(hashes) == 3


def test_heredoc_body_mention_yields_no_records() -> None:
    """An executable mention inside a heredoc body is masked out entirely."""
    command = (
        "python - <<'PY'\n"
        "import subprocess\n"
        "subprocess.run(['vaultspec-core', 'status'])\n"
        "PY"
    )
    assert candidate_segments(command) == []
    assert parse_command(command, _inventory()) == []


def test_trailing_redirect_and_head_pipe_are_stripped() -> None:
    """A ``2>&1 | head`` tail never becomes a positional argument."""
    command = "uv run --no-sync vaultspec-core vault check all 2>&1 | head -40"
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].subcommand == ("vault", "check", "all")
    assert parsed[0].flags == {}


def test_powershell_select_object_pipe_is_stripped() -> None:
    """A PowerShell ``| Select-Object`` tail is dropped, not parsed as args."""
    command = "uv run --no-sync vaultspec-core vault list | Select-Object -First 60"
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].subcommand == ("vault", "list")
    assert parsed[0].flags == {}


def test_short_feature_flag_canonicalizes_to_long_form() -> None:
    """``-f mytag`` folds to ``--feature`` and populates the feature tag."""
    command = "uv run --no-sync vaultspec-core vault list -f mytag"
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].flags == {"--feature": "mytag"}
    assert parsed[0].feature_tag == "mytag"


def test_boolean_flags_are_captured_as_true() -> None:
    """Presence-only flags map to ``True``, consuming no following token."""
    command = "uv run --no-sync vaultspec-core vault list --json --dry-run"
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].flags == {"--json": True, "--dry-run": True}
    assert parsed[0].feature_tag is None


def test_ansi_and_crlf_input_is_normalized_before_matching() -> None:
    """Colourised, CRLF-terminated input still resolves to one clean record."""
    command = (
        "\x1b[32mcd /work/proj\x1b[0m && "
        "uv run --no-sync vaultspec-core status feat\r\n"
    )
    parsed = parse_command(command, _inventory())
    assert len(parsed) == 1
    assert parsed[0].verb == "status"
    assert parsed[0].subcommand == ("status",)


def test_identical_normalized_commands_hash_identically() -> None:
    """Two spellings that normalize identically share a command hash."""
    short = parse_command(
        "uv run --no-sync vaultspec-core vault list -f mytag", _inventory()
    )
    inline = parse_command(
        "cd /elsewhere && vaultspec-core vault list --feature=mytag", _inventory()
    )
    assert len(short) == 1
    assert len(inline) == 1
    assert short[0].command_hash == inline[0].command_hash


def test_differing_commands_hash_differently() -> None:
    """Distinct feature-tag values produce distinct command hashes."""
    first = parse_command("vaultspec-core vault list --feature alpha", _inventory())
    second = parse_command("vaultspec-core vault list --feature beta", _inventory())
    assert first[0].command_hash != second[0].command_hash


def test_command_without_executable_yields_no_records() -> None:
    """A command that never invokes the executable yields no records."""
    command = 'cd "/work/proj" && git status && echo done'
    assert parse_command(command, _inventory()) == []


def test_bare_executable_mention_as_argument_yields_no_records() -> None:
    """The executable named as another command's argument is not a call."""
    command = "echo vaultspec-core"
    assert parse_command(command, _inventory()) == []


def test_extract_records_threads_context_into_call_records() -> None:
    """extract_records builds CallRecords carrying the supplied context."""
    command = "uv run --no-sync vaultspec-core vault list -f mytag"
    records = extract_records(command, _context(), _inventory())
    assert len(records) == 1
    record = records[0]
    assert record.source == "claude"
    assert record.session_id == "synthetic-session"
    assert record.project == "proj"
    assert record.cwd == "/work/proj"
    assert record.exit_status is ExitStatus.OK
    assert record.verb == "vault"
    assert record.subcommand == ("vault", "list")
    assert record.feature_tag == "mytag"
    assert record.flags == {"--feature": "mytag"}
    assert record.command_hash == parse_command(command, _inventory())[0].command_hash


def test_for_loop_extract_produces_three_call_records() -> None:
    """The for-loop unroll survives all the way into CallRecord construction."""
    command = (
        "for s in S01 S02 S03; do "
        "uv run --no-sync vaultspec-core vault plan step check PLAN $s; done"
    )
    records = extract_records(command, _context(), _inventory())
    assert len(records) == 3
    assert len({r.command_hash for r in records}) == 3
