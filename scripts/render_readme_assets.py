#!/usr/bin/env python
"""Regenerate the README terminal renders under ``docs/assets/``.

Runs real CLI commands against a neutral, synthetic demo vault and exports
each capture as a rich terminal-window SVG themed on the vaultspec logo
palette. The demo vault is built in a throwaway temporary directory with
invented feature names (``editor-demo``, ``grid-layout``,
``syntax-highlighting``) so the published screenshots never embed a real
project's own development records. ``vaultspec-core`` commands run
in-process by swapping a recording :class:`rich.console.Console` into the
shared console singleton (:mod:`vaultspec_core.console`); ``vaultspec-rag``
runs as a subprocess against the global executable, which indexes the demo
vault on the search service before searching it, and is skipped with a
warning when the semantic-search backend is unavailable or the demo index
does not populate.

Output is genuine command output over the demo vault; rendering only trims
length (a dim ellipsis marks truncation) and applies the brand terminal
theme.

Usage::

    uv run --no-sync python scripts/render_readme_assets.py [OUT_DIR]

``OUT_DIR`` defaults to ``docs/assets``.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

import vaultspec_core.console as vsconsole

# Force color even under CI/agent shells that export NO_COLOR; the
# recording consoles below are never a real terminal.
os.environ.pop("NO_COLOR", None)

# Palette derived from the vaultspec logo, light variant: warm charcoal
# foreground on cream paper, with the sage / teal / sand / dusty-rose /
# lavender accents darkened to keep contrast on the light ground.
VAULTSPEC_THEME = TerminalTheme(
    background=(250, 247, 242),
    foreground=(30, 27, 24),
    normal=[
        (30, 27, 24),
        (166, 92, 92),
        (106, 122, 77),
        (163, 122, 58),
        (86, 108, 158),
        (124, 106, 156),
        (74, 124, 116),
        (94, 86, 78),
    ],
    bright=[
        (145, 137, 129),
        (146, 72, 72),
        (88, 104, 60),
        (140, 102, 42),
        (66, 88, 140),
        (104, 86, 138),
        (56, 106, 98),
        (30, 27, 24),
    ],
)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Rich hardcodes a white window border, invisible around a light terminal
# on a light page; render_svg swaps it for a soft warm-charcoal line. The
# literal lives inside rich's export_svg, so a rich upgrade can change it.
RICH_STROKE = 'stroke="rgba(255,255,255,0.35)"'
LIGHT_STROKE = 'stroke="rgba(30,27,24,0.22)"'

# ---------------------------------------------------------------------------
# Demo vault definition
# ---------------------------------------------------------------------------
#
# A tiny, fully-valid vault authored entirely from invented feature names so
# the published renders carry no real project development records. Each
# feature contributes a research, reference, ADR, and plan document; every
# checked Step also gets an execution record so the status view reads as a
# tracked project rather than a wall of "record missing" flags.

_DemoStep = tuple[str, str, str, bool]  # (step_id, action, path, checked)
_DemoPhase = tuple[str, str, str, list[_DemoStep]]  # (phase_id, slug, intent, steps)
_DemoFeature = tuple[str, str, str, list[_DemoPhase]]  # (feature, title, date, phases)

_DEMO_FEATURES: list[_DemoFeature] = [
    (
        "editor-demo",
        "Editor Demo",
        "2026-02-04",
        [
            (
                "P01",
                "foundation",
                "Establish the document model and the markdown parser.",
                [
                    (
                        "S01",
                        "define the block and inline node types",
                        "src/editor/model.ts",
                        True,
                    ),
                    (
                        "S02",
                        "tokenise markdown into the block model",
                        "src/editor/parser.ts",
                        True,
                    ),
                ],
            ),
            (
                "P02",
                "rendering",
                "Paint the block tree and wire the live preview.",
                [
                    (
                        "S03",
                        "paint the block tree to the canvas",
                        "src/editor/renderer.ts",
                        True,
                    ),
                    (
                        "S04",
                        "reflect edits into the preview on keystroke",
                        "src/editor/preview.ts",
                        False,
                    ),
                ],
            ),
        ],
    ),
    (
        "grid-layout",
        "Grid Layout",
        "2026-02-05",
        [
            (
                "P01",
                "engine",
                "Build the responsive grid measurement engine.",
                [
                    (
                        "S01",
                        "measure column tracks from the container",
                        "src/grid/measure.ts",
                        True,
                    ),
                    (
                        "S02",
                        "place blocks into the resolved tracks",
                        "src/grid/place.ts",
                        True,
                    ),
                ],
            ),
        ],
    ),
    (
        "syntax-highlighting",
        "Syntax Highlighting",
        "2026-02-06",
        [
            (
                "P01",
                "tokeniser",
                "Wire a grammar-driven code tokeniser.",
                [
                    (
                        "S01",
                        "load the language grammar table",
                        "src/highlight/grammar.ts",
                        True,
                    ),
                    (
                        "S02",
                        "colour tokens by scope in the preview",
                        "src/highlight/paint.ts",
                        False,
                    ),
                ],
            ),
        ],
    ),
]


def _frontmatter(
    doc_type: str,
    feature: str,
    date: str,
    related: list[str],
    extra: str = "",
) -> str:
    """Render two-tag YAML frontmatter with quoted ISO dates."""
    if related:
        rel = "related:\n" + "\n".join(f'  - "[[{r}]]"' for r in related)
    else:
        rel = "related: []"
    return (
        f'---\ntags:\n  - "#{doc_type}"\n  - "#{feature}"\n'
        f"date: '{date}'\nmodified: '{date}'\n{extra}{rel}\n---\n"
    )


def _write(vault: Path, doc_type: str, stem: str, front: str, body: str) -> None:
    """Write a single vault document under ``vault/<doc_type>/``."""
    directory = vault / doc_type
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.md").write_text(front + "\n" + body, encoding="utf-8")


def build_demo_vault(root: Path) -> None:
    """Author a small, fully-valid demo vault under ``root/.vault``.

    The corpus is deliberately neutral: invented feature names, no real
    project records. It parses cleanly under ``vault check all`` and drives
    a representative ``status``/``graph``/``check`` render.
    """
    vault = root / ".vault"
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)

    for feature, title, date, phases in _DEMO_FEATURES:
        research = f"{date}-{feature}-research"
        reference = f"{date}-{feature}-reference"
        adr = f"{date}-{feature}-adr"
        plan = f"{date}-{feature}-plan"

        _write(
            vault,
            "research",
            research,
            _frontmatter("research", feature, date, []),
            f"# `{feature}` research: `{title}`\n\nExplores the problem space.\n",
        )
        _write(
            vault,
            "reference",
            reference,
            _frontmatter("reference", feature, date, []),
            f"# `{feature}` reference: `{title}`\n\nGrounds the work in code.\n",
        )
        _write(
            vault,
            "adr",
            adr,
            _frontmatter("adr", feature, date, [research, reference]),
            f"# `{feature}` adr: `{title}` | (**status:** `accepted`)\n\n"
            "## Decision\n\nThe approach is adopted.\n",
        )

        # Plan body: an L2 structure with canonical Phase/Step rows.
        lines = [
            f"# `{feature}` plan",
            "",
            "## Description",
            "",
            f"Deliver the {title.lower()} feature end to end.",
            "",
            "## Steps",
            "",
        ]
        for phase_id, slug, intent, steps in phases:
            lines += [f"### Phase `{phase_id}` - {slug}", "", intent, ""]
            for step_id, action, path, checked in steps:
                box = "x" if checked else " "
                lines.append(f"- [{box}] `{phase_id}.{step_id}` - {action}; `{path}`.")
            lines.append("")
        _write(
            vault,
            "plan",
            plan,
            _frontmatter("plan", feature, date, [adr, research], extra="tier: L2\n"),
            "\n".join(lines) + "\n",
        )

        # Execution record per checked Step so status reads as tracked work.
        exec_dir = vault / "exec" / f"{date}-{feature}"
        for phase_id, _slug, _intent, steps in phases:
            for step_id, action, _path, checked in steps:
                if not checked:
                    continue
                stem = f"{date}-{feature}-{phase_id}-{step_id}"
                front = _frontmatter(
                    "exec",
                    feature,
                    date,
                    [plan],
                    extra=f"step_id: {step_id}\n",
                )
                exec_dir.mkdir(parents=True, exist_ok=True)
                (exec_dir / f"{stem}.md").write_text(
                    front + f"\n# `{feature}` exec: `{action}`\n\nCompleted.\n",
                    encoding="utf-8",
                )


def _recording_console(width: int) -> Console:
    return Console(
        record=True,
        width=width,
        force_terminal=True,
        legacy_windows=False,
        highlight=False,
        soft_wrap=True,
        file=io.StringIO(),
    )


def run_core(args: list[str], width: int) -> str:
    """Run a ``vaultspec-core`` command in-process, return recorded ANSI text."""
    rec = _recording_console(width)
    vsconsole._console = rec

    from typer.testing import CliRunner

    from vaultspec_core.cli.root import app

    CliRunner().invoke(app, args, catch_exceptions=False)
    return rec.export_text(styles=True)


def resolve_rag() -> str | None:
    """Locate the ``vaultspec-rag`` executable, preferring a global install.

    Under ``uv run`` the active virtualenv's script directory is prepended to
    ``PATH`` and can shadow the global ``vaultspec-rag`` with a copy whose
    optional search backend is not installed. Drop the venv script directory
    from the lookup so the provisioned global CLI wins, and fall back to a
    bare lookup when that finds nothing.
    """
    venv_bin = Path(sys.executable).parent
    entries = [
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and Path(entry) != venv_bin
    ]
    return shutil.which("vaultspec-rag", path=os.pathsep.join(entries)) or shutil.which(
        "vaultspec-rag"
    )


def index_demo_vault(exe: str, demo_root: str, timeout: float = 90.0) -> bool:
    """Index the demo vault on the search service and wait for it to land.

    The service indexes asynchronously, so the ``index`` call only queues a
    job; poll ``status`` until the vault documents become queryable. Returns
    ``True`` once they are, ``False`` when the backend is unavailable or the
    index does not populate within *timeout* seconds.
    """
    try:
        queued = subprocess.run(
            [exe, "--target", demo_root, "index", "--type", "vault"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"warning: skipping vaultspec-rag render ({exc})", file=sys.stderr)
        return False
    if queued.returncode != 0:
        detail = queued.stdout.strip() or queued.stderr.strip()
        print(
            f"warning: skipping vaultspec-rag render (index refused: {detail})",
            file=sys.stderr,
        )
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(3)
        try:
            status = subprocess.run(
                [exe, "--target", demo_root, "status"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            continue
        for line in status.stdout.splitlines():
            if "Vault documents" in line:
                _, _, count = line.partition(":")
                if count.strip().isdigit() and int(count.strip()) > 0:
                    return True
    print(
        "warning: skipping vaultspec-rag render "
        "(demo vault did not finish indexing in time)",
        file=sys.stderr,
    )
    return False


def run_rag(exe: str, args: list[str], cwd: str) -> str | None:
    """Run a ``vaultspec-rag`` command in *cwd*, or ``None`` when unavailable."""
    try:
        proc = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"warning: skipping vaultspec-rag render ({exc})", file=sys.stderr)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        print(
            "warning: skipping vaultspec-rag render "
            "(no result over the demo vault; index the demo corpus to render it)",
            file=sys.stderr,
        )
        return None
    return proc.stdout


def render_svg(
    ansi: str,
    out_path: str,
    title: str,
    width: int,
    max_lines: int | None = None,
    start_match: str | None = None,
) -> None:
    """Export captured ANSI text as a themed terminal-window SVG."""
    lines = ansi.splitlines()
    if start_match is not None:
        for i, line in enumerate(lines):
            if start_match in ANSI_RE.sub("", line):
                lines = lines[i:]
                break
    while lines and not lines[-1].strip():
        lines.pop()
    truncated = max_lines is not None and len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        while lines and not lines[-1].strip():
            lines.pop()
    out = _recording_console(width)
    for line in lines:
        out.print(Text.from_ansi(line), no_wrap=True, overflow="ellipsis")
    if truncated:
        out.print(Text("  …", style="bright_black"))
    svg = out.export_svg(title=title, theme=VAULTSPEC_THEME)
    if RICH_STROKE not in svg:
        raise RuntimeError(
            "rich's window-border stroke literal changed; update RICH_STROKE"
        )
    svg = svg.replace(RICH_STROKE, LIGHT_STROKE)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out_path} ({len(lines)} lines)")


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "docs/assets"
    outdir = os.path.abspath(outdir)

    origin = Path.cwd()
    demo_root = Path(tempfile.mkdtemp(prefix="vaultspec-demo-vault-"))
    try:
        build_demo_vault(demo_root)
        os.chdir(demo_root)

        # Normalise the demo corpus the way a real workflow would: apply the
        # safe auto-fixes and regenerate the feature indexes before capture.
        run_core(["vault", "check", "all", "--fix"], 112)
        run_core(["vault", "feature", "index"], 112)

        render_svg(
            run_core(["status"], 112),
            f"{outdir}/term-status.svg",
            "vaultspec-core status",
            112,
            max_lines=13,
        )
        render_svg(
            run_core(["vault", "graph", "--feature", "editor-demo"], 200),
            f"{outdir}/term-graph.svg",
            "vaultspec-core vault graph --feature editor-demo",
            112,
        )
        render_svg(
            run_core(["vault", "check", "all"], 112),
            f"{outdir}/term-check.svg",
            "vaultspec-core vault check all",
            112,
            max_lines=40,
            start_match="Vault Check",
        )
        rag_query = "how the parser tokenises markdown into blocks"
        rag_exe = resolve_rag()
        rag_out: str | None = None
        if rag_exe is None:
            print(
                "warning: skipping vaultspec-rag render (executable not found on PATH)",
                file=sys.stderr,
            )
        elif index_demo_vault(rag_exe, str(demo_root)):
            rag_out = run_rag(
                rag_exe,
                [
                    "--target",
                    str(demo_root),
                    "search",
                    rag_query,
                    "--type",
                    "vault",
                    "--doc-type",
                    "adr",
                ],
                cwd=str(demo_root),
            )
        if rag_out:
            render_svg(
                rag_out,
                f"{outdir}/term-rag.svg",
                f'vaultspec-rag search "{rag_query}" --type vault --doc-type adr',
                112,
                max_lines=16,
            )
    finally:
        os.chdir(origin)
        with contextlib.suppress(OSError):
            _rmtree(demo_root)


def _rmtree(path: Path) -> None:
    """Best-effort recursive delete of the temporary demo vault."""
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()
