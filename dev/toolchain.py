"""The declarative registry of development verbs and their targets.

This module is the single source of truth for what the harness can do. The
``justfile`` exposes each verb; everything about *what a target runs*, whether
it gates, and how targets compose into aggregates is stated here as data.

The verbs split by CONSEQUENCE, not by tool:

``lint``
    GATES. Read-only, and a finding fails the build.
``fix``
    MUTATES. Everything automatically repairable, in one pass.
``audit``
    Only ``deps`` gates. Every other target is advisory and exits 0 even with
    findings, because each yields a lead to confirm rather than a verdict.
``test``
    GATES. See :data:`TEST` for what each lane proves.
"""

from __future__ import annotations

from dataclasses import dataclass

from dev.runner import Cmd, Echo, Ref, Step, ToolOrDocker, uv_run

PACKAGE = "src/vaultspec_core"

#: Python trees that carry committed source and are therefore linted. `scripts`
#: and `statistic` were historically excluded while holding real code; the
#: per-file-ignores in pyproject.toml already name `statistic`, so the config
#: always intended a scope the invocation never applied. `tools` holds the
#: code-health report, which is committed source like any other and must not
#: lint itself into an exception.
PYTHON_PATHS = ("src", "tests", "scripts", "statistic", "dev", "tools")

#: Markers requiring credentials or live network, excluded from every gate.
EXCLUDED_MARKERS = "not gemini and not claude and not network"

#: Trees whose Markdown is formatted and linted.
MARKDOWN_PATHS = ("README.md", "docs/", ".vault/", "src/vaultspec_core/builtins/")

#: User-facing Markdown additionally held to a hard wrap.
WRAPPED_MARKDOWN = (
    "README.md",
    "docs/framework.md",
    "docs/MCP.md",
    "docs/CLI.md",
    "src/vaultspec_core/builtins",
)

#: complexipy emits status glyphs; Windows consoles default to a codepage that
#: cannot encode them, which aborts the run before any finding is reported.
UTF8 = {"PYTHONIOENCODING": "utf-8"}

#: Repairing the corpus is reachable as both `fix vault` and `vault fix`, which
#: are the same action approached from the two verbs a reader might try. The
#: steps are defined once here so the two entry points cannot drift.
VAULT_FIX_STEPS = (
    uv_run("vaultspec-core", "vault", "check", "all", "--fix"),
    uv_run("vaultspec-core", "vault", "sanitize", "annotations"),
)


@dataclass(frozen=True)
class Target:
    """One selectable behaviour within a verb.

    Args:
        name: The target token typed on the command line.
        summary: One-line description shown by ``help``.
        steps: The steps to run, in order.
        advisory: When true the target reports findings but always exits 0.
        keep_going: When true a failing step does not stop the remaining
            steps. Aggregate dashboards set this so one red dimension does
            not hide every dimension after it.
    """

    name: str
    summary: str
    steps: tuple[Step, ...]
    advisory: bool = False
    keep_going: bool = False


@dataclass(frozen=True)
class Verb:
    """A top-level harness verb and the targets it dispatches to.

    Args:
        name: The verb token, matching the justfile recipe name.
        summary: One-line description of the verb.
        targets: The selectable targets, in display order.
        note: Optional extra line appended to the verb's ``help`` output.
    """

    name: str
    summary: str
    targets: tuple[Target, ...]
    note: str = ""

    def target_names(self) -> tuple[str, ...]:
        """Return every target token in display order."""
        return tuple(target.name for target in self.targets)

    def find(self, name: str) -> Target | None:
        """Return the named target, or ``None`` when it is not defined."""
        return next((t for t in self.targets if t.name == name), None)


def _ruff_paths(*prefix: str) -> Cmd:
    return uv_run("ruff", *prefix, *PYTHON_PATHS)


