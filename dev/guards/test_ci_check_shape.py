"""Contracts on the two-job pull-request check set.

The self-hosted fleet has one Linux runner and one Windows runner. The CI
workflow therefore has exactly one complete Linux validation job and one
independent Windows broad-suite job. This guard pins that topology, every
recipe in the old Linux lanes, and the failure semantics that keep independent
diagnostics visible after an earlier gate fails.

The recipe checks intentionally complement the older duplicate-work checks:
``test-broad`` is expected once per operating system, while every other Linux
validation recipe occurs once in the Linux job only.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from dev.runner import Cmd, Ref
from dev.toolchain import find_verb

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]

#: The pull-request workflow. The scheme and the no-repeat rule are about the
#: check set a merge waits on, which is this file and no other.
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: Every workflow. The self-hosted timeout rule is about the FLEET, not about
#: one workflow: a job that hangs holds a machine the whole estate shares.
WORKFLOWS = ROOT / ".github" / "workflows"

LINUX_JOB = "full-suite-linux"
WINDOWS_JOB = "library-windows"
EXPECTED_JOBS = frozenset({LINUX_JOB, WINDOWS_JOB})
EXPECTED_CHECK_NAMES = frozenset({"Full Suite (Linux)", "Library (Windows)"})

# The five former Linux executions contributed these gating recipes. Comparing
# counters makes an accidental omission or extra invocation fail while leaving
# harmless step reordering possible.
LINUX_RECIPES = (
    "init",
    "deps-check",
    "check-workflow",
    "check-python",
    "check-type-platforms",
    "check-toml",
    "check-links",
    "check-markdown",
    "check-complexity",
    "check-nesting",
    "check-size",
    "check-type-strict",
    "test-harness",
    "test-repo",
    "test-broad",
    "framework-install",
    "vault-check",
    "audit-deps",
)
WINDOWS_RECIPES = ("init", "test-broad")

#: How a recipe prefix is spelled in the registry. The gating verb is ``lint``
#: in the table and ``check`` at the recipe, because a contributor reaches for
#: "check the types". Every other prefix spells the same on both sides.
RECIPE_VERB = {"check": "lint"}

#: Recipes that PROVISION rather than check. Every job needs the environment,
#: so these are expected in all of them and are not repeated work in the sense
#: this file polices - re-running them is how a second machine gets a venv.
PROVISIONING = frozenset({"just init", "just framework-install"})


def _ci() -> dict[str, Any]:
    """Parse the pull-request workflow."""
    return cast("dict[str, Any]", yaml.safe_load(CI.read_text(encoding="utf-8")))


def _jobs() -> dict[str, dict[str, Any]]:
    """Return the CI jobs with a useful type for topology assertions."""
    return cast("dict[str, dict[str, Any]]", _ci().get("jobs") or {})


def _events(document: dict[str, Any]) -> dict[str, Any]:
    """Read workflow triggers under both YAML 1.1 and YAML 1.2 parsers."""
    mapping = cast("dict[object, object]", document)
    raw = mapping.get("on")
    if raw is None:
        # PyYAML's YAML 1.1 loader parses the GitHub key ``on`` as ``True``.
        raw = mapping.get(True, {})
    return cast("dict[str, Any]", raw or {})


def _just_recipes(job: dict[str, Any]) -> list[str]:
    """List the simple ``just <recipe>`` commands in one job."""
    recipes: list[str] = []
    for step in job.get("steps", []):
        command = step.get("run")
        if not isinstance(command, str) or not command.strip().startswith("just "):
            continue
        recipes.append(command.strip().removeprefix("just ").split()[0])
    return recipes


def _uses(job: dict[str, Any], action: str) -> list[dict[str, Any]]:
    """Return steps whose ``uses`` value starts with ``action``."""
    return [
        step
        for step in job.get("steps", [])
        if isinstance(step.get("uses"), str) and step["uses"].startswith(action)
    ]


def test_ci_has_exactly_two_independent_jobs() -> None:
    """The PR check set has only the fixed Linux and Windows jobs."""
    document = _ci()
    jobs = _jobs()

    assert set(jobs) == EXPECTED_JOBS, (
        "ci.yml must contain exactly the Linux full suite and the independent "
        f"Windows library job; found {sorted(jobs)}"
    )
    assert {job.get("name") for job in jobs.values()} == EXPECTED_CHECK_NAMES
    assert jobs[LINUX_JOB]["name"] == "Full Suite (Linux)"
    assert jobs[WINDOWS_JOB]["name"] == "Library (Windows)"

    # A matrix or a needs edge would make the status set dynamic or allow one
    # platform to disappear behind the other. Neither is part of this shape.
    for job_id, job in jobs.items():
        assert "strategy" not in job, f"`{job_id}` must not be a matrix job"
        assert "needs" not in job, f"`{job_id}` must not depend on another CI job"
        assert "if" not in job, f"`{job_id}` must not be conditionally skipped"

    assert not set(jobs) & {
        "lint",
        "test-harness-repo",
        "test-library",
        "test-vault",
        "audit-dependencies",
    }, "obsolete jobs must be deleted, not left as skipped placeholders"

    events = _events(document)
    assert "pull_request" in events, "ci.yml must retain its pull-request trigger"
    assert "release" not in events, "ci.yml must not have a release-only trigger"
    assert "workflow_call" not in events, "ci.yml must not retain audit-only jobs"
    for job_id, job in jobs.items():
        for step in job.get("steps", []):
            condition = str(step.get("if", ""))
            assert "workflow_call" not in condition, (
                f"`{job_id}` contains a workflow_call-only step"
            )
            assert "release" not in condition.lower(), (
                f"`{job_id}` contains a release-only step"
            )
            command = str(step.get("run", "")).lower()
            assert "inactive" not in command and "placeholder" not in command, (
                f"`{job_id}` contains a skipped/placeholder command"
            )


def test_ci_keeps_each_recipe_and_single_provisioning_cycle() -> None:
    """Linux keeps each former validation once; Windows keeps broad once."""
    jobs = _jobs()
    assert Counter(_just_recipes(jobs[LINUX_JOB])) == Counter(LINUX_RECIPES)
    assert Counter(_just_recipes(jobs[WINDOWS_JOB])) == Counter(WINDOWS_RECIPES)

    for job_id in EXPECTED_JOBS:
        job = jobs[job_id]
        assert len(_uses(job, "actions/checkout@")) == 1
        assert len(_uses(job, "actions/setup-python@")) == 1
        uv_steps = _uses(job, "astral-sh/setup-uv@")
        assert len(uv_steps) == 1
        assert uv_steps[0].get("with", {}).get("enable-cache") == (
            "${{ inputs.cache_mode != 'cold' }}"
        )
        cold_steps = [
            step
            for step in job.get("steps", [])
            if step.get("name") == "Isolate the cold uv cache"
        ]
        assert len(cold_steps) == 1
        assert cold_steps[0].get("if") == "inputs.cache_mode == 'cold'"
        assert "UV_CACHE_DIR=${RUNNER_TEMP}" in cold_steps[0].get("run", "")
        assert len(_uses(job, "taiki-e/install-action@")) == (
            3 if job_id == LINUX_JOB else 1
        )
        assert not any("matrix." in str(step) for step in job.get("steps", [])), (
            f"`{job_id}` must not use matrix expressions"
        )

    linux = jobs[LINUX_JOB]
    assert len(_uses(linux, "taiki-e/install-action@")) == 3
    assert any(step.get("with", {}).get("tool") == "lychee" for step in linux["steps"])
    assert any(
        step.get("with", {}).get("tool") == "taplo-cli" for step in linux["steps"]
    )


def test_linux_gates_run_after_failures_without_erasing_failure() -> None:
    """Independent Linux gates always run and no step is allowed to mask red."""
    jobs = _jobs()
    for step in jobs[LINUX_JOB]["steps"]:
        command = step.get("run", "")
        if not isinstance(command, str) or not command.strip().startswith("just "):
            continue
        recipe = command.strip().removeprefix("just ").split()[0]
        if recipe == "init":
            continue
        assert step.get("if") == "always()", (
            f"Linux gate `{recipe}` must run after earlier validation failures"
        )
        assert not step.get("continue-on-error", False), (
            f"Linux gate `{recipe}` must preserve the final failure state"
        )

    for job in jobs.values():
        assert not any(
            step.get("continue-on-error", False) for step in job.get("steps", [])
        ), "CI gates must not turn a failed command into a passing job"


def _check_names(job: dict[str, Any], job_id: str) -> list[str]:
    """Every status-check name one job definition produces.

    A matrix job produces one check per leg, so the matrix is expanded here:
    the names a merge waits on are the expanded ones, and an unexpanded
    ``${{ matrix.name }}`` would sail through the pattern on the literal.
    """
    name = job.get("name", job_id)
    include = _matrix_include(job)
    if "${{ matrix.name }}" not in name:
        return [name]
    assert include, (
        f"job `{job_id}` interpolates `matrix.name` into its check name but "
        "declares no `include:` entries to expand it from"
    )
    return [name.replace("${{ matrix.name }}", entry["name"]) for entry in include]


def _leaf_commands(recipe: str) -> set[tuple[str, ...]]:
    """Expand ``just <recipe>`` to the argv of every command it finally runs.

    Comparing recipe NAMES would miss every duplicate this repository has
    actually shipped, because each was spelled differently from the thing it
    duplicated. Comparing what the registry ultimately executes catches an
    aggregate that composes a leaf another job names directly - which is
    exactly how the dependency audit came to run twice.
    """
    prefix, _, target_name = recipe.partition("-")
    verb = find_verb(RECIPE_VERB.get(prefix, prefix))
    if verb is None or not target_name:
        return set()
    target = verb.find(target_name)
    if target is None:
        return set()
    leaves: set[tuple[str, ...]] = set()
    pending = [target]
    seen = {target.name}
    while pending:
        for step in pending.pop().steps:
            if isinstance(step, Ref):
                if step.target in seen:
                    continue
                seen.add(step.target)
                referenced = verb.find(step.target)
                if referenced is not None:
                    pending.append(referenced)
            elif isinstance(step, Cmd):
                leaves.add(tuple(step.argv))
    return leaves


def test_every_check_name_follows_the_scheme() -> None:
    """The two required status checks have stable, exact names."""
    jobs = _jobs()
    names = [name for job_id, job in jobs.items() for name in _check_names(job, job_id)]
    assert set(names) == EXPECTED_CHECK_NAMES
    assert len(names) == len(EXPECTED_CHECK_NAMES)


def test_no_check_name_is_spelled_by_the_tool_that_implements_it() -> None:
    """The subject says what is covered, not what covers it.

    ``Dependency Audit (uv audit)`` was accurate on the day it was written and
    stops being so the day the tool is replaced, at which point the merge box
    names something that no longer runs.
    """
    tools = ("uv", "ruff", "pytest", "ty", "pylint", "mypy", "actionlint", "just")
    jobs = _ci()["jobs"]
    for job_id, job in jobs.items():
        for name in _check_names(job, job_id):
            words = {word.strip("():,&").lower() for word in name.split()}
            named = sorted(words & set(tools))
            assert not named, (
                f"check name {name!r} (job `{job_id}`) names the tool "
                f"{named}. Name the subject it covers instead - the tool is an "
                "implementation detail that a reader cannot act on and a "
                "replacement makes a lie."
            )


def test_no_job_repeats_work_another_job_already_does() -> None:
    """No two jobs in the pull-request path run the same underlying command.

    Expanded to leaf commands, so an aggregate composing a leaf that another
    job names directly fails here just as a literal repeat would.
    """
    jobs = _ci()["jobs"]
    by_job: dict[str, set[tuple[str, ...]]] = {}
    for job_id, job in jobs.items():
        commands: set[tuple[str, ...]] = set()
        for step in job.get("steps", []):
            run = step.get("run", "").strip()
            if not run.startswith("just ") or run in PROVISIONING:
                continue
            commands |= _leaf_commands(run.removeprefix("just ").split()[0])
        by_job[job_id] = commands

    assert any(by_job.values()), (
        "no job resolved to a single leaf command; the recipe-to-registry "
        "resolution broke and this comparison would pass vacuously"
    )

    overlaps: list[str] = []
    for first, second in ((a, b) for a in by_job for b in by_job if a < b):
        shared = by_job[first] & by_job[second]
        # The broad library suite is deliberately run once on each operating
        # system. It is the only expected cross-job overlap; every other
        # overlap remains a duplicate-work regression.
        if {first, second} == {LINUX_JOB, WINDOWS_JOB}:
            shared -= _leaf_commands("test-broad")
        for argv in sorted(shared):
            overlaps.append(f"`{first}` and `{second}` both run: {' '.join(argv)}")
    assert not overlaps, (
        "these commands run in more than one job of the pull-request path. On "
        "a fleet with one runner per platform every job is serial, so a repeat "
        "is pure latency:\n  " + "\n  ".join(overlaps)
    )


#: A recipe in the pull-request path, and the recipe whose coverage makes it
#: redundant there. Each pair is a SUBSET relationship the leaf-command
#: comparison cannot see, because the commands genuinely differ:
#:
#: - ``test-unit`` is ``test-broad``'s selection with ``unit and`` prepended,
#:   over the same path, and ``test-broad`` runs on both operating systems.
#: - ``test-vault-repair`` is two ``unit``-marked files under that same path,
#:   so the Windows leg of ``test-broad`` has always collected them.
#: - ``check-type`` runs ``ty`` against the HOST platform, and every runner in
#:   this workflow that could run it is Linux - which is the first of
#:   ``check-type-platforms``' three passes.
#:
#: Each recipe stays in the registry; a maintainer runs the narrow one locally
#: because it is the fast one. What is asserted is only that the pull-request
#: path names the covering recipe and not the covered one.
SUBSUMED = {
    "test-unit": "test-broad",
    "test-vault-repair": "test-broad",
    "check-type": "check-type-platforms",
}


def test_no_job_names_a_recipe_that_another_named_recipe_subsumes() -> None:
    """A lane whose population another lane already covers is not run again."""
    named = {
        step["run"].strip().removeprefix("just ")
        for job in _ci()["jobs"].values()
        for step in job.get("steps", [])
        if "run" in step and step["run"].strip().startswith("just ")
    }
    for narrow, wide in SUBSUMED.items():
        # The covering recipe must actually be here. Without this the pair
        # passes just as well when NEITHER runs, which turns a rule about
        # duplication into a way to delete coverage.
        assert wide in named, (
            f"`{wide}` is not in the pull-request path, so dropping "
            f"`{narrow}` on the grounds that `{wide}` covers it no longer "
            "holds. Restore one of them."
        )
        assert narrow not in named, (
            f"the pull-request path names both `{narrow}` and `{wide}`, and "
            f"`{wide}` already covers everything `{narrow}` selects. On a "
            "fleet with one runner per platform that is the same work twice, "
            "serially, on the same machine."
        )


def _workflow_paths() -> list[Path]:
    """Every workflow file, proven to exist before anything reads them.

    Globbed in a helper rather than in the test, and asserted non-empty here:
    ``Path.glob`` treats "missing" and "empty" alike and raises for neither, so
    a renamed directory would otherwise retire the guard below by giving it
    nothing to find.
    """
    paths = sorted(WORKFLOWS.glob("*.yml"))
    assert paths, f"no workflow files found under {WORKFLOWS}"
    return paths


def _matrix_include(job: dict[str, Any]) -> list[dict[str, Any]]:
    """The job's matrix ``include:`` entries, or none when it declares no matrix."""
    strategy = cast("dict[str, Any]", job.get("strategy") or {})
    matrix = cast("dict[str, Any]", strategy.get("matrix") or {})
    return cast("list[dict[str, Any]]", matrix.get("include") or [])


