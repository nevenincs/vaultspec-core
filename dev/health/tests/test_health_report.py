"""Guards for the composed code-health measurement instrument.

``dev/health/health_report.py`` is invoked as a script by the ``health`` verb in
:mod:`dev.toolchain` and never imported by anything that ships, so until these
guards existed no test observed it at all - a rename, a broken third-party API,
or a flag drifting away from the recipe that passes it would have surfaced only
when someone happened to run ``just health``, and the CI job that does run it is
advisory and cannot fail.

Every contract below is one that fails silently rather than loudly: the harness
pointing at a script path that no longer exists, the harness passing a flag the
report rejects, the report's floor drifting above the gate whose offenders it
exists to surface, the module's path arithmetic anchoring on the wrong tree, and
a rendered dimension printing an empty table instead of a measurement.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from dev.health import health_report
from dev.runner import Cmd, ToolOrDocker
from dev.toolchain import find_verb

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "dev" / "health" / "health_report.py"


def _health_argv() -> list[tuple[str, ...]]:
    """Return the command line of every step the ``health`` verb declares."""
    verb = find_verb("health")
    assert verb is not None, "the toolchain registry must expose a `health` verb"
    argvs: list[tuple[str, ...]] = []
    for target in verb.targets:
        for step in target.steps:
            assert isinstance(step, (Cmd, ToolOrDocker)), (
                f"health.{target.name} declares a step that runs no command: {step}"
            )
            argvs.append(step.argv)
    return argvs


def _accepted_flags() -> set[str]:
    """Return the long flags the report's own ``--help`` usage line advertises.

    Read from the process the harness actually launches rather than from the
    parser object, so a flag that exists in the source but is unreachable at
    runtime - a shadowed name, an import that fails before parsing - still
    counts as absent.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, f"`--help` exited {result.returncode}"
    usage = result.stdout.split("\n\n", maxsplit=1)[0]
    return {token.strip("[]") for token in usage.split() if token.startswith("[--")}


def _measured_modules() -> list[Path]:
    """Measure the same population the report measures, independently of it."""
    return [
        path
        for path in sorted((REPO_ROOT / "src" / "vaultspec_core").rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def test_the_harness_invokes_a_script_that_exists() -> None:
    """Every `health` step names a real file under the repository root.

    The verb passes a repository-relative path string, which no import ever
    resolves, so moving or renaming the report leaves the recipe syntactically
    valid and broken only at runtime.
    """
    for argv in _health_argv():
        scripts = [token for token in argv if token.endswith(".py")]
        assert scripts, f"health step declares no script: {argv}"
        for script in scripts:
            assert (REPO_ROOT / script).is_file(), (
                f"health step points at a missing script: {script}"
            )


def test_the_harness_passes_only_flags_the_report_accepts() -> None:
    """No `health` target may pass a flag the report would reject.

    argparse exits 2 on an unknown flag, but the verb is advisory, so the CI
    job that runs it reports green either way. This is where that disagreement
    becomes visible.
    """
    accepted = _accepted_flags()
    assert accepted, "the report advertises no flags in its usage line"
    passed = {
        token for argv in _health_argv() for token in argv if token.startswith("--")
    }
    unknown = sorted(passed - accepted - {"--no-sync"})
    assert not unknown, (
        f"health targets pass flags the report does not accept: {unknown}; "
        f"accepted: {sorted(accepted)}"
    )


def test_report_floor_sits_below_the_gate_it_reports_against() -> None:
    """The cognitive floor must surface every function the gate would fail.

    The report exists to rank offenders ahead of the ratchet. A floor at or
    above the configured gate would hide exactly the functions the next ratchet
    step needs to see, and the module would still print a full-looking table.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    gate = config["tool"]["complexipy"]["max-complexity-allowed"]
    assert gate > health_report.COGNITIVE_REPORT_FLOOR, (
        f"the report floor ({health_report.COGNITIVE_REPORT_FLOOR}) is not below "
        f"the complexipy gate ({gate}), so gated functions go unreported"
    )


def test_package_dir_anchors_on_the_measured_production_tree() -> None:
    """The module's path arithmetic resolves to the package it claims to measure.

    ``PACKAGE_DIR`` is derived from ``__file__`` by counting directory hops up
    to the repository root. Moving the report one directory in either direction
    leaves that expression valid and silently pointed at the wrong tree, where
    every dimension reports an empty table instead of failing.
    """
    assert health_report.REPO_ROOT == REPO_ROOT
    assert health_report.PACKAGE_DIR == REPO_ROOT / "src" / "vaultspec_core"
    assert (health_report.PACKAGE_DIR / "__init__.py").is_file()


def test_module_length_dimension_reports_the_real_longest_module(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The rendered table carries a measurement, not a placeholder.

    The line count is measured here from the filesystem by a second, independent
    walk; if the report's own walk, its ranking, or the rich rendering breaks,
    the number the test computed will not appear in what the report printed.
    """
    modules = _measured_modules()
    assert modules, "no python modules found under the measured package"
    with (max(modules, key=lambda path: sum(1 for _ in path.open("rb")))).open(
        "rb"
    ) as handle:
        longest = sum(1 for _ in handle)

    health_report.report_module_length(1)
    printed = capsys.readouterr().out

    assert "Module length" in printed
    assert str(longest) in printed, (
        f"the longest measured module has {longest} lines, which the report did "
        f"not print:\n{printed}"
    )
