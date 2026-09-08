"""Idempotence: why a second `just init` costs nothing.

`init` has to be cheap enough that a git hook, a provisioner and a habit can
all call it unconditionally. It cannot get there by making each step fast -
``uv sync --locked`` against an already-synced environment still resolves, and
``npm ci`` deletes ``node_modules`` before it does anything else. It gets there
by not running the steps at all when nothing that feeds them has changed.

What decides that is a digest over the phase's declared inputs - the lockfiles,
the version pins, the manifests - plus this package's own source, so a change
to what `init` DOES invalidates every stamp that was written by the old
behaviour. The digest is per phase, so editing ``uv.lock`` re-runs
``init-python`` and still skips ``init-node``.

A stamp alone is not sufficient and is not trusted alone. It records what the
inputs were, not whether the result still exists, so each phase also declares
the artifacts that must be present. A deleted ``.venv`` with a matching stamp
is stale, which is the case that would otherwise make `init` confidently do
nothing to a broken worktree.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from dev.init.contract import CONTRACT_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dev.init.contract import Phase

#: Where the stamp lives. Inside the virtual environment on purpose: `.venv` is
#: already ignored in every repository, it is per-worktree, and destroying the
#: environment destroys the claim that it was provisioned - which is exactly
#: the coupling wanted.
STAMP_NAME: Final = ".init-stamp.json"

#: The report's name, written beside the stamp.
REPORT_NAME: Final = "init-report.json"


def stamp_path(repo_root: Path) -> Path:
    """Return the stamp file's path.

    Args:
        repo_root: The worktree root.

    Returns:
        The path, which may not exist yet.
    """
    return repo_root / ".venv" / STAMP_NAME


def report_path(repo_root: Path) -> Path:
    """Return where this run's report should be written.

    ``.venv`` is the home for it, and a run that failed before creating the
    environment has nowhere there to write. Rather than pollute the tracked
    tree with a report file that would then need ignoring, that case falls back
    to the repository root's ``.init-report.json``, whose path the run always
    prints so a caller never has to guess which one it got.

    Args:
        repo_root: The worktree root.

    Returns:
        The report path.
    """
    venv = repo_root / ".venv"
    if venv.is_dir():
        return venv / REPORT_NAME
    return repo_root / f".{REPORT_NAME}"


def _digest_file(path: Path) -> str:
    """Return a content digest for one file, or a marker for its absence.

    Args:
        path: The file to digest.

    Returns:
        A hex digest, or ``"absent"``. Absence is a state worth recording: a
        lockfile that appears must invalidate the stamp exactly as a changed
        one does.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "absent"


def _own_source_digest() -> str:
    """Return a digest over this package's own source.

    Returns:
        A hex digest over every ``.py`` file in :mod:`dev.init`, so a change to
        what a phase does invalidates the stamps written by the old behaviour.
        Without this, editing ``plan.py`` would leave every already-initialized
        worktree on the fleet silently running the previous plan.
    """
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for source in sorted(here.glob("*.py")):
        digest.update(source.name.encode("utf-8"))
        digest.update(_digest_file(source).encode("ascii"))
    return digest.hexdigest()


def phase_digest(repo_root: Path, phase: Phase) -> str:
    """Return the digest deciding whether one phase is current.

    Args:
        repo_root: The worktree root.
        phase: The phase to digest.

    Returns:
        A hex digest over the contract version, this package's source, the
        interpreter's major.minor, and the content of every declared input.
    """
    digest = hashlib.sha256()
    digest.update(f"v{CONTRACT_VERSION}".encode("ascii"))
    digest.update(_own_source_digest().encode("ascii"))
    digest.update(f"{sys.version_info.major}.{sys.version_info.minor}".encode("ascii"))
    digest.update(phase.name.encode("utf-8"))
    for relative in sorted(phase.inputs):
        digest.update(relative.encode("utf-8"))
        digest.update(_digest_file(repo_root / relative).encode("ascii"))
    return digest.hexdigest()


def missing_artifacts(repo_root: Path, phase: Phase) -> list[str]:
    """Return the phase's declared artifacts that are not present.

    Args:
        repo_root: The worktree root.
        phase: The phase to check.

    Returns:
        The relative paths that are missing, in declaration order.
    """
    return [path for path in phase.artifacts if not (repo_root / path).exists()]


def read(repo_root: Path) -> dict[str, str]:
    """Return the recorded per-phase digests.

    Args:
        repo_root: The worktree root.

    Returns:
        A mapping of phase name to digest. An unreadable, malformed, or
        wrong-version stamp reads as empty, which makes every phase stale -
        the safe direction, since the cost of being wrong is one extra run.
    """
    path = stamp_path(repo_root)
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    payload = cast("dict[str, object]", decoded)
    if payload.get("contract_version") != CONTRACT_VERSION:
        return {}
    phases = payload.get("phases")
    if not isinstance(phases, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in cast("dict[object, object]", phases).items()
    }


def write(repo_root: Path, digests: dict[str, str]) -> None:
    """Record the per-phase digests.

    Args:
        repo_root: The worktree root.
        digests: The mapping of phase name to digest to record.
    """
    path = stamp_path(repo_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "contract_version": CONTRACT_VERSION,
                    "phases": dict(sorted(digests.items())),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        # A stamp that cannot be written costs a full re-run next time and
        # nothing else. It must never fail an initialization that succeeded.
        return


def is_current(repo_root: Path, phase: Phase, recorded: dict[str, str]) -> bool:
    """Return whether a phase can be skipped.

    Args:
        repo_root: The worktree root.
        phase: The phase in question.
        recorded: The digests read from the stamp.

    Returns:
        True when the recorded digest matches the phase's inputs AND every
        declared artifact is present. Both conditions are load bearing: the
        first catches changed inputs, the second catches a destroyed result.
    """
    if recorded.get(phase.name) != phase_digest(repo_root, phase):
        return False
    return not missing_artifacts(repo_root, phase)


def staleness(repo_root: Path, phases: Iterable[Phase]) -> list[tuple[str, str]]:
    """Return the reason each stale phase is stale.

    Args:
        repo_root: The worktree root.
        phases: The phases to examine.

    Returns:
        One ``(phase name, reason)`` pair per stale phase. A phase with no
        steps is never stale: there is nothing it could fail to have done.
    """
    recorded = read(repo_root)
    reasons: list[tuple[str, str]] = []
    for phase in phases:
        if not phase.steps:
            continue
        missing = missing_artifacts(repo_root, phase)
        if missing:
            reasons.append((phase.name, f"missing: {', '.join(missing)}"))
        elif recorded.get(phase.name) != phase_digest(repo_root, phase):
            unstamped = phase.name not in recorded
            why = "no stamp" if unstamped else "inputs changed since the last run"
            reasons.append((phase.name, why))
    return reasons
