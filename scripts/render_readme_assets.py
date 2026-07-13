#!/usr/bin/env python
"""Regenerate the README terminal renders under ``docs/assets/``.

Runs real CLI commands against this repository's own vault and exports
each capture as a rich terminal-window SVG themed on the vaultspec logo
palette. ``vaultspec-core`` commands run in-process by swapping a
recording :class:`rich.console.Console` into the shared console
singleton (:mod:`vaultspec_core.console`); ``vaultspec-rag`` runs as a
subprocess and is skipped with a warning when not installed.

Output is genuine command output; rendering only trims length (a dim
ellipsis marks truncation) and applies the brand terminal theme.

Usage::

    uv run --no-sync python scripts/render_readme_assets.py [OUT_DIR]

``OUT_DIR`` defaults to ``docs/assets``.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys

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


def run_rag(args: list[str]) -> str | None:
    """Run a ``vaultspec-rag`` command, or ``None`` when unavailable."""
    try:
        proc = subprocess.run(
            ["vaultspec-rag", *args], capture_output=True, text=True, timeout=120
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"warning: skipping vaultspec-rag render ({exc})", file=sys.stderr)
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

    render_svg(
        run_core(["status"], 112),
        f"{outdir}/term-status.svg",
        "vaultspec-core status",
        112,
        max_lines=13,
    )
    render_svg(
        run_core(["vault", "graph", "--feature", "curator-reframe"], 200),
        f"{outdir}/term-graph.svg",
        "vaultspec-core vault graph --feature curator-reframe",
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
    rag_query = "rollback journal for feature rename"
    rag_out = run_rag(["search", rag_query, "--type", "vault", "--doc-type", "adr"])
    if rag_out:
        render_svg(
            rag_out,
            f"{outdir}/term-rag.svg",
            f'vaultspec-rag search "{rag_query}" --type vault --doc-type adr',
            112,
            max_lines=16,
        )


if __name__ == "__main__":
    main()