def _runner_labels(job: dict[str, Any]) -> list[str]:
    """Every runner label a job can land on, matrix selectors resolved.

    ``runs-on`` is not always a label list. A matrix job names an expression -
    ``${{ matrix.runner }}`` - and keeps the labels in its ``include:`` entries,
    so reading ``runs-on`` alone reports no labels at all for exactly the job
    that occupies a fleet runner longest. This resolves the expression back to
    the matrix values it selects from.
    """
    runs_on: object = job.get("runs-on")
    if isinstance(runs_on, list):
        return [str(label) for label in cast("list[object]", runs_on)]
    if not isinstance(runs_on, str):
        return []
    if "${{" not in runs_on:
        return [runs_on]
    key = runs_on.split("matrix.", 1)[-1].split("}}", 1)[0].strip()
    labels: list[str] = []
    for entry in _matrix_include(job):
        value: object = entry.get(key)
        if isinstance(value, list):
            labels += [str(label) for label in cast("list[object]", value)]
        elif value is not None:
            labels.append(str(value))
    return labels


def test_every_self_hosted_job_declares_a_timeout() -> None:
    """A job on the self-hosted fleet must bound how long it can hold a runner.

    GitHub's default is six hours. On hosted runners that is someone else's
    capacity; here it is one of two machines the entire estate queues behind,
    so an unbounded job that hangs stops every other workflow for the rest of
    the day.

    Scoped to self-hosted jobs on purpose: a hosted runner has its own ceiling
    and costs no local capacity, so requiring a budget there would be noise.
    """
    checked: list[str] = []
    missing: list[str] = []
    for path in _workflow_paths():
        document = cast(
            "dict[str, dict[str, dict[str, Any]]]",
            yaml.safe_load(path.read_text(encoding="utf-8")),
        )
        for job_id, job in (document.get("jobs") or {}).items():
            if "self-hosted" not in _runner_labels(job):
                continue
            checked.append(f"{path.name}:{job_id}")
            if job.get("timeout-minutes") is None:
                missing.append(f"{path.name}:{job_id}")
    # A resolver that silently stopped recognising self-hosted jobs would pass
    # this every run while asserting nothing, which is the failure mode the
    # matrix expression already produced once.
    assert checked, (
        "no self-hosted jobs were found in any workflow; the `runs-on` "
        "resolution broke and this assertion would pass vacuously"
    )
    assert not missing, (
        "these self-hosted jobs declare no `timeout-minutes`, so each can hold "
        "a fleet runner for GitHub's six-hour default: " + ", ".join(missing)
    )


