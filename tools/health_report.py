"""Aggregate code-health report for ``src/vaultspec_core``.

Prints one readable report covering every health dimension, grouping the worst
offenders per dimension. ALWAYS exits 0 - this is the measurement instrument
for the remediation campaign, not a gate. Gates live in:

- ``[tool.complexipy]``          (cognitive complexity, baseline-calibrated)
- ``[tool.pylint]``              (module length + class shape, baseline-calibrated)
- ``[tool.ruff.lint.pylint]``    (function-size limits, baseline-calibrated)
- ``[tool.ruff.lint.mccabe]``    (cyclomatic complexity, baseline-calibrated)
- ``ty`` / ``basedpyright``      (type checking)

Every gate is configured declaratively in ``pyproject.toml`` and invoked
directly by a ``just lint`` recipe. This module is the one place that composes
them, and it exists to rank offenders across dimensions - not to re-implement
any threshold, which would let the report and the gate disagree.

Dimensions reported here:

1. Cyclomatic complexity   (radon ``cc`` - worst blocks)
2. Cognitive complexity    (complexipy - worst functions)
3. Function-size limits    (ruff PLR091x/PLR1702 vs upstream DEFAULTS)
4. Module length           (physical LOC - longest modules)
5. Maintainability index   (radon ``mi`` - lowest-ranked modules)
6. Strict type checking    (basedpyright strict)

radon is used through its Python API (``radon.complexity`` / ``radon.metrics``)
rather than its CLI: the CLI feeds every ``[tool.*]`` table of pyproject.toml
into a ``%``-interpolating configparser and crashes on the pytest log formats.
The API path has no config discovery.

Usage:
    uv run --no-sync python tools/health_report.py [--top N] [--fast] [--census]

``--fast`` skips the basedpyright section (it is the slowest by far).
``--census`` prints the threshold distributions used to calibrate each
baseline ratchet in ``pyproject.toml`` instead of the offender tables.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from complexipy import file_complexity
from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_rank, mi_visit
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "vaultspec_core"

COGNITIVE_REPORT_FLOOR = 10  # report functions above this; the gate is at 20

console = Console()


def _python_files(production_only: bool = False) -> list[Path]:
    return [
        path
        for path in sorted(PACKAGE_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not (production_only and "tests" in path.parts)
    ]


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _section(title: str, mode: str) -> None:
    console.rule(f"[bold]{title}[/bold]  [dim]({mode})[/dim]")


def _distribution(values: list[int], thresholds: list[int]) -> list[tuple[int, int]]:
    """Count how many measured items sit above each candidate threshold."""
    return [(t, sum(1 for value in values if value > t)) for t in thresholds]


def report_cyclomatic(top: int) -> None:
    _section(
        "Cyclomatic complexity (radon cc)",
        "gated by ruff C90 via [tool.ruff.lint.mccabe] and by xenon ranks",
    )
    blocks: list[tuple[int, str, str]] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for block in cc_visit(source):
            blocks.append((block.complexity, block.name, _rel(path)))
    blocks.sort(reverse=True)

    table = Table(show_header=True, header_style="bold")
    table.add_column("CC", justify="right")
    table.add_column("Grade")
    table.add_column("Block")
    table.add_column("Module")
    for complexity, name, module in blocks[:top]:
        table.add_row(str(complexity), cc_rank(complexity), name, module)
    console.print(table)


def report_cognitive(top: int) -> None:
    """Rank the worst cognitive-complexity functions across the whole tree.

    The gate in ``[tool.complexipy]`` measures production only; this reports the
    test tree alongside it, because the two populations differ enough that
    collapsing them hides which one a hotspot belongs to.
    """
    _section(
        "Cognitive complexity (complexipy)",
        f"production gated via [tool.complexipy]; reporting > "
        f"{COGNITIVE_REPORT_FLOOR} across the whole tree",
    )
    findings: list[tuple[int, str, str]] = []
    for path in _python_files():
        scope = "test" if "tests" in path.parts else "prod"
        for function in file_complexity(str(path)).functions:
            if function.complexity > COGNITIVE_REPORT_FLOOR:
                findings.append(
                    (
                        function.complexity,
                        scope,
                        f"{_rel(path)}:{function.line_start} {function.name}",
                    )
                )
    findings.sort(reverse=True)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Cognitive", justify="right")
    table.add_column("Scope")
    table.add_column("Module:line Function")
    for value, scope, location in findings[:top]:
        table.add_row(str(value), scope, location)
    console.print(table)


def _function_limit_findings() -> list[tuple[int, str, str, str]]:
    """Run ruff's size rules at UPSTREAM defaults and return every finding."""
    defaults = {
        "lint.pylint.max-args": 5,
        "lint.pylint.max-returns": 6,
        "lint.pylint.max-branches": 12,
        "lint.pylint.max-statements": 50,
        "lint.pylint.max-nested-blocks": 5,
        "lint.mccabe.max-complexity": 10,
    }
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "src",
        "--select",
        "PLR0911,PLR0912,PLR0913,PLR0915,PLR1702,C901",
        "--preview",
        "--output-format",
        "json",
        "--exit-zero",
    ]
    for key, value in defaults.items():
        cmd.extend(["--config", f"{key}={value}"])
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    diagnostics = json.loads(result.stdout or "[]")

    value_pattern = re.compile(r"\((\d+) > \d+\)")
    findings: list[tuple[int, str, str, str]] = []
    for item in diagnostics:
        match = value_pattern.search(item["message"])
        value = int(match.group(1)) if match else 0
        module = Path(item["filename"]).resolve()
        location = f"{_rel(module)}:{item['location']['row']}"
        findings.append((value, item["code"], item["message"], location))
    findings.sort(reverse=True)
    return findings