DEPS = Verb(
    name="deps",
    summary="Manage project dependencies and the lockfile.",
    targets=(
        Target(
            "sync",
            "Install the locked dependency set.",
            (Cmd(("uv", "sync", "--locked", "--group", "dev")),),
        ),
        Target(
            "upgrade",
            "Upgrade every dependency group.",
            (Cmd(("uv", "sync", "--upgrade", "--all-groups")),),
        ),
        Target("lock", "Regenerate the lockfile.", (Cmd(("uv", "lock")),)),
        Target(
            "lock-upgrade",
            "Regenerate the lockfile at the newest allowed versions.",
            (Cmd(("uv", "lock", "--upgrade")),),
        ),
        Target(
            "check",
            "Verify the lockfile matches pyproject.toml.",
            (Cmd(("uv", "lock", "--check")),),
        ),
    ),
)

LINT = Verb(
    name="lint",
    summary="Run gating static analysis.",
    note=(
        "'all' omits complexity, nesting, and size - run those by name. "
        "Each is a real gate whose burndown is unfinished, so adding it to the chain "
        "would hide every dimension behind it."
    ),
    targets=(
        Target(
            "python",
            "Ruff lint and format verification.",
            (_ruff_paths("check"), _ruff_paths("format", "--check")),
        ),
        Target(
            "type",
            "Ty type checking.",
            (uv_run("python", "-m", "ty", "check", PACKAGE),),
        ),
        Target(
            "toml",
            "Taplo TOML linting.",
            (ToolOrDocker("taplo", ("lint", "*.toml"), "tamasfe/taplo:0.9"),),
        ),
        Target(
            "links",
            "Lychee link checking.",
            (
                ToolOrDocker(
                    "lychee",
                    (
                        "--config",
                        "lychee.toml",
                        "README.md",
                        "docs",
                        ".vault",
                        f"{PACKAGE}/builtins",
                    ),
                    "lycheeverse/lychee:latest",
                    (
                        "--config",
                        "/repo/lychee.toml",
                        "README.md",
                        "docs",
                        ".vault",
                        f"{PACKAGE}/builtins",
                    ),
                ),
            ),
        ),
        Target(
            "markdown",
            "Markdown formatting and style verification.",
            (
                uv_run("mdformat", "--check", *MARKDOWN_PATHS),
                uv_run("mdformat", "--wrap", "88", "--check", *WRAPPED_MARKDOWN),
                uv_run(
                    "pymarkdown",
                    "--config",
                    ".pymarkdown.json",
                    "scan",
                    "-r",
                    *MARKDOWN_PATHS,
                ),
            ),
        ),
        Target(
            "workflow",
            "Actionlint GitHub workflow checking.",
            (ToolOrDocker("actionlint", (), "rhysd/actionlint:latest"),),
        ),
        Target(
            "complexity",
            "Cognitive complexity over production code.",
            (Cmd(uv_run("complexipy", PACKAGE).argv, UTF8),),
        ),
        Target(
            "nesting",
            "Nesting depth (PLR1702, preview-scoped).",
            (uv_run("ruff", "check", "src", "--select", "PLR1702", "--preview"),),
        ),
        Target(
            "size",
            "Module length and class design limits ruff has no rule for.",
            (
                uv_run(
                    "pylint",
                    PACKAGE,
                    "--rcfile=pyproject.toml",
                    "--recursive=y",
                    "--score=n",
                ),
            ),
        ),
        Target(
            "type-strict",
            "Basedpyright strict-mode type checking.",
            (uv_run("basedpyright"),),
        ),
        Target(
            "all",
            "Every gate that is green and can hold that line.",
            # complexity/nesting/size joined this aggregate once each went green
            # and held: the governing ADR's promotion rule is that a dimension
            # graduates when its finding count reaches zero at the gate's
            # threshold. Until they did, `just lint` covered six of ten
            # dimensions while CI ran the other four as separate steps, so a
            # contributor could push a complexity regression and only learn
            # about it from CI. A local gate that omits what CI enforces
            # teaches people the wrong thing about what "green" means.
            #
            # `type-strict` joined the same way: the burndown reached zero, so
            # the dimension graduated into the chain under the same promotion
            # rule the other dimensions followed.
            tuple(
                Ref(name)
                for name in (
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
                )
            ),
        ),
    ),
)

