#!/usr/bin/env python
"""Regenerate the README terminal renders under ``docs/assets/``.

Runs real CLI commands against a neutral, synthetic demo vault and exports
each capture as an SVG styled as the brand's documentation terminal. The
demo vault is built in a throwaway temporary directory with
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
frame and palette.

Usage::

    uv run --no-sync python -m docs._render.render_readme_assets [OUT_DIR]

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
from html import escape
from pathlib import Path
from string import Template

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

import vaultspec_core.console as vsconsole

# Force color even under CI/agent shells that export NO_COLOR; the
# recording consoles below are never a real terminal.
os.environ.pop("NO_COLOR", None)

# The brand's documentation terminal, which is dark in both page themes so
# one render serves both: grey-green ink on the dark mat, the brand green for
# success, ochre for warnings, and chalk blue for commands. The remaining ANSI
# slots are filled with cool tones at the same lightness.
VAULTSPEC_THEME = TerminalTheme(
    background=(20, 24, 22),
    foreground=(216, 223, 218),
    normal=[
        (15, 18, 17),
        (229, 122, 134),
        (111, 190, 139),
        (220, 160, 90),
        (132, 182, 214),
        (180, 166, 212),
        (114, 194, 196),
        (216, 223, 218),
    ],
    bright=[
        (141, 153, 145),
        (240, 154, 163),
        (138, 207, 162),
        (232, 183, 117),
        (163, 201, 227),
        (201, 189, 227),
        (147, 211, 211),
        (241, 244, 241),
    ],
)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# The working directory the stills' title bar names. The demo vault lives in a
# throwaway temp directory, so the bar shows a neutral project path instead.
DEMO_CWD = "~/code/editor"

TERM_BAR = "#1e2321"
TERM_FAINT = "#8d9991"
TERM_RULE = "#3c4541"
FONT_STACK = (
    "'IBM Plex Mono', 'Cascadia Mono', 'Cascadia Code', ui-monospace, Menlo, "
    "Consolas, 'DejaVu Sans Mono', monospace"
)

# Frame geometry in SVG units. Rich fixes a 20-unit character height and a
# 1.22 line pitch; the aspect ratio is passed to it so both sides share it.
FONT_ASPECT = 0.61
CHAR_WIDTH = 20 * FONT_ASPECT
LINE_HEIGHT = 20 * 1.22
PAD_X = 28
BAR_HEIGHT = 50
PAD_TOP = 26
PAD_BOTTOM = 30
RADIUS = 14

# Replaces rich's default template, whose chrome draws a macOS window with
# three traffic-light buttons. `$` fields are filled here; `{}` fields are
# rich's own, filled by export_svg.
SVG_FRAME = Template("""\
<svg class="rich-terminal" viewBox="0 0 $width $height" xmlns="http://www.w3.org/2000/svg">
    <style>
    .{unique_id}-matrix {{
        font-family: $font;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}
    .{unique_id}-bar {{
        font-family: $font;
        font-size: 17px;
        fill: $faint;
    }}
    {styles}
    </style>
    <defs>
    <clipPath id="{unique_id}-clip-frame">
      <rect x="0" y="0" width="$width" height="$height" rx="$radius"/>
    </clipPath>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}"/>
    </clipPath>
    {lines}
    </defs>
    <g clip-path="url(#{unique_id}-clip-frame)">
    <rect width="$width" height="$height" fill="$background"/>
    <rect width="$width" height="$bar_height" fill="$bar"/>
    </g>
    <rect x="0.5" y="0.5" width="$outline_width" height="$outline_height"
        rx="$radius" fill="none" stroke="$rule"/>
    <text class="{unique_id}-bar" x="$pad_x" y="$bar_text_y">$left</text>
    <text class="{unique_id}-bar" x="$right_x" y="$bar_text_y"
        text-anchor="end">$right</text>
    <g transform="translate($pad_x, $body_y)"
        clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
