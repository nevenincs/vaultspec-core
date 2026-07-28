"""Integrity guards for the verb and target registry.

The failure these guard against is silent: a target renamed in
:mod:`dev.toolchain` but still referenced from an aggregate, or a verb exposed
by the ``justfile`` that no longer exists in the registry, produces a recipe
that only fails when someone runs that exact path. Every check below turns one
of those into a collection-time failure instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dev.runner import Ref
from dev.toolchain import DEFAULTS, VERBS, find_verb, public_targets

pytestmark = pytest.mark.unit

JUSTFILE = Path(__file__).resolve().parents[2] / "justfile"

#: Recipes that deliberately do not route through `python -m dev`: `bootstrap`
#: must work before a virtual environment exists, and the rest wrap a single
#: external entry point that has no target dispatch to model.
NON_REGISTRY_RECIPES = frozenset({"default", "bootstrap", "analytics", "binaries"})

#: Test lanes deliberately reachable only by naming them, each with its reason.
#: Every other lane must be in `test all` or a CI step - see
#: :func:`test_every_test_lane_is_reachable_from_an_aggregate_or_ci`.
DELIBERATELY_MANUAL = {
    # `-m benchmark` is deselected by the default addopts in pyproject.toml, so
    # these never run as a correctness gate. They are slow scale benchmarks
    # whose wall-clock measurements are the subject under test; a loaded CI
    # runner fails them for reasons unrelated to a regression.
    "benchmark",
}


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_every_reference_resolves(verb) -> None:
    """Each aggregate target references a target that exists in its verb."""
    for target in verb.targets:
        for step in target.steps:
            if isinstance(step, Ref):
                assert verb.find(step.target) is not None, (
                    f"{verb.name}.{target.name} references undefined target "
                    f"'{step.target}'"
                )


def test_every_test_lane_is_reachable_from_an_aggregate_or_ci() -> None:
    """No test lane may be runnable only by someone naming it from memory.

    This guards a defect that actually shipped. The ``repo`` lane - which runs
    the repository-root ``tests/`` tree holding the automation contracts and
    the test-suite-quality guards - was in neither ``test all`` nor any CI job.
    Its own registry description said so. The doubles guard inside that tree
    had consequently been failing undetected: a guard nothing runs is not a
    guard.

    A lane is considered reachable when ``test all`` references it, a CI
    workflow step invokes it by name, or it is named in
    :data:`DELIBERATELY_MANUAL` below. Adding a lane and wiring it to none of
    the three fails here rather than silently going unobserved. The exemption
    set is explicit on purpose: a lane nobody runs and a lane deliberately left
    manual look identical from the registry, and only one of them is fine.
    """
    verb = find_verb("test")
    assert verb is not None

    aggregate = verb.find("all")
    assert aggregate is not None, "the `test` verb must expose an `all` aggregate"
    referenced = {step.target for step in aggregate.steps if isinstance(step, Ref)}

    workflows = (Path(__file__).resolve().parents[2] / ".github" / "workflows").glob(
        "*.yml"
    )
    ci_text = "\n".join(path.read_text(encoding="utf-8") for path in workflows)

    unreachable = [
        target.name
        for target in verb.targets
        if target.name not in {"all", *referenced, *DELIBERATELY_MANUAL}
        and f"just test {target.name}" not in ci_text
    ]
    assert not unreachable, (
        "test lanes reachable from neither `test all` nor a CI step: "
        f"{sorted(unreachable)}. Add each to the `all` aggregate in "
        "dev/toolchain.py or name it in a workflow step."
    )


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_no_duplicate_target_names(verb) -> None:
    """A verb never defines the same target token twice."""
    names = verb.target_names()
    assert len(names) == len(set(names)), f"{verb.name} has duplicate targets: {names}"


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_targets_are_documented_and_executable(verb) -> None:
    """Every target carries a summary for `help` and at least one step."""
    for target in verb.targets:
        assert target.summary.strip(), f"{verb.name}.{target.name} has no summary"
        assert target.steps, f"{verb.name}.{target.name} has no steps"


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_default_target_exists(verb) -> None:
    """Each verb declares a default target, and that target is defined."""
    assert verb.name in DEFAULTS, f"{verb.name} has no entry in DEFAULTS"
    default = DEFAULTS[verb.name]
    assert verb.find(default) is not None, (
        f"{verb.name} defaults to '{default}', which is not a defined target"
    )


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_references_terminate(verb) -> None:
    """No aggregate target can reach itself, directly or transitively."""

    def walk(name: str, seen: frozenset[str]) -> None:
        assert name not in seen, f"{verb.name}.{name} is part of a reference cycle"
        target = verb.find(name)
        if target is None:
            return
        for step in target.steps:
            if isinstance(step, Ref):
                walk(step.target, seen | {name})

    for target in verb.targets:
        walk(target.name, frozenset())


def _justfile_recipe_names() -> set[str]:
    """Return every recipe name declared in the justfile."""
    pattern = re.compile(r"^([a-z][a-z0-9-]*)(?:\s+[^:\n]*)?:\s*$", re.MULTILINE)
    text = JUSTFILE.read_text(encoding="utf-8")
    return set(pattern.findall(text))


def test_justfile_exposes_every_registry_verb() -> None:
    """Every verb in the registry has a justfile recipe of the same name."""
    recipes = _justfile_recipe_names()
    missing = {verb.name for verb in VERBS} - recipes
    assert not missing, f"registry verbs with no justfile recipe: {sorted(missing)}"


def test_every_dispatching_recipe_has_a_verb() -> None:
    """Every justfile recipe that dispatches to `dev` names a real verb."""
    unknown = sorted(
        name
        for name in _justfile_recipe_names() - NON_REGISTRY_RECIPES
        if find_verb(name) is None
    )
    assert not unknown, f"justfile recipes with no registry verb: {unknown}"


def test_public_targets_hide_internal_helpers() -> None:
    """Underscore-prefixed targets never appear in help output."""
    for verb in VERBS:
        assert all(not name.startswith("_") for name in public_targets(verb))
