"""Contracts on the SHAPE of the pull-request check set: names, and no repeats.

Two properties, both about the merge box rather than about any one gate.

*Nothing runs twice.* This fleet has one Linux runner and one Windows runner,
so every job in ``ci.yml`` executes serially on one of two machines. Work
repeated between two jobs is not redundancy, it is latency, and it had
accumulated in four places at once: a unit lane that was a marker-scoped subset
of the broad lane, a Windows vault-repair job whose two files the Windows broad
leg already collected, a host-platform ``ty`` pass that is the Linux third of
the all-platforms pass, and a dependency audit composed into the advisory
dashboard while also holding a gating job of its own.

Two shapes of repeat, so two checks. An aggregate that composes a leaf another
job names directly runs the SAME command twice, and is caught by expanding
every recipe down to the commands it finally runs. A subset lane runs
DIFFERENT commands over a population another lane already covers - ``-m "unit
and ..."`` against ``-m "..."``, ``--python-platform linux`` against no flag on
a Linux runner - where the argv differ and only the relationship is the defect.
Those are named.

*Names say what they cover.* ``broad`` named a pytest marker, and
``Dependency Audit (uv audit)`` named a tool that can change. Neither told a
reader looking at a red merge box what had failed. Every check is now
``<Kind>: <Subject>`` with an optional ``(Platform)``, where the kind is one of
the three the justfile already groups recipes under.
"""

from __future__ import annotations

import re
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

#: ``<Kind>: <Subject>`` with an optional ``(Platform)``. The kinds are the
#: justfile's own recipe groups, so ``just --list`` and the merge box use one
#: vocabulary: Lint reads the tree, Test executes something, Audit asks a third
#: party for a verdict.
CHECK_NAME = re.compile(
    r"^(?P<kind>Lint|Test|Audit): "
    r"(?P<subject>[A-Z][A-Za-z]*(?:(?:, | & | )[A-Za-z][A-Za-z]*)*)"
    r"(?: \((?P<platform>[A-Za-z${}. ]+)\))?$"
)

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


def _check_names(job: dict[str, Any], job_id: str) -> list[str]:
    """Every status-check name one job definition produces.

    A matrix job produces one check per leg, so the matrix is expanded here:
    the names a merge waits on are the expanded ones, and an unexpanded
    ``${{ matrix.name }}`` would sail through the pattern on the literal.
    """
    name = job.get("name", job_id)
    include = job.get("strategy", {}).get("matrix", {}).get("include", [])
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
    """Each status check is ``<Kind>: <Subject>`` with an optional platform."""
    jobs = _ci()["jobs"]
    assert jobs, "ci.yml declares no jobs"
    for job_id, job in jobs.items():
        for name in _check_names(job, job_id):
            assert CHECK_NAME.match(name), (
                f"check name {name!r} (job `{job_id}`) does not follow "
                "`<Kind>: <Subject>` with an optional ` (Platform)`, where "
                "Kind is Lint, Test or Audit. A reader of a red merge box has "
                "the name and nothing else."
            )


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