def report_function_limits(top: int) -> None:
    _section(
        "Function-size limits (ruff PLR091x / C901 vs upstream defaults)",
        "gated at baseline via [tool.ruff.lint.pylint] and [tool.ruff.lint.mccabe]",
    )
    findings = _function_limit_findings()
    counts: Counter[str] = Counter(code for _, code, _, _ in findings)

    summary = ", ".join(f"{code}={count}" for code, count in sorted(counts.items()))
    console.print(f"violations vs upstream defaults: {summary or 'none'}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Rule")
    table.add_column("Message")
    table.add_column("Module:line")
    for value, code, message, location in findings[:top]:
        table.add_row(str(value), code, message, location)
    console.print(table)


def report_module_length(top: int) -> None:
    _section(
        "Module length (physical LOC)",
        "gated by pylint C0302 via [tool.pylint.format] (production only)",
    )
    lengths: list[tuple[int, str]] = []
    for path in _python_files():
        with path.open("rb") as handle:
            lengths.append((sum(1 for _ in handle), _rel(path)))
    lengths.sort(reverse=True)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Lines", justify="right")
    table.add_column("Module")
    for line_count, module in lengths[:top]:
        table.add_row(str(line_count), module)
    console.print(table)


def report_maintainability(top: int) -> None:
    _section(
        "Maintainability index (radon mi)",
        "report-only (informational ranking, lower is worse)",
    )
    scores: list[tuple[float, str]] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        scores.append((mi_visit(source, multi=True), _rel(path)))
    scores.sort()

    table = Table(show_header=True, header_style="bold")
    table.add_column("MI", justify="right")
    table.add_column("Rank")
    table.add_column("Module")
    for score, module in scores[:top]:
        table.add_row(f"{score:.2f}", mi_rank(score), module)
    console.print(table)


