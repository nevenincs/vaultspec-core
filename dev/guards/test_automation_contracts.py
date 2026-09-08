"""Contracts binding the repository's automation surfaces to each other.

The failures guarded here are the ones no single tool reports: a CI job that
stops invoking the gate it claims to run, a ``justfile`` recipe that grows
shell logic the declarative registry was meant to own, a threshold that drifts
away from its declaration site, or two independent type-check invocations that
quietly stop covering the same trees.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path
from typing import TypedDict, cast, get_args

import pytest
import yaml

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]

#: A sentinel step condition of the form ``outputs.state == 'healthy'``.
_SENTINEL_STATE_CONDITION = re.compile(
    r"steps\.judge\.outputs\.state\s*[=!]=\s*'(?P<state>[a-z-]+)'"
)


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
        if path.is_dir() and "__pycache__" not in path.parts
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


def test_pre_commit_runs_vault_annotation_sanitizer() -> None:
    config = _load_pre_commit_config()
    hooks = [hook for repo in config.get("repos", []) for hook in repo.get("hooks", [])]
    hook_ids = {hook.get("id") for hook in hooks}
    assert "vault-sanitize-annotations" in hook_ids
    ordered_ids = [hook.get("id") for hook in hooks]
    assert ordered_ids.index("vault-fix") < ordered_ids.index(
        "vault-sanitize-annotations"
    )
    assert ordered_ids.index("vault-sanitize-annotations") < ordered_ids.index(
        "spec-check"
    )

    raw = _read(".pre-commit-config.yaml")
    assert "vault sanitize annotations" in raw


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
        "complexity",
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
    for name in ("security", "dead-code", "dependencies", "complexity"):
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
    ci = _load_workflow(".github/workflows/ci.yml")
    jobs = ci["jobs"]
    required_jobs = {
        "lint",
        "test-harness-repo",
        "test-library",
        "test-vault",
        "audit-dependencies",
    }
    assert required_jobs.issubset(jobs), "CI workflow is missing required jobs"

    expected_runs = {
        # The four dimensions below `markdown` are pinned for the same reason
        # the test lanes are: each graduated from advisory to gating only once
        # its burndown reached zero, and an ungated promotion is one deletion
        # away from being silently undone. `type-strict` in particular was
        # promoted by removing its `continue-on-error` key; nothing but this
        # list stops the step itself from being removed next.
        "lint": {
            "just init",
            # Folded in from jobs of their own. On a fleet of one Linux runner
            # every job is serial, so a fifteen-second check in its own job
            # costs a whole provisioning cycle to reach. They are pinned here
            # so folding them in cannot become dropping them.
            "just deps-check",
            "just check-workflow",
            "just check-python",
            # `just check-type` is deliberately absent - see the comment on the
            # step in `ci.yml`. `check-type-platforms` runs `--python-platform`
            # linux, darwin and win32; this runner's host platform is Linux, so
            # naming both ran the Linux pass twice.
            "just check-type-platforms",
            "just check-toml",
            "just check-links",
            "just check-markdown",
            "just check-complexity",
            "just check-nesting",
            "just check-size",
            "just check-type-strict",
        },
        # `harness` and `repo` are pinned because the lesson that produced
        # them was a lane no CI job named: the guards it ran went unobserved
        # and one of them had been failing undetected. Naming both here means
        # removing a CI step fails this guard rather than silently shrinking
        # what "green" covers.
        #
        # `unit` and `vault-repair` are deliberately NOT pinned here. Both are
        # subsets of what `broad-tests` selects - `unit` by marker over the
        # same path, `vault-repair` as two `unit`-marked files under it - so a
        # step naming either re-ran work the broad legs had already done. The
        # coverage they stood for is pinned below, on the job that actually
        # provides it.
        "test-harness-repo": {
            "just init",
            "just test-harness",
            "just test-repo",
        },
        "test-library": {"just init", "just test-broad"},
        "test-vault": {
            "just init",
            "just framework-install",
            "just vault-check",
        },
        "audit-dependencies": {"just init", "just audit-deps"},
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
    ci = _load_workflow(".github/workflows/ci.yml")
    # The gate is a STEP of `lint-and-type` now, not a job. What this guard
    # holds is unchanged - the dispatch is by recipe and the pin lives in
    # `dev/` - but a job of its own bought nothing on a one-runner fleet.
    steps = ci["jobs"]["lint"]["steps"]

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

    assert actionlint.VERSION, "actionlint must be pinned to a version"
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
    ci = _load_workflow(".github/workflows/ci.yml")
    jobs = ci["jobs"]
    steps = jobs["lint"]["steps"]
    used_actions = {step["uses"] for step in steps if "uses" in step}
    assert "taiki-e/install-action@v2" in used_actions
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


def _sentinel_workflow() -> _Workflow:
    """The main-branch CI sentinel, parsed."""
    text = (ROOT / ".github" / "workflows" / "main-ci-sentinel.yml").read_text(
        encoding="utf-8"
    )
    return cast("_Workflow", yaml.safe_load(text))


def _sentinel_step(name_fragment: str) -> _WorkflowStep:
    """The one sentinel step whose name contains *name_fragment*."""
    steps = _sentinel_workflow()["jobs"]["assert-main-was-validated"]["steps"]
    matches = [step for step in steps if name_fragment in step.get("name", "")]
    assert len(matches) == 1, (
        f"expected exactly one sentinel step named like {name_fragment!r}, "
        f"found {[step.get('name') for step in matches]}"
    )
    return matches[0]


def test_the_sentinel_closes_its_issue_only_on_a_healthy_verdict() -> None:
    """`pending` must not close the sentinel issue.

    ``Verdict.exit_code`` is 0 for ``healthy`` and for ``pending`` alike,
    because neither should fail the sentinel job. A workflow that derives
    health from that exit code therefore cannot tell "main is green" from "no
    verdict yet" - and closes on both. That is exactly what happened at
    17:25 UTC on 2026-09-04: the judge logged ``pending: 1 CI run(s) still in
    flight``, the close step ran anyway, and issue #398 was closed as
    "validated again" while main's tip was red and its CI still running.

    The condition is asserted literally rather than by behaviour because the
    failure mode is a silent one: a condition that never matches - a typo, or
    a negation such as ``!= 'unhealthy'`` that readmits ``pending`` - leaves
    the step skipped and the job green, which is indistinguishable from
    working.
    """
    step = _sentinel_step("Close the sentinel issue")

    assert step.get("if") == "${{ steps.judge.outputs.state == 'healthy' }}"


def test_the_sentinel_opens_its_issue_only_on_an_unhealthy_verdict() -> None:
    """The other half of the same contract: `pending` must not report a fault.

    A sentinel that files an issue while a run is still in flight fires on
    every push and gets muted, which leaves main less protected than if it did
    not exist.
    """
    step = _sentinel_step("Open an issue")

    assert step.get("if") == "${{ steps.judge.outputs.state == 'unhealthy' }}"


def test_the_sentinel_branches_only_on_states_the_judge_can_return() -> None:
    """Every state named in a condition must be one the module can produce.

    A misspelled state is the worst shape this workflow can take: the
    condition is valid YAML, the expression evaluates to false forever, the
    step is skipped, and the job passes. Nothing reports it.
    """
    from dev.ci_sentinel.main_ci_health import State

    known = set(get_args(State))
    steps = _sentinel_workflow()["jobs"]["assert-main-was-validated"]["steps"]
    referenced = {
        match.group("state")
        for step in steps
        for match in _SENTINEL_STATE_CONDITION.finditer(str(step.get("if", "")))
    }

    assert referenced, "no sentinel step branches on the judge's state"
    assert referenced <= known, (
        f"these sentinel conditions name states the judge never returns: "
        f"{sorted(referenced - known)}; it returns {sorted(known)}"
    )


def test_the_sentinel_does_not_derive_health_from_the_judge_exit_code() -> None:
    """No step may branch on a boolean distilled from the module's exit code.

    Keeping the states apart in the judge step is worth nothing if a later
    step collapses them again, so the collapsed output is banned by name: the
    `healthy` output that carried this bug must not come back.
    """
    steps = _sentinel_workflow()["jobs"]["assert-main-was-validated"]["steps"]

    offenders = [
        step.get("name")
        for step in steps
        if "outputs.healthy" in str(step.get("if", ""))
        or "outputs.healthy" in str(step.get("run", ""))
        or "healthy=$(" in str(step.get("run", ""))
    ]

    assert not offenders, (
        f"these sentinel steps read health from the judge's exit code rather "
        f"than its state: {offenders}. The exit code answers 'should this job "
        f"fail?', which is 0 for both `healthy` and `pending`."
    )


def test_the_sentinel_fails_when_the_judge_returns_no_verdict() -> None:
    """A judge that crashed must not read as a quiet pass.

    With the state absent, every condition below evaluates false, no step
    runs, and the sentinel reports success having judged nothing - the same
    class of silent skip the sentinel itself exists to catch.
    """
    run = _sentinel_step("Judge main's tip").get("run", "")

    assert "the sentinel produced no verdict" in run, (
        "the judge step must fail loudly when it produces no parseable state"
    )


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
