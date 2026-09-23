"""Contracts binding the repository's automation surfaces to each other.

The failures guarded here are the ones no single tool reports: a CI job that
stops invoking the gate it claims to run, a ``justfile`` recipe that grows
shell logic the declarative registry was meant to own, a threshold that drifts
away from its declaration site, or two independent type-check invocations that
quietly stop covering the same trees.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]


class _PreCommitHook(TypedDict):
    """One hook entry under a ``.pre-commit-config.yaml`` repo block."""

    id: str
    entry: str


class _PreCommitRepo(TypedDict):
    """One repo block in ``.pre-commit-config.yaml``."""

    hooks: list[_PreCommitHook]


class _PreCommitConfig(TypedDict):
    """The top-level shape of ``.pre-commit-config.yaml``."""

    repos: list[_PreCommitRepo]


#: One step in a GitHub Actions job. Declared functionally because `if` and
#: `with` are Python keywords and so cannot be attributes in the class syntax.
_WorkflowStep = TypedDict(
    "_WorkflowStep",
    {
        "name": str,
        "run": str,
        "uses": str,
        "if": str,
        "with": dict[str, str],
        "env": dict[str, str],
    },
    total=False,
)

#: Length of a SHA-256 digest written as hex, which is how release checksums
#: are published and therefore how they are pinned in a workflow.
_SHA256_HEX_LENGTH = 64

#: Actionlint is pinned by a concrete release version, not a floating label.
_ACTIONLINT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


class _WorkflowJob(TypedDict):
    """One job in a GitHub Actions workflow."""

    steps: list[_WorkflowStep]


class _Workflow(TypedDict):
    """The top-level shape of a GitHub Actions workflow file."""

    jobs: dict[str, _WorkflowJob]


class _BasedpyrightExecutionEnvironment(TypedDict, total=False):
    """One override block under ``[[tool.basedpyright.executionEnvironments]]``."""

    root: str
    reportPrivateUsage: bool


class _BasedpyrightConfig(TypedDict):
    """The slice of ``[tool.basedpyright]`` this guard reads."""

    include: list[str]
    executionEnvironments: list[_BasedpyrightExecutionEnvironment]


class _PyprojectToolTable(TypedDict):
    """The ``[tool]`` table, narrowed to what this guard reads."""

    basedpyright: _BasedpyrightConfig


class _PyprojectConfig(TypedDict):
    """The top-level shape of ``pyproject.toml``, narrowed to what this guard reads."""

    tool: _PyprojectToolTable


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_yaml(path: str) -> object:
    return yaml.safe_load(_read(path))


def _load_pre_commit_config() -> _PreCommitConfig:
    """Parse ``.pre-commit-config.yaml`` into its known schema.

    Invariant: this repo's own config always nests
    ``repos: [{hooks: [{id: ...}]}]``; ``yaml.safe_load`` has no schema of
    its own, so this cast is the one place that shape is asserted.
    """
    return cast("_PreCommitConfig", _load_yaml(".pre-commit-config.yaml"))


def _load_workflow(path: str) -> _Workflow:
    """Parse a GitHub Actions workflow file into its known schema.

    Invariant: this repo's own workflow files always nest
    ``jobs: {name: {steps: [{run?, uses?, ...}]}}``; ``yaml.safe_load`` has
    no schema of its own, so this cast is the one place that shape is
    asserted.
    """
    return cast("_Workflow", _load_yaml(path))


def _load_basedpyright_config() -> _BasedpyrightConfig:
    """Parse ``[tool.basedpyright]`` out of ``pyproject.toml``.

    Invariant: this repo's own ``pyproject.toml`` always declares the table
    with an ``executionEnvironments`` array of tables; ``tomllib`` has no
    schema of its own, so this cast is the one place that shape is asserted.
    """
    raw = tomllib.loads(_read("pyproject.toml"))
    # Routed through `object` because a plain dict and a TypedDict are never
    # considered sufficiently overlapping for a direct cast, regardless of how
    # well the shape is known; the intermediate step expresses that, rather
    # than signalling an unproven shape.
    parsed = cast("_PyprojectConfig", cast("object", raw))
    return parsed["tool"]["basedpyright"]


def _colocated_test_dirs() -> set[str]:
    """Return every co-located ``tests/`` directory basedpyright checks.

    The trees are read from basedpyright's own ``include`` list rather than
    hardcoded, so this follows the configuration when the layout moves. That
    is not hypothetical: the co-location convention started inside
    ``src/vaultspec_core`` alone and now spans the instrument trees too, and a
    guard naming one tree by hand would have gone quietly half-blind at the
    moment the others appeared.
    """
    included = _load_basedpyright_config()["include"]
    found = {
        path.relative_to(ROOT).as_posix()
        for tree in included
        for path in (ROOT / tree).rglob("tests")
        # The walk reads the FILESYSTEM, not the index, so a directory git
        # stopped tracking survives as whatever untracked debris is left in
        # it - and `__pycache__` is always left. Without the source test,
        # renaming a co-located test package demanded an exemption for a
        # directory that no longer exists: red on the working tree where the
        # rename was correct, green on CI's fresh checkout. A gate that is red
        # only where the work happens teaches people to stop reading it. The
        # emptiness of this inner glob is an ANSWER, not an accident; the
        # corpus it feeds is proven non-empty by the assert below.
        #
        # The question is what basedpyright ANALYSES, which is source on disk,
        # so stubs count too. `git ls-files` would be the wrong instrument
        # despite being the one that knows what is tracked: a test file
        # written but not yet added is analysed, needs the exemption, and is
        # invisible to the index.
        if path.is_dir()
        and "__pycache__" not in path.parts
        and any(child.suffix in {".py", ".pyi"} for child in path.rglob("*"))
    }
    # The caller subtracts this set from the exemption list and asserts the
    # remainder is empty, so an empty set here passes unconditionally - a
    # renamed tree under `include` would retire the guard rather than trip it.
    assert found, f"no co-located tests directories found under {included}"
    return found


#: The group taxonomy, identical in every repository in the fleet. Closed on
#: purpose: `just --list` sorts by group, so a new group silently forks the
#: vocabulary a contributor learns once and expects to hold everywhere.
CLOSED_GROUPS: frozenset[str] = frozenset(
    {
        "setup",
        "dev",
        "check",
        "fix",
        "audit",
        "build",
        "release",
        "docs",
        "test",
        "meta",
    }
)

#: The recipes every repository in the fleet exposes under the same name. Kept
#: to the aggregates and the pipeline deliberately: those are the contract a CI
#: workflow and a contributor rely on across repositories, while every other
#: recipe is this repository's own business.
REQUIRED_RECIPES: frozenset[str] = frozenset(
    {
        "check-all",
        "fix-all",
        "audit-all",
        "test-all",
        "build-all",
        "ci",
    }
)


def _recipe_exists(justfile_text: str, name: str) -> bool:
    pattern = rf"(?m)^{re.escape(name)}(?:\s|:)"
    return re.search(pattern, justfile_text) is not None


def test_justfile_exposes_every_recipe_flat_and_hyphenated() -> None:
    """Every entry point is a flat `<verb>-<thing>` recipe at the root.

    Three shapes have been retired here in turn: a `just dev <verb>` nested
    namespace, a `just prod` mirror of the shipped CLI, and the
    `<verb> <target>` argument dispatch that replaced them.  The argument form
    kept the real surface out of `just --list` and out of tab completion - you
    could not discover `type-platforms` without reading the toolchain table -
    so the thing a recipe acts on is now part of its name.  This pins the
    collapse so none of the three reappears.
    """
    justfile = _read("justfile")
    missing = [
        name for name in sorted(REQUIRED_RECIPES) if not _recipe_exists(justfile, name)
    ]
    assert not missing, f"Missing required just recipes: {missing}"

    assert not _recipe_exists(justfile, "prod"), (
        "`just prod` mirrored the shipped vaultspec-core CLI and was removed; "
        "invoke the product directly with `uv run --no-sync vaultspec-core`."
    )
    assert not re.search(r"(?m)^_dev-", justfile), (
        "The `_dev-*` internal recipe namespace was collapsed to root verbs."
    )
    argument_dispatch = re.findall(r"(?m)^([a-z-]+) target='[a-z-]+':", justfile)
    assert not argument_dispatch, (
        "These recipes still take a `target` argument, which hides their real "
        f"surface from `just --list`: {sorted(argument_dispatch)}"
    )


def test_every_public_recipe_declares_a_group_from_the_closed_set() -> None:
    """The group taxonomy is a closed set of ten, identical in every repository.

    Groups are what `just --list` sorts by, so an ungrouped recipe is filed
    under a blank heading and an off-taxonomy group silently forks the fleet's
    vocabulary.  Both are build failures rather than review catches.
    """
    justfile = _read("justfile")
    declared = set(re.findall(r"(?m)^\[group\('([a-z-]+)'\)\]", justfile))
    assert declared <= CLOSED_GROUPS, (
        f"Groups outside the closed set: {sorted(declared - CLOSED_GROUPS)}"
    )
    lines = justfile.splitlines()
    ungrouped = [
        line.split(":")[0].split(" ")[0]
        for index, line in enumerate(lines)
        if re.match(r"^[a-z][a-zA-Z0-9-]*(\s+[^:]*)?:", line)
        and ":=" not in line
        and not any(
            previous.startswith("[group(")
            for previous in lines[max(0, index - 4) : index]
        )
    ]
    assert not ungrouped, f"These recipes declare no group: {sorted(set(ungrouped))}"


def test_every_aggregate_dispatches_rather_than_chaining_dependencies() -> None:
    """An `-all` recipe must run every step and report, not stop at the first.

    A just dependency list is fail-fast and cannot express run-all-then-report,
    so an aggregate written as `check-all: check-python check-toml ...` reports
    one failure where there may be six and costs a round-trip per defect. The
    membership therefore lives in `dev/toolchain.py`, where the aggregate
    target is `keep_going` and composes `Ref`s to the same targets the
    individual recipes run.
    """
    justfile = _read("justfile")
    chained = re.findall(r"(?m)^([a-z-]+-all):[ 	]+\S", justfile)
    assert not chained, (
        "These aggregates are just dependency chains, which are fail-fast: "
        f"{sorted(chained)}. Dispatch them into dev/ instead."
    )


def test_justfile_delegates_every_verb_to_the_dev_package() -> None:
    """No recipe may carry shell logic; `dev/toolchain.py` is the only source.

    The justfile previously branched on `os()` and embedded PowerShell
    `switch` bodies, which meant every target existed twice and could drift
    between platforms.  Each recipe is now a single delegation, so the
    declarative toolchain is the one place a target is defined.
    """
    justfile = _read("justfile")
    for verb in ("deps", "lint", "fix", "audit", "test", "build", "health"):
        assert re.search(rf"(?m)^\s+\{{\{{dev\}}\}} {verb} [a-z-]+$", justfile), (
            f"No recipe delegates to the `{verb}` verb in one line"
        )
    for shell_ism in ('if os() == "windows"', "switch (", "Get-Command", "elseif"):
        assert shell_ism not in justfile, (
            f"Shell branching {shell_ism!r} belongs in dev/toolchain.py, "
            "not the justfile"
        )


def test_dependency_audit_resolves_its_own_verdict_from_osv() -> None:
    """Pin HOW the supply-chain gate reaches a verdict, not just that it runs.

    This guard used to assert the gate shelled out to ``uv audit`` with
    ``--preview-features`` and ``--frozen``. It no longer does, deliberately:
    ``uv audit`` exits 0 even when it prints advisories, so a gate whose
    verdict came from that process could not fail - which is exactly how three
    sibling repositories shipped a "GATE" that never gated. The gate now reads
    the committed lockfiles itself and queries OSV, so the verdict is a
    property of the finding set.

    That substitution is the thing worth pinning. A future edit that quietly
    reintroduces a vendor tool's exit code as the verdict, or drops an
    ecosystem, would be invisible in review and undetectable at runtime on a
    clean tree - the gate would simply stop being able to fail again.
    """
    toolchain = _read("dev/toolchain.py")
    gate = _read("dev/audit/dependency_audit.py")

    # The `audit deps` target delegates to the gate; nothing else may stand in.
    assert "dev/audit/dependency_audit.py" in toolchain

    # The verdict comes from OSV, queried in bulk over resolved coordinates.
    assert "api.osv.dev" in gate
    assert "querybatch" in gate

    # Coordinates come from the lockfiles that are actually committed, so a
    # repository that grows an ecosystem is covered when its lockfile lands
    # rather than when somebody remembers to add a scanner.
    for lockfile in ("uv.lock", "package-lock.json", "Cargo.lock"):
        assert lockfile in gate, f"{lockfile} is no longer a scanned surface"

    # No vendor scanner's process status may become the verdict again. The
    # gate runs no subprocess at all: it is stdlib-only over HTTPS. Asserted
    # against the parsed module rather than its text, so the prose explaining
    # why `uv audit` was abandoned does not itself read as a use of it.
    tree = ast.parse(gate)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported, (
        "the gate must not run child processes; its verdict is its own"
    )
    docstrings = {
        node.body[0].value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    } - docstrings
    assert "uv" not in literals, (
        "the gate names `uv` as a command again; its verdict must not come "
        "from a tool that exits 0 on findings"
    )

    # A uv-managed project stays uv-native end to end and never shells out to
    # pip. pip-audit drags `pip` itself in as a transitive dependency -
    # historically the only vulnerability ever reported on this project.
    for surface in (toolchain, gate):
        assert "pip-audit" not in surface
        assert "pip-tools" not in surface


def test_dependency_audit_fails_on_a_finding_and_on_a_lapsed_acceptance() -> None:
    """The gate's two failing verdicts are contracts, not implementation.

    A gate that cannot fail is not a gate, and an acceptance nobody has
    retaken is not an acceptance. Both are asserted against the real module so
    that neither can be softened to a warning without this failing.
    """
    from dev.audit import dependency_audit as gate

    assert gate.EXIT_OK == 0
    assert gate.EXIT_FINDINGS != 0
    # A gate that could not run is neither a pass nor a finding.
    assert gate.EXIT_BROKEN not in (gate.EXIT_OK, gate.EXIT_FINDINGS)

    source = _read("dev/audit/dependency_audit.py")
    # Suppressions are declarative and dated; the allowlist is their only home.
    assert "dependency-audit-allowlist.toml" in source
    assert "expires" in source


def test_pyproject_has_no_pip_named_dev_tools() -> None:
    pyproject = _read("pyproject.toml")
    # uv-managed projects do not need pip-named tooling. pip-audit drags in
    # `pip` itself as a transitive dependency, which historically introduced
    # the only vulnerability `uv audit` reported on this project.  The
    # contract: no pip-named dev tool may appear in either dev surface
    # (the optional-dependencies dev extra or the dependency-groups dev
    # group); use `uv audit` and uv-native commands instead.
    assert "pip-audit" not in pyproject
    assert "pip-tools" not in pyproject
    assert '"pip"' not in pyproject  # bare pip pin
    assert "pipenv" not in pyproject


def test_changelog_is_release_please_managed() -> None:
    """CHANGELOG.md must be the un-edited release-please artifact.

    Manual edits to CHANGELOG.md drift away from the lockstep
    commit-history -> changelog mapping that release-please maintains and
    silently break the next release PR.  Hand-written headers from older
    Keep-a-Changelog templates (`### Added`, `### Changed`, `### Removed`,
    `### Deprecated`, `### Security`, `[Unreleased]`) are the canonical
    fingerprint of manual content; their absence proves that
    release-please is the only writer.

    The pre-commit hook ``block-manual-changelog`` blocks fresh
    hand-edits at commit time; this test catches drift that lands by
    other means (rebase, force-push, tooling regression).
    """
    changelog = _read("CHANGELOG.md")

    forbidden_keep_a_changelog = (
        "### Added",
        "### Changed",
        "### Removed",
        "### Deprecated",
        "### Security",
        "## [Unreleased]",
        "## Unreleased",
    )
    leaked = [marker for marker in forbidden_keep_a_changelog if marker in changelog]
    assert not leaked, (
        f"CHANGELOG.md contains manual Keep-a-Changelog markers {leaked}; "
        "release-please does not emit those headings.  Remove them and "
        "let release-please regenerate the file."
    )

    # Every release entry must follow the release-please header shape:
    # `## [vX.Y.Z](compare-link) (yyyy-mm-dd)`.  A bare `## X.Y.Z` (no
    # compare link, no date) is a hand-written entry.
    release_headers = re.findall(r"(?m)^## .+$", changelog)
    bad = [h for h in release_headers if not re.match(r"^## \[\d", h)]
    assert not bad, (
        f"CHANGELOG.md has non-release-please section headers: {bad}.  "
        "Every release header must be `## [vX.Y.Z](compare) (date)` as "
        "emitted by release-please-action."
    )


def test_pre_commit_blocks_manual_changelog_edits() -> None:
    """The pre-commit gate against manual CHANGELOG.md edits must be wired.

    Without this hook nothing prevents a developer from staging a
    handwritten changelog entry alongside a code change; the gate is
    what makes "release-please owns CHANGELOG.md" actually enforceable
    on the local commit path.
    """
    config = _load_pre_commit_config()
    hook_ids = {
        hook.get("id")
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
    }
    assert "block-manual-changelog" in hook_ids, (
        "Missing pre-commit hook `block-manual-changelog`; CHANGELOG.md "
        "must be writable only by release-please-action in CI."
    )

    raw = _read(".pre-commit-config.yaml")
    # The hook only fires for CHANGELOG.md (release-please artifact).
    assert "^CHANGELOG\\.md$" in raw


def test_pre_commit_carries_no_retired_vault_hooks() -> None:
    """The repository's own hook config runs the canonical gates, nothing retired.

    A retired hook left here would keep rewriting the vault from inside a
    commit in this checkout even though no consumer install renders it.
    """
    from vaultspec_core.core.precommit import RETIRED_HOOK_IDS

    config = _load_pre_commit_config()
    hooks = [hook for repo in config.get("repos", []) for hook in repo.get("hooks", [])]
    ordered_ids = [hook.get("id") for hook in hooks]
    assert not RETIRED_HOOK_IDS & set(ordered_ids)
    assert ordered_ids.index("vault-fix") < ordered_ids.index("spec-check")


def _toolchain_targets(verb_name: str) -> set[str]:
    """Return the target names the dev toolchain declares for one verb."""
    from dev import toolchain

    verb = toolchain.find_verb(verb_name)
    assert verb is not None, f"dev/toolchain.py declares no `{verb_name}` verb"
    return {target.name for target in verb.targets}


def test_lint_covers_every_validation_surface() -> None:
    """The gating dimensions must all be reachable by name."""
    required = {
        "python",
        "type",
        "toml",
        "links",
        "markdown",
        "workflow",
        "complexity",
        "nesting",
        "size",
        "type-strict",
        "all",
    }
    missing = sorted(required - _toolchain_targets("lint"))
    assert not missing, f"lint verb is missing targets: {missing}"


def test_audit_covers_every_advisory_dimension() -> None:
    """Advisory dimensions are named individually so each can graduate to lint."""
    required = {
        "deps",
        "security",
        "dead-code",
        "dependencies",
        "advisory",
        "all",
    }
    missing = sorted(required - _toolchain_targets("audit"))
    assert not missing, f"audit verb is missing targets: {missing}"


def test_only_the_dependency_audit_gates() -> None:
    """`deps` is a verdict and gates; every other audit dimension is a lead.

    A check whose documented contract and actual exit code disagree is worse
    than no check, so the advisory flag is asserted rather than assumed.
    """
    from dev import toolchain

    audit = toolchain.find_verb("audit")
    assert audit is not None
    by_name = {target.name: target for target in audit.targets}
    assert not by_name["deps"].advisory, "the dependency audit must gate"
    for name in ("security", "dead-code", "dependencies"):
        assert by_name[name].advisory, f"audit target `{name}` must be advisory"


def test_health_report_is_measurement_only() -> None:
    """Every health target exits 0; it ranks offenders rather than gating."""
    from dev import toolchain

    health = toolchain.find_verb("health")
    assert health is not None
    assert {"report", "fast", "census"} <= {t.name for t in health.targets}
    for target in health.targets:
        assert target.advisory, (
            f"health target `{target.name}` must be advisory - the report is the "
            "measurement instrument, and the gates live in pyproject.toml"
        )


def test_fix_surface_covers_every_autofixable_target() -> None:
    required = {"python", "toml", "markdown", "vault", "all"}
    missing = sorted(required - _toolchain_targets("fix"))
    assert not missing, f"fix verb is missing targets: {missing}"


def test_bandit_excludes_every_nested_test_tree() -> None:
    """The security scan must not measure test code at any nesting depth.

    A path-shaped exclusion (`<pkg>/tests`) only covers the top-level test
    package and silently admitted `<pkg>/hooks/tests/` and its siblings, which
    is where the scan's only MEDIUM findings came from. The glob covers every
    depth.
    """
    from dev import toolchain
    from dev.runner import Cmd, ToolOrDocker

    audit = toolchain.find_verb("audit")
    assert audit is not None
    security = next(t for t in audit.targets if t.name == "security")
    step = security.steps[0]
    assert isinstance(step, (Cmd, ToolOrDocker))
    argv = step.argv
    assert "-x" in argv, "the bandit scan must carry an exclusion"
    assert argv[argv.index("-x") + 1] == "*/tests/*", (
        "the bandit exclusion must be a glob covering nested test trees"
    )


def _ty_pre_commit_paths() -> set[str]:
    """Return the path arguments the pre-commit ``ty`` hook checks.

    The hook's ``entry`` is a literal shell-style command line rather than
    structured data, so the paths are recovered by locating the ``check``
    token and taking every following word that is not a flag.
    """
    config = _load_pre_commit_config()
    hooks = [hook for repo in config.get("repos", []) for hook in repo.get("hooks", [])]
    ty_hook = next(hook for hook in hooks if hook.get("id") == "ty")
    tokens = ty_hook["entry"].split()
    check_index = tokens.index("check")
    return {token for token in tokens[check_index + 1 :] if not token.startswith("-")}


def _ty_toolchain_paths() -> set[str]:
    """Return the path arguments :mod:`dev.toolchain`'s ``type`` target checks.

    Mirrors :func:`_ty_pre_commit_paths` so both sides are derived from their
    real source rather than a literal expected list, per
    :func:`test_ty_pre_commit_scope_matches_dev_toolchain_scope`.
    """
    from dev import toolchain
    from dev.runner import Cmd

    lint = toolchain.find_verb("lint")
    assert lint is not None
    target = next(t for t in lint.targets if t.name == "type")
    step = target.steps[0]
    assert isinstance(step, Cmd)
    argv = step.argv
    check_index = argv.index("check")
    return {token for token in argv[check_index + 1 :] if not token.startswith("-")}


def test_ty_pre_commit_scope_matches_dev_toolchain_scope() -> None:
    """The pre-commit ``ty`` hook and ``just check-type`` must check the same trees.

    ``.pre-commit-config.yaml``'s ``ty`` hook hardcodes its own argv instead of
    delegating to :mod:`dev.toolchain`, so it is a second, independent source
    of truth for what "type checked" means. If one is widened without the
    other, pre-commit silently checks less than CI while both read as green.
    Both sides are derived from their real source here rather than compared
    against a literal path list, so this fails the moment either one drifts,
    in either direction, without needing an edit of its own when the covered
    trees change.
    """
    pre_commit_paths = _ty_pre_commit_paths()
    toolchain_paths = _ty_toolchain_paths()
    assert pre_commit_paths == toolchain_paths, (
        f"pre-commit `ty` hook checks {sorted(pre_commit_paths)} but "
        f"dev/toolchain.py's `type` target checks {sorted(toolchain_paths)} - "
        "widen both together."
    )


#: Seconds a test may spend on its OWN work, on top of the advisory-lock waits
#: the harness timer has to sit above. The slowest test in this suite runs
#: about 27 seconds, so this is generous on purpose: the number it pads is a
#: worst case that only contention reaches, and being wrong in this direction
#: costs a slower report on a genuinely hung test, while being wrong in the
#: other direction costs the diagnostic entirely.
_TEST_WORK_ALLOWANCE_SECONDS = 120.0

#: Advisory-lock acquisitions one test may make in sequence. Two, because a
#: test that takes a second lock while holding contention on the first is the
#: shape that exhausted the old margin.
_SEQUENTIAL_LOCK_ACQUISITIONS = 2


def test_the_test_timeout_sits_above_the_advisory_lock_budget() -> None:
    """pytest's timer must not pre-empt ``AdvisoryLockTimeoutError``.

    ``advisory_lock`` bounds a single acquisition at
    ``lock_timeout_seconds`` and then raises an error that names the sentinel,
    the budget and the layer that gave up. That error is the designed
    diagnostic for contention, and it is only ever seen if the harness lets it
    happen.

    It did not. At ``timeout = 300`` against a 120-second budget, one exhausted
    acquisition left 180 seconds and two left none, so a contended test died on
    a pytest stack dump naming whatever syscall the sampler caught rather than
    on the error built to explain it. The dump that prompted this guard pointed
    at ``os.open`` inside ``_open_atomic_temp`` and read as a deadlock in the
    atomic-write path, which it was not.

    Both numbers live in different files and neither knows about the other, so
    the relationship is asserted rather than assumed.
    """
    from vaultspec_core.config import VaultSpecConfig

    pyproject = tomllib.loads(_read("pyproject.toml"))
    options = pyproject["tool"]["pytest"]["ini_options"]
    harness_timeout = float(options["timeout"])
    budget = VaultSpecConfig().lock_timeout_seconds

    required = _SEQUENTIAL_LOCK_ACQUISITIONS * budget + _TEST_WORK_ALLOWANCE_SECONDS
    assert harness_timeout >= required, (
        f"pytest's `timeout` is {harness_timeout:g}s but the advisory-lock "
        f"budget is {budget:g}s, so {_SEQUENTIAL_LOCK_ACQUISITIONS} contended "
        f"acquisitions plus {_TEST_WORK_ALLOWANCE_SECONDS:g}s of the test's own "
        f"work need {required:g}s. Below that, contention surfaces as a pytest "
        "stack dump instead of AdvisoryLockTimeoutError, and the dump names a "
        "syscall rather than the lock. Raise `timeout` in pyproject.toml, or "
        "lower `lock_timeout_seconds`."
    )

    assert options.get("timeout_func_only") is False, (
        "`timeout_func_only` must stay false: fixture setup and teardown need "
        "the same bounded failure reporting as the test call"
    )


def test_the_running_interpreter_matches_the_pin() -> None:
    """The interpreter this suite runs on is the one ``.python-version`` pins.

    ``.python-version`` is the single interpreter pin: every CI job resolves
    its Python from that file and ``requires-python`` bounds the same range.
    Nothing enforced that the interpreter actually RESOLVED matched it, and a
    setup step silently falling back to a different minor would leave the
    declared pin and the tested interpreter disagreeing - the drift that
    invalidated venvs across this estate when a host OS upgrade moved the
    system interpreter.

    This was a CI job of its own, which meant it answered the question about a
    runner rather than about a test run, and only on the one platform that job
    ran on. Asserted here it holds wherever the suite executes - every CI lane,
    both operating systems, and a contributor's laptop - and costs no job.
    """
    pinned = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert pinned == actual, (
        f".python-version pins {pinned} but this suite is running on {actual}. "
        "The declared pin is not what is being tested."
    )


def test_ci_workflow_calls_just_for_quality_gates() -> None:
    gate = _load_workflow(".github/workflows/merge-gate.yml")
    jobs = gate["jobs"]
    required_jobs = {"lint", "test-linux", "test-windows", "gate"}
    assert set(jobs) == required_jobs, "the merge gate must contain exactly four jobs"

    expected_runs = {
        # The four dimensions below `markdown` are pinned for the same reason
        # the test lanes are: each graduated from advisory to gating only once
        # its burndown reached zero, and an ungated promotion is one deletion
        # away from being silently undone. `type-strict` in particular was
        # promoted by removing its `continue-on-error` key; nothing but this
        # list stops the step itself from being removed next.
        # The lint tier runs on every push. Each check is pinned so folding it
        # into a tier cannot become dropping it.
        "lint": {
            "just init",
            "just deps-check",
            "just check-workflow",
            "just check-python",
            # `just check-type` is deliberately absent. `check-type-platforms`
            # runs `--python-platform` linux, darwin and win32; this runner's
            # host platform is Linux, so naming both ran the Linux pass twice.
            "just check-type-platforms",
            "just check-toml",
            "just check-markdown",
        },
        "test-linux": {
            "just init",
            "just check-links",
            "just check-complexity",
            "just check-nesting",
            "just check-size",
            "just check-type-strict",
            "just test-harness",
            "just test-repo",
            "just test-broad",
            "just framework-install",
            "just vault-check",
            "just audit-deps",
        },
        "test-windows": {"just init", "just test-broad"},
    }

    for job_name, expected in expected_runs.items():
        steps = jobs[job_name]["steps"]
        run_commands = {step["run"] for step in steps if "run" in step}
        missing = [cmd for cmd in sorted(expected) if cmd not in run_commands]
        assert not missing, f"Job {job_name} missing just commands: {missing}"

        # `just init` is the ONE provisioning entry point, so a second
        # provisioning command beside it is the defect rather than a
        # belt-and-braces addition: two definitions of "the environment this
        # job needs" drift, and the one that drifts is the one nobody reads.
        # This job previously ran `just deps-sync`, which provisioned less
        # than `init` does and less than the gates below it assume.
        # Named MUTATING recipes rather than the `just deps-` prefix. The
        # prefix also caught `deps-check`, which resolves nothing and installs
        # nothing - it only reports whether the lockfile agrees with
        # pyproject.toml - so the rule that exists to stop a second definition
        # of "the environment this job needs" was also barring the read-only
        # question about it.
        mutating_deps = {
            "just deps-sync",
            "just deps-upgrade",
            "just deps-lock",
            "just deps-lock-upgrade",
        }
        provisioning = {
            command
            for command in run_commands
            if command.split()[0] in {"uv", "npm", "pip", "pipx"}
            or command in mutating_deps
        }
        assert not provisioning, (
            f"Job {job_name} provisions outside `just init`: {sorted(provisioning)}"
        )


def test_ci_workflow_lints_workflows_through_the_pinned_recipe() -> None:
    """Workflow linting is dispatched by recipe, and the pin lives in `dev/`.

    This has now been wrong in three different ways, and each rewrite of this
    guard records the one it closed.

    It first asserted `docker://rhysd/actionlint:`, which made a required check
    depend on the runner account reaching the docker socket. On the
    self-hosted fleet it cannot, and the job failed in `Pull down action image`
    having linted nothing.

    It then asserted a hand-written download step here in the workflow, pinned
    by version and by digest. That was right about the property and wrong
    about the location: the digest named `linux_amd64` unconditionally, so on
    the ARM64 cell it PASSED - the file really is the amd64 archive the digest
    names - and died at `Exec format error` one line later. A verification that
    reports success while handing back an unusable binary is worse than none.

    What holds now: the job calls `just check-workflow`, and the pin lives in
    `dev/actionlint.py` where a developer runs the same gate before pushing.
    So this asserts the DISPATCH here and the PIN there, and forbids the two
    acquisition routes that have already failed - plus a third that would:
    `taiki-e/install-action` is the fleet's `just` installer, but actionlint is
    a Go binary and that action falls back to cargo-binstall for it, which is a
    different tool arriving under the same name.
    """
    gate = _load_workflow(".github/workflows/merge-gate.yml")
    # The gate is a step of the lint tier, which every push runs. What this
    # guard holds is unchanged: dispatch stays behind the recipe and the pin
    # stays in ``dev/``.
    steps = gate["jobs"]["lint"]["steps"]

    run_commands = {step["run"].strip() for step in steps if "run" in step}
    assert "just check-workflow" in run_commands, (
        "workflow linting must dispatch through the recipe; a gate re-listed "
        f"in YAML cannot be proven to match the gate. Runs: {sorted(run_commands)}"
    )
    assert not any(command.startswith("actionlint") for command in run_commands), (
        "actionlint is invoked BY the recipe, not beside it - a second caller "
        "is a second set of flags, and the flags are what the gate checks"
    )

    used_actions = {step.get("uses", "") for step in steps}
    assert not any(action.startswith("docker://") for action in used_actions), (
        "a container action reintroduces the docker-socket dependency that "
        "this gate cannot satisfy on the self-hosted fleet"
    )
    assert not any("actionlint" in action for action in used_actions), (
        "actionlint must not arrive from a marketplace action: the fleet's "
        "installer action falls back to cargo-binstall for a Go binary, which "
        "silently substitutes a different tool"
    )

    # The pin, at its new home. Per ARCHITECTURE, because a single digest is
    # what let an amd64 archive pass its own check on an ARM runner.
    from dev import actionlint

    assert _ACTIONLINT_VERSION.fullmatch(actionlint.VERSION), (
        "actionlint must be pinned to a concrete release version"
    )
    assert actionlint.ARCHIVES, "actionlint must pin at least one platform"
    # The architecture token upstream uses, per machine this fleet runs on.
    # Named here rather than derived from the entry being checked: deriving it
    # from `suffix` would make the assertion agree with whatever the table
    # says, which is how a guard passes over the defect it exists to catch.
    upstream_arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    for (system, machine), (suffix, digest) in actionlint.ARCHIVES.items():
        assert system in suffix, (
            f"the {system}/{machine} entry names archive {suffix!r}, which is "
            "not that operating system's"
        )
        expected_arch = upstream_arch.get(machine)
        assert expected_arch is not None, (
            f"{machine} has no known upstream architecture token; add it here "
            "rather than letting the entry go unchecked"
        )
        assert f"_{expected_arch}" in suffix, (
            f"the {system}/{machine} entry names archive {suffix!r}, which is "
            "a different architecture's. This is the amd64-on-ARM failure "
            "exactly: the digest matches, so the download PASSES, and the "
            "binary dies at `Exec format error` one line later"
        )
        assert len(digest) == _SHA256_HEX_LENGTH, (
            f"the {system}/{machine} archive must be pinned by content as well "
            "as by version, so a retagged release fails the gate rather than "
            "quietly changing what lints these workflows"
        )


def test_ci_workflow_installs_native_lint_tools() -> None:
    gate = _load_workflow(".github/workflows/merge-gate.yml")
    jobs = gate["jobs"]
    steps = jobs["lint"]["steps"] + jobs["test-linux"]["steps"]
    used_actions = {step["uses"] for step in steps if "uses" in step}
    assert any(action.startswith("taiki-e/install-action@") for action in used_actions)
    assert all(
        "@" in action and len(action.split("@", 1)[1]) == 40 for action in used_actions
    ), "every action must be pinned by commit, not by a movable tag"
    # Node.js is no longer required - taplo and pymarkdown are native
    assert "actions/setup-node@v4" not in used_actions


def test_quality_gate_thresholds_are_declared_not_reimplemented() -> None:
    """Every ratcheted threshold lives in pyproject.toml, not in the harness.

    The harness composes the gates by invoking their tools; the moment it
    carries a threshold of its own, the reported number and the enforced
    number can drift apart. This pins each baseline-calibrated dimension to
    its declaration site.
    """
    pyproject = _read("pyproject.toml")
    for table in (
        "[tool.complexipy]",
        "[tool.pylint.format]",
        "[tool.pylint.design]",
        "[tool.ruff.lint.mccabe]",
        "[tool.ruff.lint.pylint]",
        "[tool.vulture]",
        "[tool.bandit]",
        "[tool.deptry]",
        "[tool.basedpyright]",
    ):
        assert table in pyproject, f"missing gate declaration {table}"

    toolchain = _read("dev/toolchain.py")
    for threshold_flag in (
        "--max-complexity-allowed",
        "--max-module-lines",
        "--max-attributes",
        "--min-confidence",
    ):
        assert threshold_flag not in toolchain, (
            f"{threshold_flag} must be declared in pyproject.toml, not passed "
            "on the command line where it can drift from the gate"
        )


def test_test_tree_exclusion_patterns_match_windows_paths() -> None:
    """Ignore patterns must be TOML literal strings, not basic strings.

    As a basic string, `".*[\\\\/]tests[\\\\/].*"` decodes to the regex
    `.*[\\/]tests[\\/].*`, whose character class contains only a forward slash
    - the backslash reads as an escape of `/` rather than a class member. The
    pattern then never matches a Windows path and the test tree silently
    enters the gate it was meant to leave. Both sibling repositories carry
    this defect; the literal-string form is the fix.
    """
    pyproject = _read("pyproject.toml")
    assert "ignore-paths = ['.*[\\\\/]tests[\\\\/].*']" in pyproject
    assert "extend_exclude = ['.*[\\\\/]tests[\\\\/].*']" in pyproject
    assert '".*[\\\\/]tests[\\\\/].*"' not in pyproject, (
        "a basic-string ignore pattern never matches a Windows path"
    )


def _pytest_addopts() -> str:
    """Return ``[tool.pytest.ini_options].addopts`` from ``pyproject.toml``."""
    raw = tomllib.loads(_read("pyproject.toml"))
    return cast("str", raw["tool"]["pytest"]["ini_options"]["addopts"])


def test_pytest_addopts_deselects_every_credential_or_network_marker() -> None:
    """A bare ``pytest`` invocation must gate the same markers `just test` does.

    `dev.toolchain.EXCLUDED_MARKERS` is what every `just test` lane passes
    explicitly via `-m`, so those invocations never depend on `addopts` at
    all - a later `-m` on the command line simply replaces an earlier one
    from `addopts`, it does not combine with it. A bare `pytest` invocation
    (a contributor's shell, an editor's test runner, CI calling the binary
    directly) has no such explicit `-m` and falls through to `addopts`
    alone, so `addopts` is the ONLY gate for that path. Letting it drift
    from `EXCLUDED_MARKERS` is exactly how `@pytest.mark.gemini` stopped
    being an opt-in gate: the marker was registered and documented as
    excluding the test, while nothing in `addopts` actually deselected it.
    """
    from dev import toolchain

    addopts = _pytest_addopts()
    assert f"not benchmark and {toolchain.EXCLUDED_MARKERS}" in addopts, (
        f"pyproject.toml addopts {addopts!r} has drifted from "
        f"dev.toolchain.EXCLUDED_MARKERS {toolchain.EXCLUDED_MARKERS!r}; a "
        "bare `pytest` invocation would stop deselecting a credential- or "
        "network-gated marker"
    )


def test_provider_capability_enum_covers_all_tools(tmp_path: Path) -> None:
    """Every Tool enum member must have a ToolConfig with non-empty capabilities."""
    from vaultspec_core.core.enums import Tool
    from vaultspec_core.core.types import init_paths

    (tmp_path / ".vaultspec").mkdir()
    ctx = init_paths(tmp_path)

    for tool in Tool:
        cfg = ctx.tool_configs.get(tool)
        assert cfg is not None, f"Tool {tool.value} has no ToolConfig"
        assert cfg.capabilities, f"Tool {tool.value} has empty capabilities"


def test_provider_capability_consistency(tmp_path: Path) -> None:
    """Capability declarations must be consistent with ToolConfig fields."""
    from vaultspec_core.core.enums import ProviderCapability, Tool
    from vaultspec_core.core.types import init_paths

    (tmp_path / ".vaultspec").mkdir()
    ctx = init_paths(tmp_path)

    for tool in Tool:
        cfg = ctx.tool_configs.get(tool)
        if cfg is None:
            continue
        caps = cfg.capabilities
        if ProviderCapability.RULES in caps:
            assert cfg.rules_dir is not None or cfg.native_config_file is not None, (
                f"{tool.value} declares RULES but has no rules_dir"
                " or native_config_file"
            )
        if ProviderCapability.SKILLS in caps:
            assert cfg.skills_dir is not None, (
                f"{tool.value} declares SKILLS but has no skills_dir"
            )
        if ProviderCapability.ROOT_CONFIG in caps:
            assert cfg.config_file is not None, (
                f"{tool.value} declares ROOT_CONFIG but has no config_file"
            )
        if ProviderCapability.WORKFLOWS in caps:
            assert cfg.workflows_dir is not None, (
                f"{tool.value} declares WORKFLOWS but has no workflows_dir"
            )


def test_every_capability_has_at_least_one_provider(tmp_path: Path) -> None:
    """Each ProviderCapability value must map to at least one provider."""
    from vaultspec_core.core.enums import ProviderCapability, Tool
    from vaultspec_core.core.types import init_paths

    (tmp_path / ".vaultspec").mkdir()
    ctx = init_paths(tmp_path)

    for cap in ProviderCapability:
        providers = [
            tool.value
            for tool in Tool
            if (cfg := ctx.tool_configs.get(tool)) is not None
            and cap in cfg.capabilities
        ]
        assert providers, f"ProviderCapability.{cap.name} has no providers"


def test_basedpyright_private_usage_exemption_covers_every_tests_directory() -> None:
    """Every co-located ``tests/`` tree needs its own privacy-exemption entry.

    ``executionEnvironments[].root`` matches by directory PREFIX only, so this
    list cannot be collapsed. A glob root such as ``src/vaultspec_core/**/tests``
    is accepted, matches nothing, and reports no error - a silent no-op that
    looks identical to success. A per-directory ``pyrightconfig.json`` is never
    discovered either, because one config is resolved per invocation. A
    file-header ``# pyright: reportPrivateUsage=false`` does work, but needs one
    per file and scatters suppressions through tracked test source, which is
    what this project's ban on inline ``# pyright: ignore`` exists to prevent.

    Each tree therefore needs a literal entry. Without this guard, a new
    co-located suite would instead fail the GATE with a ``reportPrivateUsage``
    error, inviting the one fix the exemption's own comment warns against -
    making the internals public. This makes the omission loud and
    self-explaining instead.
    """
    environments = _load_basedpyright_config()["executionEnvironments"]
    exempted = {
        root
        for env in environments
        if (root := env.get("root")) is not None
        and env.get("reportPrivateUsage") is False
    }

    missing = sorted(_colocated_test_dirs() - exempted)

    assert not missing, (
        "these co-located test directories have no reportPrivateUsage "
        f"exemption in pyproject.toml: {missing}. `root` matches by directory "
        "prefix only - no glob - so each needs its own "
        "[[tool.basedpyright.executionEnvironments]] entry."
    )


def _workflow_paths() -> list[Path]:
    """Every workflow file, proven to exist before anything reads them."""
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflow files found under .github/workflows"
    return workflows


def test_workflow_run_blocks_fit_actionlint_shellcheck_pipe() -> None:
    """Actionlint must be able to hand every Bash block to ShellCheck.

    Actionlint 1.7.12 writes a script to its child-process stdin pipe before it
    starts ShellCheck. Windows pipes are small enough that a roughly 4 KiB
    block fills the pipe and deadlocks actionlint forever. Keep explanatory
    prose as YAML comments outside ``run`` blocks so the native gate completes
    on every supported development platform without dropping ShellCheck.
    """
    limit = 4_000
    oversized: list[str] = []
    for path in _workflow_paths():
        workflow = cast("_Workflow", yaml.safe_load(path.read_text(encoding="utf-8")))
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []) or []:
                script = step.get("run")
                if isinstance(script, str) and len(script.encode("utf-8")) > limit:
                    oversized.append(
                        f"{path.name}:{job_name}:{step.get('name')} "
                        f"({len(script.encode('utf-8'))} bytes)"
                    )

    assert not oversized, (
        f"workflow run blocks exceed actionlint's {limit}-byte cross-platform "
        f"ShellCheck limit: {oversized}"
    )


def _guard_module_texts() -> list[tuple[str, str]]:
    """Every guard module under ``dev/guards/`` as ``(relative path, text)``."""
    modules = sorted((ROOT / "dev" / "guards").rglob("test_*.py"))
    assert modules, "no guard modules found under dev/guards"
    return [
        (path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))
        for path in modules
    ]


#: The marker the pre-commit hook selects with, and the flag that selects it.
_PRECOMMIT_MARKER = "precommit"
_MARKER_SELECTOR = f"-m {_PRECOMMIT_MARKER}"


def _precommit_hook_entries() -> list[str]:
    """Every ``entry:`` line declared by a local hook in the pre-commit config."""
    config = cast(
        "_PreCommitConfig",
        yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")),
    )
    return [
        hook["entry"]
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if "entry" in hook
    ]


def test_the_markdown_guards_run_before_a_commit_not_only_in_ci() -> None:
    """The bare-reference guard must be reachable without pushing.

    It was CI-only until 2026-09-05, so ``vault check`` - a snippet naming a
    command group that is not an executable - landed in README.md on
    2026-09-02 and main stayed red for two days. The guard itself costs 0.02s
    and reads markdown; only its siblings in the same file are slow, because
    they shell out to ``--help`` for every command.

    Asserted against the config rather than against behaviour because the
    failure is silent: a deleted hook removes local coverage and breaks
    nothing that any test would otherwise notice.
    """
    entries = _precommit_hook_entries()

    assert any(_MARKER_SELECTOR in entry for entry in entries), (
        f"no pre-commit hook selects '{_MARKER_SELECTOR}', so the markdown "
        "guards run only after a push"
    )


def test_the_precommit_marker_selects_something() -> None:
    """A marker nothing carries selects nothing, and the hook stops guarding.

    pytest exits 5 on an empty selection, so the hook would fail rather than
    pass quietly - but it would fail on every markdown commit for a reason
    that reads like tooling breakage. Naming the cause here is cheaper.
    """
    marked = [
        rel
        for rel, text in _guard_module_texts()
        if f"@pytest.mark.{_PRECOMMIT_MARKER}" in text
    ]

    assert marked, (
        f"no test in dev/guards carries @pytest.mark.{_PRECOMMIT_MARKER}, so "
        "the pre-commit hook selects an empty set"
    )


def test_the_precommit_marker_never_becomes_the_ci_selection() -> None:
    """CI must keep running the whole file, marker or no marker.

    The hook is an accelerator: it runs the cheap subset early. The moment CI
    selects the same subset, the expensive guards - the ones that compare
    documentation against live ``--help`` output - stop running anywhere, and
    the marker silently converts from a speed-up into a coverage cut.
    """
    offenders: list[str] = []
    for path in _workflow_paths():
        workflow = cast("_Workflow", yaml.safe_load(path.read_text(encoding="utf-8")))
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []) or []:
                if _MARKER_SELECTOR in str(step.get("run", "")):
                    offenders.append(f"{path.name}:{job_name}:{step.get('name')}")

    assert not offenders, (
        f"these CI steps select '{_MARKER_SELECTOR}', which would leave the "
        f"guards outside that marker running nowhere: {offenders}"
    )


def test_every_gating_dimension_is_declared_as_a_gate() -> None:
    """The `lint` verb is gates end to end, and each says so structurally.

    `quiet_on_pass` withholds a tool's success output, so the question of which
    targets may do it has to be answered by a rule rather than per target. The
    rule is the one in `EXIT-CODES.md`: `check-*` is READ-ONLY, so a clean pass
    has nothing to report and everything it prints is narration. Declaring the
    whole verb through `gate` keeps a new dimension quiet because of what it
    is, rather than because someone remembered a flag.
    """
    from dev import toolchain

    lint = toolchain.find_verb("lint")
    assert lint is not None
    loud = [target.name for target in lint.targets if not target.quiet_on_pass]
    assert not loud, (
        f"lint targets not declared through `gate`: {loud} - a read-only gate's "
        "success output is narration, and the harness reports the verdict itself"
    )


def test_no_mutating_or_reporting_target_is_quiet() -> None:
    """Suppression is confined to read-only inspection.

    Everywhere else the tool's output IS the product - what a fix changed,
    which tests ran and which skipped, the ranked offenders an audit found -
    and withholding it would replace the answer with a claim that there was
    one. `advisory` is a separate axis: an advisory target's findings do not
    gate, which is no reason not to print them.
    """
    from dev import toolchain

    for verb_name in ("fix", "test", "build", "audit", "health", "docs"):
        verb = toolchain.find_verb(verb_name)
        assert verb is not None, f"no `{verb_name}` verb"
        quiet = [target.name for target in verb.targets if target.quiet_on_pass]
        assert not quiet, (
            f"`{verb_name}` targets declared quiet: {quiet} - these report a "
            "product rather than a verdict, so their output is the answer"
        )


def test_the_harness_reports_every_status_the_contract_names() -> None:
    """Each exit code reaches the reader as its own word.

    The display is the other half of the exit-code contract, and the half a
    human reads. A status that arrives as silence - which is what `EMPTY`,
    `BROKEN` and `MISSING` all used to be at a terminal - is indistinguishable
    from the clean pass none of them is.
    """
    from dev import exit_codes, reporting

    named = {
        value
        for name, value in vars(exit_codes).items()
        if name.isupper() and isinstance(value, int) and not name.endswith("_ENV")
    }
    unworded = sorted(
        code
        for code in named
        if code not in reporting.STATUS_WORDS
        and code != exit_codes.PYTEST_NO_TESTS_COLLECTED
    )
    assert not unworded, (
        f"exit codes with no word in dev/reporting.py: {unworded} - a status "
        "the reader cannot name is one they cannot act on"
    )


def test_every_test_lane_reports_the_population_it_ran() -> None:
    """No pytest step may report a verdict without saying how many tests earned it.

    A lane's exit code cannot carry its population, so a marker expression
    narrowed by a typo or a path that no longer reaches its tests runs, passes,
    and reads exactly like the full suite. `toolchain.lane` is what attaches
    the record the count is read from; a step that calls pytest directly would
    be a lane with a verdict and no population behind it.
    """
    from dev import testing, toolchain
    from dev.runner import Cmd

    verb = toolchain.find_verb("test")
    assert verb is not None
    unrecorded = [
        (target.name, step.argv)
        for target in verb.targets
        for step in target.steps
        if isinstance(step, Cmd)
        and "pytest" in step.argv
        and testing.declared_report(step.argv) is None
    ]
    assert not unrecorded, (
        f"test steps not declared through `lane`: {unrecorded} - a lane that "
        "records nothing cannot report the population its verdict covers"
    )


def test_every_test_lane_records_to_its_own_file() -> None:
    """Two lanes never share a record.

    `unit` and `broad` each run two passes over disjoint populations. Pointed
    at one file, the second pass overwrites the first and the target reports
    half of what it ran as though that were all of it.
    """
    from dev import testing, toolchain
    from dev.runner import Cmd

    verb = toolchain.find_verb("test")
    assert verb is not None
    for target in verb.targets:
        reports = [
            testing.declared_report(step.argv)
            for step in target.steps
            if isinstance(step, Cmd)
        ]
        named = [report for report in reports if report is not None]
        assert len(set(named)) == len(named), (
            f"`test {target.name}` points two lanes at one record: {named}"
        )


def test_the_harness_carries_no_second_duration_reporter() -> None:
    """One instrument per question, and the harness owns this one.

    Two standing duration reporters used to print on every lane of every run -
    four blocks from `pytest-durations` and one from `--durations` - and both
    printed their headers whether or not anything was slow. The harness reads
    each test's time from the record it already collects and names the outlier
    only when there is one.
    """
    pyproject = _read("pyproject.toml")

    assert "pytest-durations" not in pyproject, (
        "pytest-durations duplicates the slow-test signal in dev/testing.py"
    )
    assert "--durations" not in pyproject, (
        "a standing --durations prints its header even when nothing is slow; "
        "type it on a specific run instead"
    )


def test_release_please_is_the_single_release_authority() -> None:
    """A release creates exactly one proof, one publish run and one build run.

    release-please dispatches release.yml once it creates the immutable tag;
    release.yml proves the tagged tree with the merge gate and only then
    dispatches the binaries build, which dispatches the publication in turn. If
    a consumer also listened for the tag push, the same release could race an
    unproven run through publication.
    """
    for name in ("release.yml", "publish.yml", "binaries.yml"):
        workflow = cast(
            "dict[str, object]",
            yaml.load(_read(f".github/workflows/{name}"), Loader=yaml.BaseLoader),
        )
        triggers = cast("dict[str, object]", workflow["on"])
        assert set(triggers) == {"workflow_dispatch"}, (
            f"{name} must be dispatch-only; release-please owns release "
            f"initiation, but it also declares {sorted(triggers)}"
        )
        dispatch = cast("dict[str, object]", triggers["workflow_dispatch"])
        inputs = cast("dict[str, object]", dispatch["inputs"])
        tag = cast("dict[str, str]", inputs["tag"])
        assert tag.get("required") == "true", (
            f"{name} must require the immutable release tag"
        )

    authority = _read(".github/workflows/release-please.yml")
    assert "gh workflow run release.yml" in authority, (
        "release-please no longer dispatches the release workflow"
    )
    assert '-f "tag=${TAG}"' in authority, (
        "the release workflow must receive release-please's immutable tag"
    )
    for consumer in ("publish.yml", "binaries.yml"):
        assert consumer not in authority, (
            f"release-please dispatches {consumer} directly, skipping the "
            "release workflow's merge gate"
        )


def test_the_release_is_proven_before_anything_is_published() -> None:
    """The consumers are dispatched only after the merge gate passed the tag."""
    release = cast(
        "dict[str, dict[str, dict[str, object]]]",
        yaml.safe_load(_read(".github/workflows/release.yml")),
    )
    jobs = release["jobs"]
    assert jobs["health"]["uses"] == "./.github/workflows/merge-gate.yml"
    health_inputs = cast("dict[str, str]", jobs["health"]["with"])
    assert health_inputs["ref"] == "${{ inputs.tag }}", (
        "the release gate must prove the tag, not the dispatch ref"
    )

    dispatch = jobs["dispatch"]
    assert dispatch["needs"] == "health", "the consumers must wait on the release gate"
    assert "if" not in dispatch, (
        "a condition on the dispatch job would override the default success "
        "check and let a failed gate publish"
    )
    runs = " ".join(
        str(step.get("run", ""))
        for step in cast("list[dict[str, object]]", dispatch["steps"])
    )
    assert "gh workflow run binaries.yml" in runs, (
        "the release workflow no longer dispatches the binaries build"
    )
    assert "gh workflow run publish.yml" not in runs, (
        "the release workflow dispatches the publication beside the binaries "
        "build again. PyPI cannot be unpublished, so a version reaches the "
        "index while the build that justifies it can still fail - which is how "
        "a release can exist on PyPI with no binaries behind it. The binaries "
        "lane dispatches the publication once every declared target is proven"
    )


def _job_bodies(workflow: str) -> str:
    """Return a workflow's job definitions as text, for credential greps."""
    parsed = cast("dict[str, object]", yaml.safe_load(workflow))
    return yaml.safe_dump(parsed.get("jobs"))