def test_a_main_run_can_never_supersede_another_main_run() -> None:
    """Every commit on the default branch gets its own concurrency group.

    `cancel-in-progress: false` is necessary and not sufficient. It governs a
    run that has STARTED; GitHub's other concurrency rule has no switch, and
    cancels any previously PENDING run when a new one enters the same group.
    On a fleet of one runner per platform a main run routinely waits without
    starting, so it is pending, so the next push to main kills it - which is
    how the merge of the check-set rework ended `cancelled` with no job ever
    assigned, forty-four minutes after it was created.

    Putting the SHA in the group on main is what makes two main commits
    incapable of sharing a group. Both halves are asserted: the SHA must be
    there, and cancellation must still be off, because either one alone leaves
    a way for a main commit to end with no verdict.
    """
    document = cast("dict[str, Any]", yaml.safe_load(CI.read_text(encoding="utf-8")))
    concurrency = cast("dict[str, str]", document.get("concurrency") or {})
    group = concurrency.get("group", "")
    cancel = str(concurrency.get("cancel-in-progress", ""))

    assert "github.sha" in group, (
        "the concurrency group does not vary by SHA, so every push to the "
        f"default branch shares one group: {group!r}. A main run that is still "
        "pending when the next push lands is cancelled outright, and a "
        "cancelled run is not red - nothing downstream reacts to it."
    )
    assert "refs/heads/main" in group, (
        "the SHA must be added only on the default branch: a per-SHA group on "
        "every ref would stop branch pushes superseding their own obsolete "
        f"runs, which is the behaviour worth keeping. Group: {group!r}"
    )
    assert "refs/heads/main" in cancel and cancel.startswith("${{"), (
        "cancellation must stay disabled on the default branch; a per-SHA "
        f"group does not by itself stop an in-flight run being cancelled: {cancel!r}"
    )
    assert "github.ref != 'refs/heads/main'" in cancel, (
        "non-main runs must cancel in-progress superseded work while main runs "
        f"remain uncancelled: {cancel!r}"
    )
    assert "format('-{0}', github.sha)" in group, (
        "main's concurrency group must append the commit SHA, rather than only "
        f"mentioning it in an unrelated expression: {group!r}"
    )
