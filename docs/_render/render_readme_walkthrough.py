#!/usr/bin/env python
"""Render the terminal stills of the README feature walkthrough.

Plays the scripted feature build in :mod:`docs._render.walkthrough` and draws
the stages the README shows (:data:`STILLS`) as terminal windows: a dim comment
naming what the stage does, then every command it runs at a prompt, each
followed by the command's own output.
Commands longer than the window wrap at their options with a shell ``\\``
continuation, so a reader can copy them as shown. Output lines longer than the
window are ellipsis-trimmed, exactly as :func:`render_svg` trims the other
stills; the palette and window chrome are shared with them.

The cross-reference stage runs against a local stand-in for the TypeSafe API
(see :mod:`docs._render.walkthrough`), and its still says so.

Usage::

    uv run --no-sync python -m docs._render.render_readme_walkthrough [OUT_DIR]

``OUT_DIR`` defaults to ``docs/assets/walkthrough``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from docs._render.render_readme_assets import VAULTSPEC_THEME, render_svg
from docs._render.walkthrough import WIDTH, walkthrough

if TYPE_CHECKING:
    from docs._render.walkthrough import Command, Stage


def _fg(rgb: tuple[int, int, int]) -> str:
    return "\x1b[38;2;{};{};{}m".format(*rgb)


TEAL = _fg(VAULTSPEC_THEME.ansi_colors[6])
DIM = _fg(VAULTSPEC_THEME.ansi_colors[8])
BOLD = "\x1b[1m"
RESET = "\x1b[0m"
PROMPT = "\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT}"
CONTINUATION = "    "

#: The stages the README shows, by slug. Installing has its own README section,
#: the research still reads like the decision's, and a clean check is a column
#: of ``ok`` lines better stated in prose; the video shows all of them.
STILLS = (
    "03-decide",
    "04-crossref",
    "05-plan",
    "06-execute",
    "08-status",
    "09-graph",
)

#: What the cross-reference still says about where its judgments came from.
STAND_IN_NOTE = (
    "# Judged here by a local stand-in for the TypeSafe API.",
    "# Set VAULTSPEC_CORE_TYPESAFE_API_KEY for live judgments.",
)


def wrap_command(command: Command, width: int = WIDTH) -> list[str]:
    """Break *command* into shell lines that fit the window.

    Lines break only between :meth:`Command.groups`, so an option stays with
    its value, and every line but the last ends in a ``\\`` continuation a
    shell accepts. A group wider than the window stays whole.
    """
    lines: list[str] = []
    for group in command.groups():
        # The first line sits after the prompt glyph; later ones are indented.
        lead = 2 if len(lines) <= 1 else len(CONTINUATION)
        if lines and lead + len(f"{lines[-1]} {group} \\") <= width:
            lines[-1] += f" {group}"
        elif lines:
            lines[-1] += " \\"
            lines.append(group)
        else:
            lines.append(group)
    return lines


def output_lines(output: str) -> list[str]:
    """Drop blank lines at either end and collapse runs of them to one."""
    lines: list[str] = []
    for line in output.splitlines():
        blank = not line.strip() or line.strip() == RESET
        if blank and (not lines or not lines[-1]):
            continue
        lines.append("" if blank else line)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def compose(stage: Stage) -> str:
    """Return the stage as one terminal session, in ANSI."""
    lines = [f"{DIM}# {stage.caption}{RESET}"]
    for command in stage.commands:
        lines.append("")
        for index, part in enumerate(wrap_command(command)):
            lead = f"{TEAL}{PROMPT}{RESET} " if index == 0 else CONTINUATION
            lines.append(f"{lead}{BOLD}{part}{RESET}")
        lines.extend(output_lines(command.output))
    if stage.stand_in:
        lines += ["", *(f"{DIM}{note}{RESET}" for note in STAND_IN_NOTE)]
    return "\n".join(lines) + "\n"


def main() -> None:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets/walkthrough")
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    with walkthrough() as stages:
        by_slug = {stage.slug: stage for stage in stages}
        missing = sorted(set(STILLS) - set(by_slug))
        if missing:
            raise SystemExit(f"error: the walkthrough has no stage {missing}")
        for slug in STILLS:
            stage = by_slug[slug]
            render_svg(compose(stage), str(outdir / f"{slug}.svg"), stage.title, WIDTH)


if __name__ == "__main__":
    main()
