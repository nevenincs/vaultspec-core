"""Contracts on the pull-request merge gate and the names every workflow shows.

The self-hosted fleet has one Linux runner and one Windows runner, so the pull
request path is tiered. ``Check: Lint (Linux)`` runs on every push; the two
full suites run only when the ``ci:full`` label asks for them, or when the
workflow is called or dispatched; ``Check: Merge gate (Linux)`` is the sole
required check and always reaches a verdict. This guard pins that topology,
every recipe each tier runs, and the failure semantics that keep independent
diagnostics visible after an earlier gate fails.

It also pins the naming grammar shared across the fleet: a workflow is named
``Core <subject>`` and a job ``<Check|Test|Build>: <subject> (<platforms>)``,
so the checks list reads the same in every repository.

The recipe checks intentionally complement the duplicate-work checks:
``test-broad`` is expected once per operating system, while every other
validation recipe occurs once in the gate only.
"""

from __future__ import annotations

import re
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

#: Every workflow. The naming and timeout rules are about the whole Actions
#: surface, not about one workflow.
WORKFLOWS = ROOT / ".github" / "workflows"

#: The pull-request workflow. The tiering and the no-repeat rule are about the
#: check set a merge waits on, which is this file and no other.
GATE = WORKFLOWS / "merge-gate.yml"

LINT_JOB = "lint"
LINUX_JOB = "test-linux"
WINDOWS_JOB = "test-windows"
GATE_JOB = "gate"
EXPECTED_NAMES = {
    LINT_JOB: "Check: Lint (Linux)",
    LINUX_JOB: "Test: Full suite (Linux)",
    WINDOWS_JOB: "Test: Library suite (Windows)",
    GATE_JOB: "Check: Merge gate (Linux)",
}

#: The label that asks for one full run.
FULL_LABEL = "ci:full"

#: The only workflow a push to main may start. main is ruleset-protected, so a
#: commit reaching it already passed the gate; release-please is the one lane
#: whose work begins when a release-bearing commit lands.
PUSH_MAIN_WORKFLOWS = frozenset({"release-please.yml"})

LINT_RECIPES = (
    "init",
    "deps-check",
    "check-workflow",
    "check-python",
    "check-type-platforms",
    "check-toml",
    "check-markdown",
)
LINUX_RECIPES = (
    "init",
    "check-links",
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

#: `<Check|Test|Build>: <subject> (<platforms>)`. A reusable-workflow call
#: spans the platforms of the jobs it runs, so the parenthesis may list more
#: than one.
_JOB_NAME = re.compile(
    r"^(Check|Test|Build): [A-Za-z0-9][A-Za-z0-9 .:_-]*"
    r" \((Linux|Windows|macOS)( [A-Za-z0-9._:-]+)?"
    r"(, [A-Za-z0-9._:-]+(?: [A-Za-z0-9._:-]+)?)*\)$"
)
_WORKFLOW_NAME = re.compile(r"^Core [A-Z][A-Za-z0-9 ]*$")
_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.(?P<key>[\w-]+)\s*\}\}")

#: How a recipe prefix is spelled in the registry. The gating verb is ``lint``
#: in the table and ``check`` at the recipe, because a contributor reaches for
#: "check the types". Every other prefix spells the same on both sides.
RECIPE_VERB = {"check": "lint"}

#: Recipes that PROVISION rather than check. Every job needs the environment,
#: so these are expected in all of them and are not repeated work in the sense
#: this file polices - re-running them is how a second machine gets a venv.
PROVISIONING = frozenset({"just init", "just framework-install"})


