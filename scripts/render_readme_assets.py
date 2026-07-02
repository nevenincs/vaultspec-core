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

# Palette derived from the vaultspec logo: cream foreground on warm
# charcoal, with sage / teal / sand / dusty-rose / lavender accents.
VAULTSPEC_THEME = TerminalTheme(
    background=(30, 27, 24),
    foreground=(242, 236, 228),
    normal=[
        (30, 27, 24),
        (201, 138, 138),
        (163, 177, 138),
        (217, 185, 138),
        (138, 159, 201),
        (181, 168, 201),
        (143, 188, 181),
        (242, 236, 228),
    ],
    bright=[
        (110, 102, 94),
        (222, 160, 160),
        (185, 199, 160),
        (233, 205, 160),
        (160, 181, 222),
        (203, 190, 222),
        (165, 210, 203),
        (250, 247, 242),
    ],
)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


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