def test_the_release_is_held_as_a_draft_until_the_lane_publishes_it() -> None:
    """release-please must create the release unpublished, and its tag anyway.

    A published release cannot be filled in afterwards once immutable releases
    are on, so the release object is created as a draft and published by the
    lane that has proved it. `force-tag-creation` is the other half: GitHub
    does not create a git tag for a draft release, and every job in the lane
    checks out the tag for its source, so without it the build has no ref.
    """
    config = cast(
        "dict[str, dict[str, dict[str, object]]]",
        json.loads(_read("release-please-config.json")),
    )
    package = config["packages"]["."]
    assert package.get("draft") is True, (
        "release-please must create the release as a draft; a published "
        "release cannot receive the assets that justify it"
    )
    assert package.get("force-tag-creation") is True, (
        "a draft release creates no git tag, and the whole lane builds from "
        "the tag - release-please must force it into existence"
    )


def test_pypi_is_published_only_once_every_binary_is_proven() -> None:
    """The publication is dispatched from the gate that judged the assets.

    PyPI is the one irreversible step in the release: a version number is spent
    the moment it lands on the index, and no re-dispatch takes it back. So it
    is dispatched last, by the gate that has already found every declared
    target attached and verified - not beside the build that produces them.
    """
    binaries = cast(
        "dict[str, dict[str, dict[str, object]]]",
        yaml.safe_load(_read(".github/workflows/binaries.yml")),
    )
    gate = binaries["jobs"]["verify-release-assets"]
    steps = cast("list[dict[str, object]]", gate["steps"])
    dispatching = [
        step
        for step in steps
        if "gh workflow run publish.yml" in str(step.get("run", ""))
    ]
    assert len(dispatching) == 1, (
        "exactly one step in the release-proven gate must dispatch the "
        f"publication; found {len(dispatching)}"
    )
    assert dispatching[0].get("if") == "${{ success() }}", (
        "the publication dispatch must be conditioned on the gate succeeding, "
        "or an incomplete release publishes to PyPI anyway"
    )


