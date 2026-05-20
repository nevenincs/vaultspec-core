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


def test_justfile_contains_required_recipes() -> None:
    justfile = _read("justfile")
    required = {
        "prod",
        "dev",
        "ci",
        "_dev-deps",
        "_dev-lint",
        "_dev-fix",
        "_dev-audit",
        "_dev-test",
        "_dev-build",
        "_dev-publish",
        "_dev-precommit",
    }
    missing = [name for name in sorted(required) if not _recipe_exists(justfile, name)]
    assert not missing, f"Missing required just recipes: {missing}"


def test_justfile_exposes_approved_targets() -> None:
    justfile = _read("justfile")
    # Top-level namespace recipes
    assert "prod *args='':" in justfile
    assert "dev target='--help' *args='':" in justfile
    assert "ci *args='':" in justfile
    # Internal dev recipes with default targets
    assert "_dev-deps target='--help':" in justfile
    assert "_dev-lint target='--help':" in justfile
    assert "_dev-fix target='--help':" in justfile
    assert "_dev-audit target='--help':" in justfile
    assert "_dev-test target='--help':" in justfile
    assert "_dev-build target='--help':" in justfile
    assert "_dev-publish target='--help' tag='':" in justfile
    assert "_dev-precommit target='--help':" in justfile
    # Dev dispatch covers all verbs
    for verb in (
        "deps",
        "lint",
        "fix",
        "audit",
        "test",
        "build",
        "publish",
        "precommit",
    ):
        assert verb in justfile
    # Lint sub-targets
    for target in ("python", "type", "links", "toml", "markdown", "workflow"):
        assert target in justfile
    # Build/test sub-targets
    for target in ("python", "docker", "all"):
        assert target in justfile
    assert "docker-ghcr" in justfile


def test_dependency_audit_uses_uv_native_scanner() -> None:
    justfile = _read("justfile")
    audit_script = _read("scripts/dependency_audit.py")
    # The supply-chain gate's justfile recipe delegates to the cross-platform
    # audit wrapper, which runs uv's native auditor against the frozen
    # lockfile. The default scope already covers the project plus the default
    # dependency groups, so no group-selection flag is pinned: --all-groups
    # was accepted by uv 0.10.x but rejected by 0.11.x, and breaking CI on a
    # uv minor bump is exactly the brittleness this audit is meant to prevent.
    assert "scripts/dependency_audit.py" in justfile
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
    for surface in (justfile, audit_script):
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


def test_lint_all_runs_every_validation_surface() -> None:
    justfile = _read("justfile")
    assert "just _dev-lint-python" in justfile
    assert "just _dev-lint-type" in justfile
    assert "just _dev-lint-links" in justfile
    assert "just _dev-lint-toml" in justfile
    assert "just _dev-lint-markdown" in justfile
    assert "just _dev-lint-workflow" in justfile
    assert "uv run ruff format --check src tests" in justfile


def test_test_all_runs_python_and_docker() -> None:
    justfile = _read("justfile")
    assert "just _dev-test-python" in justfile
    assert "just _dev-test-docker" in justfile
    assert "just _dev-build-docker" in justfile
    assert "just _dev-build-python" in justfile


def test_fix_surface_covers_all_autofixable_targets() -> None:
    justfile = _read("justfile")
    assert "_dev-fix target='--help':" in justfile
    assert "uv run ruff format src tests" in justfile
    assert "uv run ruff check --fix src tests" in justfile
    assert "taplo fmt" in justfile
    assert "pymarkdown" in justfile
    assert ".pymarkdown.json" in justfile
    assert "vault check all --fix" in justfile
    assert "vault sanitize annotations" in justfile


def test_markdown_lint_uses_pymarkdown() -> None:
    justfile = _read("justfile")
    assert "pymarkdown" in justfile
    assert "--config .pymarkdown.json" in justfile
    assert "README.md" in justfile


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
            "just dev deps sync",
            "just dev lint python",
            "just dev lint type",
            "just dev lint toml",
            "just dev lint links",
            "just dev lint markdown",
        },
        "tests": {"just dev deps sync", "just dev test python"},
        "windows-vault-repair": {
            "just dev deps sync",
            (
                "uv run pytest src/vaultspec_core/tests/cli/test_vault_repair.py "
                "src/vaultspec_core/vaultcore/checks/tests/"
                "test_structure_case_rename.py -q"
            ),
        },
        "vault-audit": {"just dev deps sync", "just prod vault check all"},
        "dependency-audit": {"just dev deps sync", "just dev audit deps"},
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


def test_prod_delegates_to_cli() -> None:
    justfile = _read("justfile")
    # prod recipe passes all args through to uv run vaultspec-core
    assert "prod *args='':" in justfile
    assert '"uv run vaultspec-core " + args' in justfile
    # install/uninstall available via prod namespace (documented in comments)
    assert "just prod install" in justfile
    assert "uv run vaultspec-core" in justfile


def test_provider_capability_enum_covers_all_tools() -> None:
    """Every Tool enum member must have a ToolConfig with non-empty capabilities."""
    from vaultspec_core.core.enums import Tool
    from vaultspec_core.core.types import init_paths

    ctx = init_paths(ROOT)

    for tool in Tool:
        cfg = ctx.tool_configs.get(tool)
        assert cfg is not None, f"Tool {tool.value} has no ToolConfig"
        assert cfg.capabilities, f"Tool {tool.value} has empty capabilities"


def test_provider_capability_consistency() -> None:
    """Capability declarations must be consistent with ToolConfig fields."""
    from vaultspec_core.core.enums import ProviderCapability, Tool
    from vaultspec_core.core.types import init_paths

    ctx = init_paths(ROOT)

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


def test_every_capability_has_at_least_one_provider() -> None:
    """Each ProviderCapability value must map to at least one provider."""
    from vaultspec_core.core.enums import ProviderCapability, Tool
    from vaultspec_core.core.types import init_paths

    ctx = init_paths(ROOT)

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
