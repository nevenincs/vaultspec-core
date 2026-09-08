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
from dev.toolchain import DEFAULTS, VERBS, Verb, find_verb, public_targets

pytestmark = pytest.mark.unit

JUSTFILE = Path(__file__).resolve().parents[2] / "justfile"

#: Recipes that deliberately do not route through `python -m dev`: the `init`
#: family must work before a virtual environment exists, and the rest wrap a
#: single external entry point that has no target dispatch to model.
NON_REGISTRY_RECIPES = frozenset(
    # `binaries` and `channels` are release-path recipes: each invokes a
    # `dev/` script directly under a bare `--no-project` interpreter, exactly
    # as the release workflow does, so a local reproduction and CI run the
    # same command. Routing them through the dev runner would put a project
    # environment between the maintainer and the thing being reproduced.
    # The `init` family provisions the environment `python -m dev` runs in, so
    # it cannot route through it; it runs on an ephemeral `--no-project`
    # interpreter, which is why `dev/init/` is stdlib-only.
    {
        "default",
        "init",
        "init-python",
        "init-node",
        "init-tools",
        "init-check",
        "analytics",
        "release-binaries",
        "release-channels",
        "ci",
    },
)

#: How a verb is SPELLED at the recipe versus in the registry. The gating verb
#: is `lint` in the table and `check` at the recipe, because a contributor
#: reaches for "check the types" and the group heading `check` is what
#: `just --list` sorts under. Every other verb spells the same on both sides.
RECIPE_VERB_SPELLING: dict[str, str] = {"check": "lint"}

#: Test lanes deliberately reachable only by naming them, each with its reason.
#: Every other lane must be in `test all` or a CI step - see
#: :func:`test_every_test_lane_is_reachable_from_an_aggregate_or_ci`.
DELIBERATELY_MANUAL = {
    # `-m benchmark` is deselected by the default addopts in pyproject.toml, so
    # these never run as a correctness gate. They are slow scale benchmarks
    # whose wall-clock measurements are the subject under test; a loaded CI
    # runner fails them for reasons unrelated to a regression.
    "benchmark",
    # `unit` is `broad`'s selection with `unit and` prepended and `-x` added,
    # over the same path. CI runs `broad` on both operating systems, so a CI
    # step naming `unit` re-ran a strict subset of work already done on the
    # same machine - six minutes of serial time on a fleet with one Linux
    # runner. The lane stays because the fast fail-first slice is the local
    # inner loop; nothing is unobserved by its absence from CI, because
    # everything it selects is selected by a lane CI does run.
    "unit",
}


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_every_reference_resolves(verb: Verb) -> None:
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

    This guards a defect that actually shipped. The ``repo`` lane - which ran
    the repository-root ``tests/`` tree holding the automation contracts and
    the test-suite-quality guards - was in neither ``test all`` nor any CI job.
    Its own registry description said so. The doubles guard inside that tree
    had consequently been failing undetected: a guard nothing runs is not a
    guard. Both the lane and the tree are gone now - those guards live in
    ``dev/guards`` and are collected by the ``harness`` lane, which CI does
    run - but the check below is what keeps the next lane from repeating it.

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
        and f"just test-{target.name}" not in ci_text
    ]
    assert not unreachable, (
        "test lanes reachable from neither `test all` nor a CI step: "
        f"{sorted(unreachable)}. Add each to the `all` aggregate in "
        "dev/toolchain.py or name it in a workflow step."
    )


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_no_duplicate_target_names(verb: Verb) -> None:
    """A verb never defines the same target token twice."""
    names = verb.target_names()
    assert len(names) == len(set(names)), f"{verb.name} has duplicate targets: {names}"


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_targets_are_documented_and_executable(verb: Verb) -> None:
    """Every target carries a summary for `help` and at least one step."""
    for target in verb.targets:
        assert target.summary.strip(), f"{verb.name}.{target.name} has no summary"
        assert target.steps, f"{verb.name}.{target.name} has no steps"


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_default_target_exists(verb: Verb) -> None:
    """Each verb declares a default target, and that target is defined."""
    assert verb.name in DEFAULTS, f"{verb.name} has no entry in DEFAULTS"
    default = DEFAULTS[verb.name]
    assert verb.find(default) is not None, (
        f"{verb.name} defaults to '{default}', which is not a defined target"
    )


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_references_terminate(verb: Verb) -> None:
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


def _recipe_verb(name: str) -> str:
    """Return the registry verb a flat recipe name dispatches to."""
    head, _, _tail = name.partition("-")
    return RECIPE_VERB_SPELLING.get(head, head)


def test_justfile_exposes_every_registry_target() -> None:
    """Every target in the registry is typeable as a recipe of its own.

    The verb-plus-argument form kept the real surface out of `just --list`: a
    contributor could not discover `type-platforms` without reading this table.
    Each target is now its own recipe, so the list IS the surface - which only
    holds if every target actually has one.
    """
    recipes = _justfile_recipe_names()
    missing: list[str] = []
    for verb in VERBS:
        # `ci` is the composed pipeline, reached as the bare `just ci`. Its one
        # target exists only so the dispatcher has something to select.
        if verb.name == "ci":
            continue
        spelling = next(
            (
                recipe
                for recipe, registry in RECIPE_VERB_SPELLING.items()
                if registry == verb.name
            ),
            verb.name,
        )
        missing.extend(
            f"{spelling}-{target.name}"
            for target in verb.targets
            if not target.name.startswith("_")
            and f"{spelling}-{target.name}" not in recipes
        )
    assert not missing, f"registry targets with no justfile recipe: {sorted(missing)}"


def test_every_dispatching_recipe_names_a_real_target() -> None:
    """Every dispatching recipe resolves to a verb AND one of its targets.

    A typo in the target segment is otherwise invisible until someone runs the
    recipe: it exists, so `just --list` offers it, and only the dispatcher
    rejects the argument.
    """
    unknown: list[str] = []
    for name in sorted(_justfile_recipe_names() - NON_REGISTRY_RECIPES):
        verb = find_verb(_recipe_verb(name))
        if verb is None:
            unknown.append(name)
            continue
        target = name.partition("-")[2]
        if not target or verb.find(target) is None:
            unknown.append(name)
    assert not unknown, f"justfile recipes with no registry target: {unknown}"


def test_public_targets_hide_internal_helpers() -> None:
    """Underscore-prefixed targets never appear in help output."""
    for verb in VERBS:
        assert all(not name.startswith("_") for name in public_targets(verb))