def test_the_release_is_published_last_and_only_once() -> None:
    """One step takes the release out of draft, after everything that fills it.

    The release is created unpublished and every lane attaches to that draft,
    so the flip to published is the statement that the release is complete. It
    belongs at the end of the publication lane - the last thing to attach is
    the distribution - and nowhere else.
    """
    publish = cast(
        "dict[str, dict[str, dict[str, object]]]",
        yaml.safe_load(_read(".github/workflows/publish.yml")),
    )
    steps = cast("list[dict[str, object]]", publish["jobs"]["publish-pypi"]["steps"])
    names = [str(step.get("name", "")) for step in steps]
    runs = [str(step.get("run", "")) for step in steps]

    publishing = [i for i, run in enumerate(runs) if "--draft=false" in run]
    assert len(publishing) == 1, (
        f"exactly one step must publish the release; found {len(publishing)}"
    )

    attaching = next(i for i, run in enumerate(runs) if "gh release upload" in run)
    assert attaching < publishing[0], (
        "the distribution is attached after the release is published, which "
        "immutable releases forbid outright"
    )

    pypi = next(i for i, run in enumerate(runs) if "uv publish" in run)
    assert pypi < publishing[0], (
        "the release is published before PyPI. Both steps are one-way, but a "
        "failed upload should leave an unpublished draft rather than a release "
        "advertising a version the index does not carry"
    )

    acquisition = next(
        i for i, run in enumerate(runs) if "gh workflow run acquisition.yml" in run
    )
    assert acquisition > publishing[0], (
        f"the acquisition check ({names[acquisition]}) is asked to acquire a "
        "release that is still a draft; it acquires unauthenticated and cannot "
        "see one"
    )


