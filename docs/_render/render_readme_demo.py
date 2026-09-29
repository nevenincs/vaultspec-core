#!/usr/bin/env python
"""Regenerate the README pipeline demo GIF under ``docs/assets/``.

Builds a disposable demo project in a temp directory, runs the real
pipeline commands against it (provision, scaffold research -> ADR ->
plan, check, graph, status), and captures each command's genuine
output in-process (see :mod:`docs._render.render_readme_assets` for the
recording-console technique). The captures are stitched into a
synthesized asciicast v2 stream - typed prompts, streamed output, a
comment beat for the off-screen drafting and first Step - and rendered to
GIF with `agg <https://github.com/asciinema/agg>`_ themed on the
vaultspec logo palette.

The only edits to the captured output are cosmetic: the temp directory
path is redacted to ``~/code/search-api``, Windows path separators are
shown as ``/``, and over-long lines are ellipsis-trimmed to the terminal
width.

Usage::

    uv run --no-sync python -m docs._render.render_readme_demo [OUT_GIF]

Run as a MODULE, not as a file path. This module imports its sibling
:mod:`docs._render.render_readme_assets` for the shared palette, and only
``-m`` gives that import a package context to resolve against; executing the
file directly puts ``docs/_render`` rather than the repository root on
``sys.path``, which leaves the sibling reachable only as the implicit-relative
import basedpyright's ``reportImplicitRelativeImport`` rejects.
``dev/toolchain.py``'s ``docs`` verb invokes it this way.

``OUT_GIF`` defaults to ``docs/assets/demo.gif``. Requires the ``agg``
binary on PATH (or set ``AGG`` to its location).
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from rich.console import Console
from rich.text import Text

import vaultspec_core.console as vsconsole
from docs._render.render_readme_assets import VAULTSPEC_THEME

os.environ.pop("NO_COLOR", None)

COLS = 112
ROWS = 30
FEATURE = "search-api"
REDACTED = "~/code/search-api"
# The prompt shows the command form the README tells readers to type; the
# captured output is the same in-process CLI either way.
CLI = "uvx vaultspec-core"

RESEARCH_SECTIONS = {
    "Findings": "Postgres `tsvector` columns with a GIN index rank keyword matches "
    "inside the existing database. A dedicated engine adds a second store to "
    "keep in sync with every write.",
    "Sources": "https://www.postgresql.org/docs/current/textsearch.html",
}
ADR_SECTIONS = {
    "Problem Statement": "Clients cannot search document text; they page "
    "through every record.",
    "Considerations": "Results must stay consistent with writes.",
    "Considered options": "Postgres full-text search, or a dedicated search engine.",
    "Constraints": "No new service to operate.",
    "Implementation": "A generated `tsvector` column with a GIN index, queried "
    "from `GET /search`.",
    "Rationale": "Search stays transactional with the data it indexes.",
    "Consequences": "Ranking is simpler than a dedicated engine's.",
}
PLAN_SECTIONS = {
    "Description": "Serve ranked full-text search over documents.",
    "Parallelization": "Sequential: `S02` queries the index `S01` creates.",
    "Verification": "`pytest tests/test_search.py` passes on a seeded database.",
}
# (action, scope) per Step, authored through `vault plan step add`.
PLAN_STEPS = [
    (
        "Add a generated tsvector column and GIN index to documents",
        "migrations/0012_search_index.sql",
    ),
    ("Serve ranked results from GET /search", "api/search.py"),
]


def _hex(rgb: tuple[int, int, int]) -> str:
    return "".join(f"{c:02x}" for c in rgb)


def _fg(rgb: tuple[int, int, int]) -> str:
    return "\x1b[38;2;{};{};{}m".format(*rgb)


# Derived from the single palette source in render_readme_assets so the
# demo GIF and the SVG stills can never drift apart.
TEAL = _fg(VAULTSPEC_THEME.ansi_colors[6])
DIM = _fg(VAULTSPEC_THEME.ansi_colors[8])
RESET = "\x1b[0m"
PROMPT = f"{TEAL}❯{RESET} "  # noqa: RUF001

# agg theme string: bg, fg, then ANSI colors 0-15.
AGG_THEME = ",".join(
    _hex(c)
    for c in (
        VAULTSPEC_THEME.background_color,
        VAULTSPEC_THEME.foreground_color,
        *VAULTSPEC_THEME.ansi_colors,
    )
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


def run_core(args: list[str], width: int = 200) -> str:
    """Run a ``vaultspec-core`` command in-process, return recorded ANSI."""
    rec = _recording_console(width)

    from typer.testing import CliRunner

    from vaultspec_core.cli.root import app

    with vsconsole.override_console(rec):
        result = CliRunner().invoke(app, args, catch_exceptions=False)
    if result.exit_code not in (0, 1):
        print(f"warning: exit {result.exit_code} for {args}", file=sys.stderr)
    return rec.export_text(styles=True)


def fit_lines(ansi: str, width: int = COLS) -> list[str]:
    """Ellipsis-trim each captured line to the demo terminal width."""
    out = _recording_console(width)
    for line in ansi.splitlines():
        text = Text.from_ansi(line)
        text.truncate(width, overflow="ellipsis")
        out.print(text, no_wrap=True, overflow="crop")
    text = out.export_text(styles=True)
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


class Cast:
    """Accumulate asciicast v2 events with a running clock."""

    def __init__(self) -> None:
        self.t = 0.5
        self.events: list[tuple[float, str]] = []

    def emit(self, data: str, dt: float = 0.0) -> None:
        self.t += dt
        self.events.append((round(self.t, 4), data))

    def type_line(self, text: str, style: str = "") -> None:
        """Type a prompt line character by character."""
        if self.events:
            self.emit("\r\n", 0.0)
        self.emit(PROMPT, 0.1)
        for i, ch in enumerate(text):
            self.emit(
                f"{style}{ch}{RESET}" if style else ch, 0.024 + ((i * 29) % 23) / 1000
            )
        self.emit("\r\n", 0.35)

    def stream(self, lines: list[str]) -> None:
        for i in range(0, len(lines), 2):
            chunk = "".join(f"{line}\r\n" for line in lines[i : i + 2])
            self.emit(chunk, 0.045)

    def dump(self, path: str, title: str) -> None:
        header = {
            "version": 2,
            "width": COLS,
            "height": ROWS,
            "title": title,
        }
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(header) + "\n")
            for t, data in self.events:
                fh.write(json.dumps([t, "o", data]) + "\n")


def fill_prose(vault: pathlib.Path, date: str) -> None:
    """Stand in for the off-screen agent work between scaffold and review.

    Fills every required body section, authors the plan's Steps and closes
    the first through the plan verbs, and logs it to the ledger, so the
    scenes that follow show a clean check and a plan in progress.
    """
    research = vault / "research" / f"{date}-{FEATURE}-research.md"
    adr = vault / "adr" / f"{date}-{FEATURE}-adr.md"
    plan_stem = f"{date}-{FEATURE}-plan"
    plan = vault / "plan" / f"{plan_stem}.md"

    run_core(["vault", "check", "annotations", "--fix"])
    fill_sections(
        research,
        {"{topic}": "full-text search options"},
        RESEARCH_SECTIONS,
    )
    fill_sections(
        adr,
        {
            "{title}": "adopt postgres full-text search",
            "{proposed|accepted|rejected|superseded|deprecated}": "accepted",
        },
        ADR_SECTIONS,
    )
    fill_sections(plan, {}, PLAN_SECTIONS)
    for action, scope in PLAN_STEPS:
        run_core(
            [
                "vault",
                "plan",
                "step",
                "add",
                plan_stem,
                "--action",
                action,
                "--scope",
                scope,
            ]
        )
    run_core(["vault", "plan", "step", "check", plan_stem, "S01"])
    run_core(
        [
            "vault",
            "exec",
            "log",
            "--feature",
            FEATURE,
            "--related",
            plan_stem,
            "--step",
            "S01",
            "--row",
            f"A:{PLAN_STEPS[0][1]}",
            "--verify",
            "pytest tests/test_search.py=pass",
        ]
    )
    run_core(["vault", "feature", "index", "-f", FEATURE])
    run_core(["vault", "check", "all", "--fix"])


def fill_sections(
    path: pathlib.Path, placeholders: dict[str, str], sections: dict[str, str]
) -> None:
    """Replace heading placeholders and give each empty section its prose."""
    text = path.read_text(encoding="utf-8")
    for placeholder, value in placeholders.items():
        text = text.replace(placeholder, value)
    for heading, prose in sections.items():
        text = text.replace(f"\n## {heading}\n", f"\n## {heading}\n\n{prose}\n", 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    out_gif = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else "docs/assets/demo.gif"
    )
    agg = os.environ.get("AGG") or shutil.which("agg")
    if not agg:
        sys.exit("error: agg not found on PATH (set AGG=<path-to-agg>)")

    demo = pathlib.Path(tempfile.mkdtemp(prefix="vaultspec-demo-")) / FEATURE
    demo.mkdir()
    os.chdir(demo)
    subprocess.run(["git", "init", "-q", "."], check=True)

    def redact(ansi: str) -> str:
        for variant in (str(demo), str(demo).replace("\\", "/")):
            ansi = ansi.replace(variant, REDACTED)
        # Normalize the backslash paths Windows prints, after the redacted
        # root or relative to it, so the demo reads the same on every platform.
        return re.sub(
            "(?:" + re.escape(REDACTED) + r"|\.vault)(?:\\[\w.\-]+)+",
            lambda m: m.group(0).replace("\\", "/"),
            ansi,
        )

    cast = Cast()

    def scene(command: list[str], shown: str, hold: float = 1.7) -> str:
        ansi = redact(run_core(command))
        cast.type_line(shown)
        cast.stream(fit_lines(ansi))
        cast.emit("", hold)
        return ansi

    def narrate(comment: str) -> None:
        cast.type_line(comment, style=DIM)
        cast.emit("\r\n", 1.1)

    scene(["install"], f"{CLI} install", hold=2.2)
    scene(
        ["vault", "add", "research", "--feature", FEATURE],
        f"{CLI} vault add research --feature {FEATURE}",
    )
    date = next((demo / ".vault" / "research").glob("*.md")).name.split(f"-{FEATURE}")[
        0
    ]
    scene(
        [
            "vault",
            "add",
            "adr",
            "--feature",
            FEATURE,
            "--related",
            f"{date}-{FEATURE}-research",
        ],
        f"{CLI} vault add adr --feature {FEATURE} --related {date}-{FEATURE}-research",
    )
    scene(
        [
            "vault",
            "add",
            "plan",
            "--feature",
            FEATURE,
            "--related",
            f"{date}-{FEATURE}-adr",
        ],
        f"{CLI} vault add plan --feature {FEATURE} --related {date}-{FEATURE}-adr",
    )
    narrate("# ... the agent drafts each record, then implements and logs S01 ...")
    fill_prose(demo / ".vault", date)
    scene(["vault", "check", "all"], f"{CLI} vault check all", hold=2.2)
    scene(
        ["vault", "graph", "--feature", FEATURE],
        f"{CLI} vault graph --feature {FEATURE}",
        hold=2.2,
    )
    scene(["status", FEATURE], f"{CLI} status {FEATURE}", hold=3.0)

    cast_path = str(demo / "demo.cast")
    cast.dump(cast_path, "vaultspec pipeline demo")
    subprocess.run(
        [
            agg,
            cast_path,
            out_gif,
            "--theme",
            AGG_THEME,
            "--font-family",
            "Cascadia Mono,Consolas",
            "--font-size",
            "14",
            "--line-height",
            "1.35",
            "--last-frame-duration",
            "4",
        ],
        check=True,
    )
    print(f"wrote {out_gif}")


if __name__ == "__main__":
    main()