FIX = Verb(
    name="fix",
    summary="Apply every available formatter and automatic fix.",
    targets=(
        Target(
            "python",
            "Format and auto-repair Python source.",
            (_ruff_paths("format"), _ruff_paths("check", "--fix")),
        ),
        Target(
            "toml",
            "Format TOML files.",
            (ToolOrDocker("taplo", ("fmt", "*.toml"), "tamasfe/taplo:0.9"),),
        ),
        Target(
            "markdown",
            "Format and auto-repair Markdown.",
            (
                uv_run("mdformat", *MARKDOWN_PATHS),
                uv_run("mdformat", "--wrap", "88", *WRAPPED_MARKDOWN),
                uv_run(
                    "pymarkdown",
                    "--config",
                    ".pymarkdown.json",
                    "fix",
                    "-r",
                    *MARKDOWN_PATHS,
                ),
            ),
        ),
        Target(
            "vault",
            "Repair this repository's own .vault/ corpus.",
            VAULT_FIX_STEPS,
        ),
        Target(
            "all",
            "Run every fixer.",
            tuple(Ref(name) for name in ("python", "toml", "markdown", "vault")),
        ),
    ),
)

AUDIT = Verb(
    name="audit",
    summary="Audit dependencies and code quality; only 'deps' gates.",
    note=(
        "Only 'deps' gates - a published advisory against a pinned version is a "
        "verdict. Every other target is advisory and exits 0 even with findings."
    ),
    targets=(
        Target(
            "deps",
            "Dependency vulnerability audit (GATES).",
            (Cmd(("uv", "run", "python", "scripts/dependency_audit.py")),),
        ),
        Target(
            "security",
            "Bandit security scan.",
            (
                uv_run(
                    "bandit",
                    "-c",
                    "pyproject.toml",
                    "-r",
                    PACKAGE,
                    "-x",
                    "*/tests/*",
                    "-q",
                ),
            ),
            advisory=True,
        ),
        Target(
            "dead-code", "Vulture dead-code scan.", (uv_run("vulture"),), advisory=True
        ),
        Target(
            "dependencies",
            "Deptry dependency-drift scan.",
            (uv_run("deptry", PACKAGE),),
            advisory=True,
        ),
        Target(
            "complexity",
            "Cognitive complexity over the test tree.",
            (Cmd(uv_run("complexipy", f"{PACKAGE}/tests").argv, UTF8),),
            advisory=True,
        ),
        Target(
            "all",
            "Every audit dimension, as a dashboard.",
            (
                Echo("=== dependency advisories ==="),
                Ref("deps"),
                Echo("=== security ==="),
                Ref("security"),
                Echo("=== dead code ==="),
                Ref("dead-code"),
                Echo("=== undeclared dependencies ==="),
                Ref("dependencies"),
                Echo("=== test-tree cognitive complexity ==="),
                Ref("complexity"),
            ),
            advisory=True,
            keep_going=True,
        ),
    ),
)