def test_the_channel_pointers_are_written_only_after_publication() -> None:
    """Nothing advertises a release before the release exists.

    A Scoop manifest and a Homebrew formula address assets by release download
    URL, so they are an advertisement rather than a part of the release. The
    binaries lane used to write them, which was correct only while the release
    was published before anything was attached to it - and stopped being
    correct when publication moved to the end of the lane.
    """
    binaries = _read(".github/workflows/binaries.yml")
    assert "dev.packaging.generate" not in binaries, (
        "the binaries lane generates channel pointers again. It runs before "
        "the release is published, so the pointers would address URLs that "
        "serve nothing until the publication lane finishes"
    )
    assert "CHANNEL_ROOT_DEPLOY_KEY" not in _job_bodies(binaries), (
        "the binaries lane can push to the channel root again"
    )

    channels = cast(
        "dict[str, dict[str, dict[str, object]]]",
        yaml.safe_load(_read(".github/workflows/channels.yml")),
    )
    steps = cast("list[dict[str, object]]", channels["jobs"]["channels"]["steps"])
    runs = [str(step.get("run", "")) for step in steps]

    refusing = next(
        (i for i, run in enumerate(runs) if "isDraft" in run),
        None,
    )
    assert refusing is not None, (
        "the channels lane does not check whether the release is published. It "
        "is dispatched by another workflow, so the one mistake that "
        "reintroduces this defect is a dispatch aimed at a draft"
    )
    writing = next(i for i, run in enumerate(runs) if "dev.packaging.generate" in run)
    assert refusing < writing, (
        "the channels lane generates pointers before checking that the release "
        "is published"
    )

    publish = cast(
        "dict[str, dict[str, dict[str, object]]]",
        yaml.safe_load(_read(".github/workflows/publish.yml")),
    )
    publish_runs = [
        str(step.get("run", ""))
        for step in cast(
            "list[dict[str, object]]", publish["jobs"]["publish-pypi"]["steps"]
        )
    ]
    published = next(i for i, run in enumerate(publish_runs) if "--draft=false" in run)
    dispatched = next(
        i for i, run in enumerate(publish_runs) if "gh workflow run channels.yml" in run
    )
    assert dispatched > published, (
        "the channels lane is dispatched before the release is published"
    )


def test_an_incomplete_release_is_never_edited_into_shape() -> None:
    """No lane demotes, promotes, or holds a release with the prerelease flag.

    That machinery existed because the release was published before its assets
    and had to be walked back. A draft cannot reach those states, so the
    mechanism has no domain left - and a dormant recovery path is
    indistinguishable from a working one until the day it is needed.
    """
    for name in ("binaries.yml", "publish.yml", "release.yml"):
        source = _read(f".github/workflows/{name}")
        assert "--prerelease" not in source, (
            f"{name} still edits a release's prerelease flag. The release is "
            "held as a draft now; holding it out of `latest` as well publishes "
            "it as a prerelease, because nothing promotes it back any more"
        )
