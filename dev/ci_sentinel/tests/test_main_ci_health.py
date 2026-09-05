"""Guards for the main-branch CI sentinel's judgement.

Every case below is a state ``main`` has actually been in or can reach. The one
that matters most is the empty run list: a run that was never created leaves no
record, so it is the only fault shape that cannot be found by inspecting runs,
and the only one a naive "look at the latest run" check misses entirely.

The run payloads are shaped as the GitHub API returns them - ``status`` plus
``conclusion``, the two-field encoding where ``conclusion`` is meaningless
until ``status`` is ``completed``.
"""

from __future__ import annotations

from typing import Any

import pytest

from dev.ci_sentinel.main_ci_health import (
    DEFAULT_GRACE_MINUTES,
    State,
    Verdict,
    classify,
    render,
)

pytestmark = pytest.mark.unit


def run(status: str, conclusion: str | None = None) -> dict[str, Any]:
    """One workflow run in the shape the API returns it."""
    return {"status": status, "conclusion": conclusion}


COMPLETED_SUCCESS = run("completed", "success")
COMPLETED_FAILURE = run("completed", "failure")
STARTUP_FAILURE = run("completed", "startup_failure")
CANCELLED = run("completed", "cancelled")


def test_a_successful_run_is_healthy() -> None:
    """The ordinary case: something ran and passed."""
    assert classify([COMPLETED_SUCCESS], commit_age_minutes=10).state == "healthy"


def test_a_startup_failure_is_unhealthy() -> None:
    """The incident this sentinel exists for: zero jobs, zero logs, no verdict.

    A run in this state is present in the API and looks like a run, so anything
    that only checks "does a run exist" reports main as fine.
    """
    verdict = classify([STARTUP_FAILURE], commit_age_minutes=200)

    assert verdict.state == "unhealthy"
    assert "startup_failure" in verdict.reason


def test_a_cancelled_run_is_unhealthy() -> None:
    """A cancelled run validated nothing, and reports as cancelled, not failed."""
    assert classify([CANCELLED], commit_age_minutes=200).state == "unhealthy"


def test_a_failed_run_is_unhealthy() -> None:
    """An ordinary red run leaves main unvalidated just as thoroughly."""
    assert classify([COMPLETED_FAILURE], commit_age_minutes=200).state == "unhealthy"


def test_no_run_at_all_past_the_grace_window_is_unhealthy() -> None:
    """The shape with no record to inspect - found by the commit's age alone.

    This is the case the issue calls out as the reason to assert the invariant
    rather than watch the runs: there is nothing to watch.
    """
    verdict = classify([], commit_age_minutes=DEFAULT_GRACE_MINUTES + 1)

    assert verdict.state == "unhealthy"
    # Distinguishes this branch from the other unhealthy one, whose message
    # says CI "did not succeed" - a run existed there and none does here.
    assert "ever created" in verdict.reason


def test_no_run_yet_inside_the_grace_window_is_pending() -> None:
    """A commit pushed seconds ago has no run, and that is not a fault.

    Without this the sentinel fires on every push and gets muted, which would
    leave main less protected than before it existed.
    """
    assert classify([], commit_age_minutes=1).state == "pending"


def test_a_run_still_in_flight_is_pending_however_old_the_commit_is() -> None:
    """A long lane mid-run is not a fault, even past the grace window.

    The slowest lane here takes ~30 minutes and a queued self-hosted job can
    wait far longer, so age alone must not condemn a run that is still going.
    """
    for status in ("queued", "in_progress", "waiting", "requested", "pending"):
        verdict = classify([run(status)], commit_age_minutes=10_000)
        assert verdict.state == "pending", status


def test_one_success_outweighs_other_failed_runs() -> None:
    """A re-run that passes validates the commit; the earlier red does not undo it."""
    assert (
        classify([STARTUP_FAILURE, COMPLETED_SUCCESS], commit_age_minutes=200).state
        == "healthy"
    )


def test_every_failing_conclusion_is_named_in_the_reason() -> None:
    """The message is what a human acts on, so it must say which shape occurred."""
    verdict = classify([STARTUP_FAILURE, CANCELLED], commit_age_minutes=200)

    assert "startup_failure" in verdict.reason
    assert "cancelled" in verdict.reason


@pytest.mark.parametrize(
    ("state", "expected"),
    [("healthy", 0), ("pending", 0), ("unhealthy", 1)],
)
def test_only_an_unhealthy_verdict_exits_non_zero(state: State, expected: int) -> None:
    """Pending must not fail the job, or every push turns the sentinel red."""
    assert Verdict(state, "").exit_code == expected


def test_the_grace_window_exceeds_the_slowest_ci_lane() -> None:
    """A grace shorter than a normal run makes the sentinel fire during one.

    The `broad (windows-latest)` lane has taken up to ~30 minutes on main, and
    self-hosted jobs queue behind each other on a single runner, so the window
    has to clear both comfortably.
    """
    assert DEFAULT_GRACE_MINUTES >= 60


def test_the_key_value_format_carries_the_state_a_caller_must_branch_on() -> None:
    """The exit code cannot answer "is main green?", so the state has to.

    ``exit_code`` is 0 for ``healthy`` and ``pending`` alike - correctly, as
    neither should fail the sentinel job - which leaves a caller that reads
    only the exit code unable to tell a validated main from one whose verdict
    has not arrived. The sentinel workflow closes its issue on exactly that
    distinction, and got it wrong until it started reading this field: issue
    #398 was closed as "validated again" on a ``pending`` verdict, with main's
    tip red and its CI run still in flight.
    """
    rendered = render(Verdict("pending", "1 CI run(s) still in flight"), "key-value")

    assert rendered.splitlines() == [
        "state=pending",
        "reason=1 CI run(s) still in flight",
    ]


@pytest.mark.parametrize("state", ["healthy", "pending", "unhealthy"])
def test_every_state_survives_the_round_trip_a_caller_parses(state: State) -> None:
    """Each state must appear verbatim, since callers compare it literally."""
    rendered = render(Verdict(state, "some reason"), "key-value")

    assert f"state={state}" in rendered.splitlines()


def test_a_multi_line_reason_cannot_forge_a_second_key() -> None:
    """The consumer appends this to ``$GITHUB_OUTPUT``, one key per line.

    A newline inside a value would end the ``reason`` there and let the rest
    be read as another key - including a second ``state`` that overrides the
    real verdict. Reasons are built from this module's own literals today, so
    this guards the format rather than a live input.
    """
    rendered = render(Verdict("unhealthy", "first\nstate=healthy"), "key-value")

    assert len(rendered.splitlines()) == 2
    assert rendered.splitlines()[1] == "reason=first state=healthy"


def test_the_text_format_stays_one_human_sentence() -> None:
    """The step summary and the issue body both read this shape."""
    assert render(Verdict("healthy", "CI succeeded for main's tip")) == (
        "healthy: CI succeeded for main's tip"
    )