def report_strict_types(top: int) -> None:
    _section(
        "Strict type checking (basedpyright strict)",
        "advisory until the burndown reaches zero; ty remains the fast gate",
    )
    executable = shutil.which("basedpyright")
    if executable is None:
        console.print(
            "[yellow]basedpyright not found on PATH - run "
            "`uv sync --locked --group dev`[/yellow]"
        )
        return
    result = subprocess.run(
        [executable, "--outputjson"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        console.print("[red]basedpyright produced no parseable output[/red]")
        console.print(result.stderr[:2000])
        return

    summary = payload.get("summary", {})
    console.print(
        f"files analyzed: {summary.get('filesAnalyzed', '?')}  "
        f"errors: {summary.get('errorCount', '?')}  "
        f"warnings: {summary.get('warningCount', '?')}"
    )
    per_file: Counter[str] = Counter()
    per_rule: Counter[str] = Counter()
    for diagnostic in payload.get("generalDiagnostics", []):
        if diagnostic.get("severity") == "error":
            per_file[diagnostic.get("file", "?")] += 1
            per_rule[diagnostic.get("rule", "(no rule)")] += 1

    rules = Table(show_header=True, header_style="bold")
    rules.add_column("Errors", justify="right")
    rules.add_column("Rule")
    for rule, count in per_rule.most_common(top):
        rules.add_row(str(count), rule)
    console.print(rules)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Errors", justify="right")
    table.add_column("Module")
    for file_name, count in per_file.most_common(top):
        module = Path(file_name)
        label = _rel(module) if module.is_absolute() else file_name
        table.add_row(str(count), label)
    console.print(table)


def report_census() -> None:
    """Print the distributions each baseline ratchet in pyproject.toml is set from.

    Every gate here is calibrated at the current worst offender so it is green
    on landing and can only be lowered. This is the measurement that justifies
    each number, and the census comment beside it.
    """
    console.rule("[bold]Baseline census[/bold]  [dim](production only)[/dim]")

    cognitive: list[int] = []
    for path in _python_files(production_only=True):
        cognitive.extend(f.complexity for f in file_complexity(str(path)).functions)
    console.print(f"\n[bold]Cognitive complexity[/bold] (worst {max(cognitive)})")
    for threshold, count in _distribution(cognitive, [30, 25, 20, 18, 16, 15]):
        console.print(f"  over {threshold:>4}: {count:>4} functions")

    cyclomatic: list[int] = []
    for path in _python_files(production_only=True):
        source = path.read_text(encoding="utf-8")
        cyclomatic.extend(block.complexity for block in cc_visit(source))
    console.print(f"\n[bold]Cyclomatic complexity[/bold] (worst {max(cyclomatic)})")
    for threshold, count in _distribution(cyclomatic, [25, 20, 15, 12, 10]):
        console.print(f"  over {threshold:>4}: {count:>4} blocks")

    lengths = [
        sum(1 for _ in path.open("rb")) for path in _python_files(production_only=True)
    ]
    console.print(
        f"\n[bold]Module length[/bold] "
        f"({len(lengths)} production modules, longest {max(lengths)})"
    )
    for threshold, count in _distribution(lengths, [2000, 1500, 1200, 1000, 500]):
        console.print(f"  over {threshold:>4}: {count:>4} modules")

    console.print("\n[bold]Function-size limits[/bold] (worst value per ruff rule)")
    worst: dict[str, int] = {}
    for value, code, _, _ in _function_limit_findings():
        worst[code] = max(worst.get(code, 0), value)
    for code, value in sorted(worst.items()):
        console.print(f"  {code}: worst {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="worst offenders to list per dimension (default 10)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip the basedpyright section (slowest dimension)",
    )
    parser.add_argument(
        "--census",
        action="store_true",
        help="print baseline-calibration distributions instead of offender tables",
    )
    args = parser.parse_args()

    if args.census:
        report_census()
        return 0

    console.print(
        "[bold]vaultspec-core code-health report[/bold] "
        "[dim](measurement only - always exits 0)[/dim]"
    )
    report_cyclomatic(args.top)
    report_cognitive(args.top)
    report_function_limits(args.top)
    report_module_length(args.top)
    report_maintainability(args.top)
    if not args.fast:
        report_strict_types(args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