""")

# ---------------------------------------------------------------------------
# Demo vault definition
# ---------------------------------------------------------------------------
#
# A tiny, fully-valid vault authored entirely from invented feature names so
# the published renders carry no real project development records. Each
# feature contributes a research, reference, ADR, and plan document; every
# checked Step is logged to its plan's ledger so the status view reads as a
# tracked project rather than a wall of "record missing" flags. Each ADR
# states a concrete decision so the semantic-search render recalls a passage
# that answers its query.

_DemoStep = tuple[str, str, str, bool]  # (step_id, action, path, checked)
_DemoPhase = tuple[str, str, str, list[_DemoStep]]  # (phase_id, slug, intent, steps)
# (feature, title, date, decision, phases)
_DemoFeature = tuple[str, str, str, str, list[_DemoPhase]]

_DEMO_FEATURES: list[_DemoFeature] = [
    (
        "editor-demo",
        "Editor Demo",
        "2026-02-04",
        "Parse markdown with a hand-written tokeniser that emits a tree of block "
        "and inline nodes, so the canvas renderer and the live preview share one "
        "document model instead of each re-parsing the source text.",
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
        "Measure column tracks once per container resize and place blocks into "
        "the resolved tracks, rather than reflowing the whole page on every edit.",
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
        "Colour fenced code by scopes from a per-language grammar table, loaded "
        "on first use, and keep that tokeniser separate from the markdown parser.",
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

    The framework content is seeded first because the ledger is written by
    the same verb an executor uses, and that verb scaffolds from the
    deployed template mirror.
    """
    from vaultspec_core.builtins import seed_builtins
    from vaultspec_core.vaultcore.exec_log import LogRequest, log_step, parse_row_spec

    vault = root / ".vault"
    seed_builtins(root / ".vaultspec")

    for feature, title, date, decision, phases in _DEMO_FEATURES:
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
            f"## Decision\n\n{decision}\n",
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

        # Log each checked Step to the plan's ledger so status reads as
        # tracked work.
        for phase_id, _slug, _intent, steps in phases:
            for step_id, _action, path, checked in steps:
                if checked:
                    log_step(
                        root,
                        LogRequest(
                            feature=feature,
                            plan_stem=plan,
                            step=f"{phase_id}.{step_id}",
                            rows=(parse_row_spec(f"A:{path}"),),
                        ),
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

    from typer.testing import CliRunner

    from vaultspec_core.cli.root import app

    with vsconsole.override_console(rec):
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
        # The demo root is always a project the service has never seen, and
        # the service refuses an incremental index of a project with no prior
        # generation; a rebuild is the explicit first build.
        queued = subprocess.run(
            [exe, "--target", demo_root, "index", "--type", "vault", "--rebuild"],
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
    cwd: str = DEMO_CWD,
) -> None:
    """Export captured ANSI text as a brand-styled terminal SVG.

    The title bar names *cwd* on the left and the command, *title*, on the
    right.
    """
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
    rows = len(lines) + int(truncated)
    svg = out.export_svg(
        title=title,
        theme=VAULTSPEC_THEME,
        font_aspect_ratio=FONT_ASPECT,
        code_format=svg_frame(rows, width, left=cwd, right=title),
    )
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print(f"wrote {out_path} ({len(lines)} lines)")


def svg_frame(rows: int, columns: int, *, left: str, right: str) -> str:
    """Return the rich ``code_format`` for a *rows* by *columns* terminal."""
    width = PAD_X * 2 + CHAR_WIDTH * columns
    height = BAR_HEIGHT + PAD_TOP + LINE_HEIGHT * rows + PAD_BOTTOM

    def bar_text(text: str) -> str:
        # Rich formats the result with str.format, so literal braces double.
        return escape(text).replace("{", "{{").replace("}", "}}")

    return SVG_FRAME.substitute(
        width=f"{width:g}",
        height=f"{height:g}",
        outline_width=f"{width - 1:g}",
        outline_height=f"{height - 1:g}",
        radius=RADIUS,
        font=FONT_STACK,
        faint=TERM_FAINT,
        background=VAULTSPEC_THEME.background_color.hex,
        bar=TERM_BAR,
        bar_height=BAR_HEIGHT,
        rule=TERM_RULE,
        pad_x=PAD_X,
        right_x=f"{width - PAD_X:g}",
        bar_text_y=BAR_HEIGHT // 2 + 6,
        body_y=BAR_HEIGHT + PAD_TOP,
        left=bar_text(left),
        right=bar_text(right),
    )


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
