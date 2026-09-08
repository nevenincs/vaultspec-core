"""The shape of an initialization: phases, steps, results, and the report.

Everything a caller can rely on is declared here once, as data. The phases are
fixed and identical in every repository even where one of them has nothing to
do, because a caller that must probe which recipes a repository happens to
define has no contract at all - it has a lookup table. ``just init-node`` in a
repository with no Node dependency graph reports ``skipped`` with a reason,
which is an answer; a missing recipe is an error message about `just`.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

#: Bumped whenever the report schema, the stamp format, or the meaning of a
#: phase changes. It is part of the stamp digest, so bumping it re-initializes
#: every worktree on the fleet exactly once.
CONTRACT_VERSION: Final = 1

#: The phases, in the order `init` runs them. The order is a dependency order,
#: not a preference: `tools` installs git hooks and enrolls the framework out
#: of the environment `python` creates, and in one repository those hooks lint
#: the SPA that `node` restores.
PHASES: Final[tuple[str, ...]] = ("python", "node", "tools")

#: The environment variable that turns on the NDJSON event stream, so the
#: justfile recipes can stay argument-free and a caller can still ask for
#: machine-readable output.
JSON_ENV: Final = "VAULTSPEC_INIT_JSON"

#: The environment variable that forces a full run, ignoring the stamp.
FORCE_ENV: Final = "VAULTSPEC_INIT_FORCE"

#: Statuses a phase or a run can end in. Deliberately NOT named ``OK``: the
#: exit-code contract already owns that name for the integer 0, and a module
#: importing both would silently mix a status string into an exit code.
DONE: Final = "ok"
SKIPPED: Final = "skipped"
FRESH: Final = "fresh"
FAILED: Final = "failed"
STALE: Final = "stale"


@dataclass(frozen=True)
class Step:
    """One command in a phase.

    Attributes:
        name: The stable identifier a report names this step by. It is the key
            a machine matches on, so it never carries prose.
        argv: The command, already split. Never a shell string: there is no
            shell involved on any platform, which is what makes one
            implementation serve `cmd.exe`, `pwsh` and `sh` alike.
        summary: One line of prose for a human reading the terminal.
        advisory: When true, a non-zero status is reported and does not fail
            the phase. Reserved for diagnosis that is worth printing and is
            not a precondition for a usable worktree.
        timeout: Seconds before the step is abandoned, or ``None``.
    """

    name: str
    argv: tuple[str, ...]
    summary: str
    advisory: bool = False
    timeout: float | None = 1800.0


@dataclass(frozen=True)
class Phase:
    """One phase of an initialization.

    Attributes:
        name: One of :data:`PHASES`.
        summary: One line of prose describing what the phase provisions.
        steps: The commands, in order. An empty tuple means this repository has
            nothing to do in this phase, which is reported as ``skipped``.
        inputs: Repository-relative paths whose content decides whether the
            phase is current. A change to any of them makes the phase stale.
        artifacts: Repository-relative paths that must exist for the phase to
            count as done. This is what stops a stamp from vouching for an
            environment somebody has since deleted.
        skip_reason: Why this repository has no work here. Required when
            ``steps`` is empty, so a ``skipped`` result always explains itself.
    """

    name: str
    summary: str
    steps: tuple[Step, ...] = ()
    inputs: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    skip_reason: str | None = None


@dataclass
class StepResult:
    """What one step did.

    Attributes:
        name: The step's identifier.
        argv: The command as executed.
        status: :data:`OK`, :data:`FAILED`, or :data:`SKIPPED`.
        exit_code: The process's status, or ``None`` when it never ran.
        duration_ms: Wall-clock milliseconds.
        output_tail: The last lines the process wrote, which is the part a
            reader needs and the part a report can afford to carry.
        advisory: Whether a non-zero status was tolerated.
    """

    name: str
    argv: tuple[str, ...]
    status: str
    exit_code: int | None = None
    duration_ms: int = 0
    output_tail: str = ""
    advisory: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return the JSON form of this result."""
        return {
            "name": self.name,
            "argv": list(self.argv),
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "advisory": self.advisory,
            "output_tail": self.output_tail,
        }


@dataclass
class PhaseResult:
    """What one phase did.

    Attributes:
        name: One of :data:`PHASES`.
        status: :data:`OK`, :data:`FRESH`, :data:`SKIPPED`, :data:`FAILED`, or
            :data:`STALE` (the last only under ``init-check``).
        reason: Why, in one line, for any status that is not :data:`OK`.
        steps: The step results, in execution order.
        exit_code: The contract code this phase would exit with.
    """

    name: str
    status: str
    reason: str = ""
    steps: list[StepResult] = field(default_factory=list)
    exit_code: int = 0

    def as_dict(self) -> dict[str, object]:
        """Return the JSON form of this result."""
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "steps": [step.as_dict() for step in self.steps],
        }


class Emitter:
    """The run's two output channels.

    Human prose goes to stderr and machine events go to stdout, so a caller can
    consume the event stream without stripping decoration out of it and a human
    watching the terminal loses nothing when a machine is also listening. The
    separation is the reason ``--json`` does not need a quiet mode.
    """

    def __init__(self, *, json_mode: bool) -> None:
        """Initialize the emitter.

        Args:
            json_mode: Whether to write NDJSON events to stdout.
        """
        self._json = json_mode
        self._started = time.monotonic()

    @property
    def json_mode(self) -> bool:
        """Whether machine-readable events are being written."""
        return self._json

    def say(self, message: str) -> None:
        """Write one line of human prose.

        Args:
            message: The line, without a trailing newline.
        """
        print(message, file=sys.stderr, flush=True)

    def event(self, kind: str, **fields: object) -> None:
        """Write one machine-readable event.

        Args:
            kind: The event type.
            **fields: The event's payload.
        """
        if not self._json:
            return
        payload: dict[str, object] = {
            "event": kind,
            "elapsed_ms": int((time.monotonic() - self._started) * 1000),
        }
        payload.update(fields)
        print(json.dumps(payload, sort_keys=True), flush=True)


@dataclass(frozen=True)
class Outcome:
    """How a run ended.

    Attributes:
        status: The run's overall status.
        exit_code: The status the process will exit with. It travels WITH the
            status rather than beside it because the two are one fact: a report
            claiming success under a non-zero code, or the reverse, is the kind
            of disagreement a caller cannot recover from.
    """

    status: str
    exit_code: int


def build_report(
    *,
    repo_root: Path,
    selection: Sequence[str],
    phases: Iterable[PhaseResult],
    outcome: Outcome,
    remediation: Sequence[str],
) -> dict[str, object]:
    """Assemble the run report.

    Args:
        repo_root: The worktree this run initialized.
        selection: The phases that were asked for.
        phases: The results, in execution order.
        outcome: How the run ended.
        remediation: Actionable lines a human or a provisioner should surface.

    Returns:
        The report, ready to serialize.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "repo": repo_root.name,
        "repo_path": str(repo_root),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "selection": list(selection),
        "status": outcome.status,
        "exit_code": outcome.exit_code,
        "phases": [phase.as_dict() for phase in phases],
        "remediation": list(remediation),
    }