TEST = Verb(
    name="test",
    summary="Run the project test suites.",
    note=(
        "'unit' is marker-scoped and selects a slice, not the suite - a green 'unit' "
        "says nothing about the far larger population 'broad' runs."
    ),
    targets=(
        Target(
            "unit",
            "The fast marker-scoped gate; first failure aborts.",
            (
                uv_run(
                    "pytest",
                    PACKAGE,
                    "-x",
                    "-q",
                    "--tb=short",
                    "-m",
                    f"unit and {EXCLUDED_MARKERS}",
                ),
            ),
        ),
        Target(
            "broad",
            "The whole package suite minus credential-gated markers.",
            (uv_run("pytest", PACKAGE, "-q", "--tb=short", "-m", EXCLUDED_MARKERS),),
        ),
        Target(
            "repo",
            "The repository-root tests/ tree (automation and suite-quality guards).",
            (uv_run("pytest", "tests", "-q", "--tb=short", "-m", EXCLUDED_MARKERS),),
        ),
        Target(
            "vault-repair",
            "The Windows repair and case-rename regression cohort.",
            (
                uv_run(
                    "pytest",
                    f"{PACKAGE}/tests/cli/test_vault_repair.py",
                    f"{PACKAGE}/vaultcore/checks/tests/test_structure_case_rename.py",
                    "-q",
                    "--tb=short",
                ),
            ),
        ),
        Target(
            "benchmark",
            "The slow scale benchmarks, deselected by default.",
            (uv_run("pytest", PACKAGE, "-q", "--tb=short", "-m", "benchmark"),),
        ),
        Target(
            "harness",
            "The dev/ harness registry integrity guards.",
            (uv_run("pytest", "dev/tests", "-q", "--tb=short"),),
        ),
        Target(
            "all",
            "The broad suite, vault-repair cohort, harness guards, and repo tests.",
            # `repo` is in this aggregate deliberately. It was previously
            # reachable only by naming it, and no CI lane named it either, so
            # the tree it runs - the automation contracts and the suite-quality
            # guards - was unobserved. A guard nothing runs is not a guard: the
            # test-doubles check in it had been failing undetected.
            (Ref("broad"), Ref("vault-repair"), Ref("harness"), Ref("repo")),
        ),
    ),
)

BUILD = Verb(
    name="build",
    summary="Build the Python distribution artifacts.",
    note="The standalone binaries are 'just binaries <tag> <rust-target>'.",
    targets=(
        Target("python", "Build the wheel and sdist.", (Cmd(("uv", "build")),)),
        Target("all", "Run every build.", (Ref("python"),)),
    ),
)

VAULT = Verb(
    name="vault",
    summary="Operate on this repository's own .vault/ development corpus.",
    targets=(
        Target(
            "check",
            "Run the vault health checks.",
            (uv_run("vaultspec-core", "vault", "check", "all"),),
        ),
        Target("fix", "Repair and sanitize the corpus.", VAULT_FIX_STEPS),
        Target(
            "graph",
            "Render the document graph with metrics.",
            (uv_run("vaultspec-core", "vault", "graph", "--metrics"),),
        ),
        Target(
            "index",
            "Regenerate the auto-generated feature indexes.",
            (uv_run("vaultspec-core", "vault", "feature", "index"),),
        ),
        Target(
            "list",
            "List every vault document.",
            (uv_run("vaultspec-core", "vault", "list"),),
        ),
        Target(
            "stats",
            "Show corpus statistics.",
            (uv_run("vaultspec-core", "vault", "stats"),),
        ),
        Target(
            "status",
            "Show in-flight plan orientation.",
            (uv_run("vaultspec-core", "status"),),
        ),
    ),
)

FRAMEWORK = Verb(
    name="framework",
    summary="Operate on this repository's own .vaultspec/ framework harness.",
    note=(
        "'uninstall' is deliberately absent: .vaultspec/ here is the canonical "
        "framework source, not a consumer's installed copy."
    ),
    targets=(
        Target(
            "doctor",
            "Diagnose workspace health, failing on errors.",
            (uv_run("vaultspec-core", "spec", "doctor", "--gate-errors"),),
        ),
        Target(
            "install",
            "Rebuild the install manifest from tracked config.",
            (uv_run("vaultspec-core", "install", "--force"),),
        ),
        Target(
            "upgrade",
            "Refresh the installed builtin snapshots.",
            (uv_run("vaultspec-core", "install", "--upgrade"),),
        ),
        Target(
            "sync",
            "Regenerate the provider outputs.",
            (uv_run("vaultspec-core", "sync"),),
        ),
        Target(
            "reference",
            "Regenerate the bundled CLI reference.",
            (uv_run("vaultspec-core", "spec", "reference", "generate"),),
        ),
        Target(
            "reference-check",
            "Verify the bundled CLI reference is current.",
            (uv_run("vaultspec-core", "spec", "reference", "generate", "--check"),),
        ),
        Target(
            "providers",
            "Guard against committing provider artifacts.",
            (uv_run("vaultspec-core", "check-providers"),),
        ),
    ),
)

