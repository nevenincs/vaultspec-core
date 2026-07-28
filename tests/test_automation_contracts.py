from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_yaml(path: str) -> dict:
    return yaml.safe_load(_read(path))


def _recipe_exists(justfile_text: str, name: str) -> bool:
    pattern = rf"(?m)^{re.escape(name)}(?:\s|:)"
    return re.search(pattern, justfile_text) is not None


def test_justfile_exposes_every_verb_at_the_root() -> None:
    """Every entry point is a root verb; there is no nested dispatch namespace.

    The harness was previously reached through `just dev <verb>` with a
    parallel `just prod` mirror of the shipped CLI.  Both are gone: the
    justfile is a development-only file, so a `dev` namespace inside it named
    nothing, and mirroring a finished product's CLI only adds a layer that
    drifts.  This pins the collapse so neither reappears.
    """
    justfile = _read("justfile")
    missing = [
        name
        for name in sorted(
            {
                "deps",
                "lint",
                "fix",
                "audit",
                "test",
                "build",
                "precommit",
                "vault",
                "framework",
                "assets",
                "health",
                "ci",
            }
        )
        if not _recipe_exists(justfile, name)
    ]
    assert not missing, f"Missing required just recipes: {missing}"

    assert not _recipe_exists(justfile, "prod"), (
        "`just prod` mirrored the shipped vaultspec-core CLI and was removed; "
        "invoke the product directly with `uv run --no-sync vaultspec-core`."
    )
    assert not re.search(r"(?m)^_dev-", justfile), (
        "The `_dev-*` internal recipe namespace was collapsed to root verbs."
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
        assert re.search(
            rf"(?m)^{verb} target='[a-z-]+':\n\s+\{{\{{dev\}}\}} {verb} ", justfile
        ), f"Recipe `{verb}` must delegate to the dev package in one line"
    for shell_ism in ('if os() == "windows"', "switch (", "Get-Command", "elseif"):
        assert shell_ism not in justfile, (
            f"Shell branching {shell_ism!r} belongs in dev/toolchain.py, "
            "not the justfile"
        )


def test_dependency_audit_uses_uv_native_scanner() -> None:
    # The invocation moved out of the justfile into the declarative toolchain
    # when every recipe collapsed to a single delegation; the contract is
    # unchanged, so it is asserted against its new home.
    toolchain = _read("dev/toolchain.py")
    audit_script = _read("scripts/dependency_audit.py")
    # The supply-chain gate's justfile recipe delegates to the cross-platform
    # audit wrapper, which runs uv's native auditor against the frozen
    # lockfile. The default scope already covers the project plus the default
    # dependency groups, so no group-selection flag is pinned: --all-groups
    # was accepted by uv 0.10.x but rejected by 0.11.x, and breaking CI on a
    # uv minor bump is exactly the brittleness this audit is meant to prevent.
    assert "scripts/dependency_audit.py" in toolchain
    assert "uv audit" in audit_script
    assert "--preview-features" in audit_script
    assert "--frozen" in audit_script
    # This is a uv-managed project: the supply-chain gate is uv-native end to
    # end and never shells out to pip. pip-audit drags `pip` itself into the
    # environment as a transitive dependency - historically the only
    # vulnerability `uv audit` ever reported here - so no pip-named scanner
    # may appear in the recipe or the wrapper. When uv's preview decoder
    # aborts on a malformed OSV record, the wrapper independently repeats the
    # bulk OSV query rather than falling back to a second tool.
    for surface in (toolchain, audit_script):
        assert "pip-audit" not in surface
        assert "pip-tools" not in surface


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
    config = _load_yaml(".pre-commit-config.yaml")
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
    config = _load_yaml(".pre-commit-config.yaml")
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
    required = {"deps", "security", "dead-code", "dependencies", "complexity", "all"}
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

    audit = toolchain.find_verb("audit")
    assert audit is not None
    security = next(t for t in audit.targets if t.name == "security")
    argv = security.steps[0].argv
    assert "-x" in argv, "the bandit scan must carry an exclusion"
    assert argv[argv.index("-x") + 1] == "*/tests/*", (
        "the bandit exclusion must be a glob covering nested test trees"
    )


def test_ci_workflow_calls_just_for_quality_gates() -> None:
    ci = _load_yaml(".github/workflows/ci.yml")
    jobs = ci["jobs"]
    required_jobs = {
        "workflow-lint",
        "lint-and-type",
        "tests",
        "windows-vault-repair",
        "vault-audit",
        "dependency-audit",
    }
    assert required_jobs.issubset(jobs), "CI workflow is missing required jobs"

    expected_runs = {
        "lint-and-type": {
            "just deps sync",
            "just lint python",
            "just lint type",
            "just lint toml",
            "just lint links",
            "just lint markdown",
        },
        "tests": {"just deps sync", "just test unit"},
        "windows-vault-repair": {"just deps sync", "just test vault-repair"},
        "vault-audit": {
            "just deps sync",
            "just framework install",
            "just vault check",
        },
        "dependency-audit": {"just deps sync", "just audit deps"},
    }

    for job_name, expected in expected_runs.items():
        steps = jobs[job_name]["steps"]
        run_commands = {step.get("run") for step in steps if "run" in step}
        missing = [cmd for cmd in sorted(expected) if cmd not in run_commands]
        assert not missing, f"Job {job_name} missing just commands: {missing}"


def test_ci_workflow_uses_actionlint() -> None:
    ci = _load_yaml(".github/workflows/ci.yml")
    jobs = ci["jobs"]
    steps = jobs["workflow-lint"]["steps"]
    used_actions = {step.get("uses") for step in steps if "uses" in step}
    assert any(a.startswith("docker://rhysd/actionlint:") for a in used_actions)


def test_ci_workflow_installs_native_lint_tools() -> None:
    ci = _load_yaml(".github/workflows/ci.yml")
    jobs = ci["jobs"]
    steps = jobs["lint-and-type"]["steps"]
    used_actions = {step.get("uses") for step in steps if "uses" in step}
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
            if cap
            in ctx.tool_configs.get(
                tool, type("", (), {"capabilities": frozenset()})()
            ).capabilities
        ]
        assert providers, f"ProviderCapability.{cap.name} has no providers"