def _load(path: Path) -> dict[str, Any]:
    """Parse one workflow file."""
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _workflow_jobs(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return one workflow's jobs, typed for the walks below."""
    return cast("dict[str, dict[str, Any]]", document.get("jobs") or {})


def _gate() -> dict[str, Any]:
    """Parse the pull-request workflow."""
    return _load(GATE)


def _jobs() -> dict[str, dict[str, Any]]:
    """Return the merge-gate jobs with a useful type for topology assertions."""
    return _workflow_jobs(_gate())


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


def _workflow_paths() -> list[Path]:
    """Every workflow file, proven to exist before anything reads them.

    Globbed in a helper rather than in the test, and asserted non-empty here:
    ``Path.glob`` treats "missing" and "empty" alike and raises for neither, so
    a renamed directory would otherwise retire the guards below by giving them
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


def _check_names(job: dict[str, Any], job_id: str) -> list[str]:
    """Every status-check name one job definition produces.

    A matrix job produces one check per leg, so every ``${{ matrix.<key> }}``
    is expanded here: the names a reader sees are the expanded ones, and an
    unexpanded expression would sail through the pattern on the literal.
    """
    name = str(job.get("name", job_id))
    keys = {match.group("key") for match in _MATRIX_REF.finditer(name)}
    if not keys:
        return [name]
    include = _matrix_include(job)
    assert include, (
        f"job `{job_id}` interpolates {sorted(keys)} into its check name but "
        "declares no `include:` entries to expand them from"
    )
    names: list[str] = []
    for entry in include:
        missing = keys - set(entry)
        assert not missing, (
            f"job `{job_id}` names {sorted(missing)} in its check name, which a "
            f"matrix entry does not declare: {entry}"
        )
        names.append(
            _MATRIX_REF.sub(lambda match, e=entry: str(e[match.group("key")]), name)
        )
    return names


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


def test_the_gate_has_exactly_its_tiered_jobs() -> None:
    """Lint, two full suites, and the gate - nothing more, nothing hidden."""
    jobs = _jobs()
    assert set(jobs) == set(EXPECTED_NAMES), (
        f"merge-gate.yml must contain exactly {sorted(EXPECTED_NAMES)}; "
        f"found {sorted(jobs)}"
    )
    for job_id, name in EXPECTED_NAMES.items():
        assert jobs[job_id]["name"] == name
        # A matrix would make the status set dynamic and let one platform
        # disappear behind another.
        assert "strategy" not in jobs[job_id], f"`{job_id}` must not be a matrix job"

    # The suites must not wait on the lint or on each other: a red lint must
    # not hide what the suites would have said.
    for job_id in (LINT_JOB, LINUX_JOB, WINDOWS_JOB):
        assert "needs" not in jobs[job_id], f"`{job_id}` must start independently"


def test_the_gate_runs_on_pull_requests_calls_and_dispatches_only() -> None:
    """Every push to a pull request is seen; main pushes are not."""
    events = _events(_gate())
    assert set(events) == {"pull_request", "workflow_call", "workflow_dispatch"}
    pull_request = cast("dict[str, Any]", events["pull_request"])
    assert set(pull_request.get("types", [])) == {
        "opened",
        "reopened",
        "synchronize",
        "labeled",
    }
    call_inputs = cast("dict[str, Any]", events["workflow_call"]["inputs"])
    assert call_inputs["ref"]["required"] is True, (
        "a caller must name the ref it wants proven; the default would be the "
        "caller's own ref, which for the release lane is main, not the tag"
    )


def test_only_release_please_runs_when_main_moves() -> None:
    """A direct push to main starts nothing but the release proposal."""
    pushed: set[str] = set()
    for path in _workflow_paths():
        if "push" in _events(_load(path)):
            pushed.add(path.name)
    assert pushed == PUSH_MAIN_WORKFLOWS, (
        "only release-please may run on a push; main is protected, so every "
        f"commit on it already passed the merge gate. Push-triggered: {sorted(pushed)}"
    )


def test_the_full_suites_run_only_when_asked() -> None:
    """A push runs the lint; the label, a call, or a dispatch runs the suites."""
    jobs = _jobs()
    for job_id in (LINUX_JOB, WINDOWS_JOB):
        condition = str(jobs[job_id].get("if", ""))
        assert "github.event_name != 'pull_request'" in condition, condition
        assert "github.event.action == 'labeled'" in condition, condition
        assert f"github.event.label.name == '{FULL_LABEL}'" in condition, condition
        assert "head.repo.full_name == github.repository" in condition, (
            f"`{job_id}` would run a fork's code on the self-hosted fleet"
        )

    lint = str(jobs[LINT_JOB].get("if", ""))
    assert "head.repo.full_name == github.repository" in lint, (
        "the lint would run a fork's code on the self-hosted fleet"
    )
    assert f"github.event.label.name == '{FULL_LABEL}'" in lint, (
        "an unrelated label must not re-run the lint"
    )


def test_the_gate_always_reaches_a_verdict() -> None:
    """The required check is never skipped, and it weighs every tier.

    A required check whose job is skipped counts as passed, so a gate with a
    narrower condition would let an unrelated label merge an unproven commit.
    """
    gate = _jobs()[GATE_JOB]
    assert gate.get("if") == "${{ !cancelled() }}"
    assert set(gate.get("needs", [])) == {LINT_JOB, LINUX_JOB, WINDOWS_JOB}

    env = cast("dict[str, str]", gate.get("env", {}))
    needed = (("LINT", LINT_JOB), ("LINUX", LINUX_JOB), ("WINDOWS", WINDOWS_JOB))
    for key, job_id in needed:
        assert env.get(key) == f"${{{{ needs.{job_id}.result }}}}", (
            f"the gate no longer reads `{job_id}`'s result"
        )

    steps = {str(step.get("name")): step for step in gate["steps"]}
    judge = steps["Judge the merge readiness"]
    script = str(judge["run"])
    assert "check_name=Check:%20Merge%20gate%20(Linux)" in script, (
        "a lint-only run must look for an earlier full verdict under the "
        "required check's exact name"
    )
    assert "HEAD_SHA" in script, "the earlier verdict must be on the same commit"
    assert (
        env.get("HEAD_REPO") == "${{ github.event.pull_request.head.repo.full_name }}"
    )
    refusal = script.index('[ "${HEAD_REPO}" != "${GITHUB_REPOSITORY}" ]')
    assert refusal < script.index("exit 0"), (
        "a fork pull request must be refused before any path can pass the gate"
    )

    release = steps["Release the ci:full label"]
    assert "|| true" in str(release["run"]), (
        "a label another run already removed must not redden the gate"
    )


def test_each_tier_keeps_its_recipes_and_one_provisioning_cycle() -> None:
    """Each job runs its recipes once and provisions once."""
    jobs = _jobs()
    assert Counter(_just_recipes(jobs[LINT_JOB])) == Counter(LINT_RECIPES)
    assert Counter(_just_recipes(jobs[LINUX_JOB])) == Counter(LINUX_RECIPES)
    assert Counter(_just_recipes(jobs[WINDOWS_JOB])) == Counter(WINDOWS_RECIPES)
    assert not _just_recipes(jobs[GATE_JOB]), "the gate judges; it runs no recipe"

    for job_id in (LINT_JOB, LINUX_JOB, WINDOWS_JOB):
        job = jobs[job_id]
        assert len(_uses(job, "actions/checkout@")) == 1
        assert len(_uses(job, "actions/setup-python@")) == 1
        uv_steps = _uses(job, "astral-sh/setup-uv@")
        assert len(uv_steps) == 1
        assert uv_steps[0].get("with", {}).get("enable-cache") is False

    def tools(job_id: str) -> set[str]:
        return {
            str(step.get("with", {}).get("tool"))
            for step in _uses(jobs[job_id], "taiki-e/install-action@")
        }

    assert tools(LINT_JOB) == {"taplo-cli", "just@1.38.0"}
    assert tools(LINUX_JOB) == {"lychee", "just@1.38.0"}
    assert tools(WINDOWS_JOB) == {"just@1.38.0"}
    assert jobs[WINDOWS_JOB].get("env", {}).get("PYTEST_XDIST_AUTO_NUM_WORKERS") == "4"


def test_gates_run_after_failures_without_erasing_failure() -> None:
    """Independent gates always run and no step is allowed to mask red."""
    jobs = _jobs()
    for job_id in (LINT_JOB, LINUX_JOB):
        for step in jobs[job_id]["steps"]:
            command = step.get("run", "")
            if not isinstance(command, str) or not command.strip().startswith("just "):
                continue
            recipe = command.strip().removeprefix("just ").split()[0]
            if recipe == "init":
                continue
            assert step.get("if") == "always()", (
                f"`{job_id}` gate `{recipe}` must run after earlier failures"
            )

    for job in jobs.values():
        assert not any(
            step.get("continue-on-error", False) for step in job.get("steps", [])
        ), "CI gates must not turn a failed command into a passing job"


def test_every_workflow_and_job_name_follows_the_grammar() -> None:
    """`Core <subject>` workflows, `<Verb>: <subject> (<platforms>)` jobs."""
    offenders: list[str] = []
    for path in _workflow_paths():
        document = _load(path)
        name = str(document.get("name", ""))
        if not _WORKFLOW_NAME.fullmatch(name):
            offenders.append(f"{path.name}: workflow name {name!r}")
        for job_id, job in _workflow_jobs(document).items():
            for check in _check_names(job, job_id):
                if not _JOB_NAME.fullmatch(check):
                    offenders.append(f"{path.name}:{job_id}: {check!r}")
    assert not offenders, (
        "these names break the fleet grammar - `Core <subject>` for a "
        "workflow, `<Check|Test|Build>: <subject> (<platforms>)` for a job:\n  "
        + "\n  ".join(offenders)
    )


def test_every_check_name_is_unique_within_its_workflow() -> None:
    """Two checks with one name are indistinguishable in the merge box."""
    for path in _workflow_paths():
        document = _load(path)
        names = [
            check
            for job_id, job in _workflow_jobs(document).items()
            for check in _check_names(job, job_id)
        ]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        assert not duplicates, f"{path.name} repeats check names: {duplicates}"


def test_no_check_name_is_spelled_by_the_tool_that_implements_it() -> None:
    """The subject says what is covered, not what covers it.

    ``Dependency Audit (uv audit)`` was accurate on the day it was written and
    stops being so the day the tool is replaced, at which point the merge box
    names something that no longer runs.
    """
    tools = ("uv", "ruff", "pytest", "ty", "pylint", "mypy", "actionlint", "just")
    for path in _workflow_paths():
        for job_id, job in _workflow_jobs(_load(path)).items():
            for name in _check_names(job, job_id):
                words = {word.strip("():,&").lower() for word in name.split()}
                named = sorted(words & set(tools))
                assert not named, (
                    f"check name {name!r} ({path.name}:{job_id}) names the tool "
                    f"{named}. Name the subject it covers instead - the tool is "
                    "an implementation detail that a reader cannot act on and a "
                    "replacement makes a lie."
                )


def test_no_job_repeats_work_another_job_already_does() -> None:
    """No two jobs in the pull-request path run the same underlying command.

    Expanded to leaf commands, so an aggregate composing a leaf that another
    job names directly fails here just as a literal repeat would.
    """
    by_job: dict[str, set[tuple[str, ...]]] = {}
    for job_id, job in _jobs().items():
        commands: set[tuple[str, ...]] = set()
        for step in job.get("steps", []):
            run = str(step.get("run", "")).strip()
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
        # system. It is the only expected cross-job overlap.
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
        for job in _jobs().values()
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
        for job_id, job in _workflow_jobs(_load(path)).items():
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


def test_no_workflow_runs_a_fork_on_any_runner() -> None:
    """Fork pull requests always fail: no job may fall back to a hosted runner.

    A `runs-on` that switches on the head repository would run a fork's code
    somewhere and let its checks report; the rule is refusal, everywhere.
    """
    offenders = [
        f"{path.name}:{job_id}"
        for path in _workflow_paths()
        for job_id, job in _workflow_jobs(_load(path)).items()
        if "head.repo" in str(job.get("runs-on", ""))
    ]
    assert not offenders, f"these jobs pick a runner by head repository: {offenders}"


def test_a_release_run_of_the_gate_is_never_superseded() -> None:
    """Only pull-request runs cancel; a call or a dispatch is a release.

    GitHub cancels a PENDING run in an occupied group whatever
    `cancel-in-progress` says, so the group must also separate triggers: an
    unrelated label must not share a group with the full run it would kill.
    """
    concurrency = cast("dict[str, str]", _gate().get("concurrency") or {})
    group = concurrency.get("group", "")
    cancel = str(concurrency.get("cancel-in-progress", ""))

    assert cancel == "${{ github.event_name == 'pull_request' }}", cancel
    assert "github.event.pull_request.number" in group, group
    assert "inputs.ref" in group, (
        "two release refs proven at once must not share a group"
    )
    assert "github.event.label.name" in group, (
        "an unrelated label would cancel the full run in flight"
    )