ASSETS = Verb(
    name="assets",
    summary="Regenerate the committed README terminal renders and demo GIF.",
    note="Both renderers drive real commands against a throwaway synthetic vault.",
    targets=(
        Target(
            "readme",
            "Regenerate the terminal-render SVGs.",
            (uv_run("python", "scripts/render_readme_assets.py"),),
        ),
        Target(
            "demo",
            "Regenerate the pipeline demo GIF (needs agg on PATH).",
            (uv_run("python", "scripts/render_readme_demo.py"),),
        ),
        Target("all", "Regenerate every asset.", (Ref("readme"), Ref("demo"))),
    ),
)

HEALTH = Verb(
    name="health",
    summary="Rank the worst offenders across every code-health dimension.",
    note=(
        "MEASUREMENT ONLY - every target exits 0. This composes the gates rather "
        "than re-implementing any threshold, so the report and the gate can never "
        "disagree. 'census' regenerates the distributions each baseline ratchet in "
        "pyproject.toml is calibrated from; run it before lowering a threshold so "
        "the new value is a measurement rather than a guess."
    ),
    targets=(
        Target(
            "report",
            "Worst offenders per dimension, including strict types.",
            (Cmd(uv_run("python", "tools/health_report.py").argv, UTF8),),
            advisory=True,
        ),
        Target(
            "fast",
            "The same report without the basedpyright section.",
            (Cmd(uv_run("python", "tools/health_report.py", "--fast").argv, UTF8),),
            advisory=True,
        ),
        Target(
            "census",
            "Baseline-calibration distributions for the ratchet thresholds.",
            (Cmd(uv_run("python", "tools/health_report.py", "--census").argv, UTF8),),
            advisory=True,
        ),
    ),
)

CI = Verb(
    name="ci",
    summary="Run the full local gate.",
    targets=(
        Target(
            "all",
            "Lint, dependency audit, vault checks, and the broad test suite.",
            (
                Echo("=== lint ==="),
                Cmd(("uv", "run", "--no-sync", "python", "-m", "dev", "lint", "all")),
                Echo("=== dependency audit ==="),
                Cmd(("uv", "run", "--no-sync", "python", "-m", "dev", "audit", "deps")),
                Echo("=== vault ==="),
                Cmd(
                    ("uv", "run", "--no-sync", "python", "-m", "dev", "vault", "check")
                ),
                Echo("=== tests ==="),
                Cmd(("uv", "run", "--no-sync", "python", "-m", "dev", "test", "broad")),
            ),
        ),
    ),
)

#: Every verb, in the order ``help`` lists them.
VERBS: tuple[Verb, ...] = (
    DEPS,
    LINT,
    FIX,
    AUDIT,
    TEST,
    BUILD,
    VAULT,
    FRAMEWORK,
    ASSETS,
    HEALTH,
    CI,
)

#: Default target per verb, used when the justfile passes none.
DEFAULTS: dict[str, str] = {
    "deps": "sync",
    "lint": "all",
    "fix": "all",
    "audit": "all",
    "test": "all",
    "build": "python",
    "vault": "check",
    "framework": "doctor",
    "assets": "all",
    "health": "report",
    "ci": "all",
}


def find_verb(name: str) -> Verb | None:
    """Return the named verb, or ``None`` when it is not defined.

    Args:
        name: The verb token to resolve.

    Returns:
        The matching :class:`Verb`, or ``None``.
    """
    return next((verb for verb in VERBS if verb.name == name), None)


def public_targets(verb: Verb) -> tuple[str, ...]:
    """Return a verb's user-selectable target names.

    Targets whose name begins with an underscore are internal composition
    helpers and are hidden from help output.

    Args:
        verb: The verb to inspect.

    Returns:
        The public target tokens in display order.
    """
    return tuple(name for name in verb.target_names() if not name.startswith("_"))
