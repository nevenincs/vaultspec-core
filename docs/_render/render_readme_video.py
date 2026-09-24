#!/usr/bin/env python
"""Render the README's feature-cycle video: one feature, start to finish.

Plays the scripted feature build in :mod:`docs._render.walkthrough` and turns
it into a 45-second explainer: a stage timeline across the top, the terminal on
the left typing each command and printing its genuine output, and on the right
the record that stage produced, rendered from its Markdown - the research and
the decision as the agent wrote them, the cross-references TypeSafe ranked, the
plan's Steps, the checks, the progress, and the feature's link graph drawn from
``vaultspec-core vault graph --json``. A caption names each stage.

The frames come from :file:`feature_cycle.html`, a self-contained player whose
``renderAt(t)`` sets every visible state from the time alone. Chromium loads it
headless and is driven over the DevTools protocol on a pipe (stdlib only), one
screenshot per frame; ``ffmpeg`` encodes the frames as an H.264 MP4 and a
palette-optimised GIF for the README, which skips the opening title card
because the README already opens with the same title.

The cross-reference stage runs against the walkthrough's local stand-in for the
TypeSafe API, and its card says so.

Usage::

    uv run --no-sync python -m docs._render.render_readme_video [OUT_DIR]

``OUT_DIR`` defaults to ``docs/assets``; the renderer writes
``feature-cycle.mp4`` and ``feature-cycle.gif`` there. Requires a Chromium or
Chrome binary (set ``CHROMIUM`` to its path, or have ``chromium`` on PATH) and
``ffmpeg`` built with libx264 (set ``FFMPEG``, or have it on PATH). POSIX only:
the DevTools pipe is handed to the browser as file descriptors 3 and 4.
"""

from __future__ import annotations

import base64
import contextlib
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from markdown_it import MarkdownIt
from rich.console import Console
from rich.text import Text

from docs._render.render_readme_assets import VAULTSPEC_THEME
from docs._render.render_readme_walkthrough import output_lines, wrap_command
from docs._render.walkthrough import FEATURE, run_core, walkthrough
from vaultspec_core.vaultcore.parser import parse_vault_metadata

if TYPE_CHECKING:
    from docs._render.walkthrough import Stage

HERE = Path(__file__).resolve().parent
PLAYER = HERE / "feature_cycle.html"
LOGO = HERE.parent / "assets" / "logo.png"

#: The player's CSS canvas, and the scale the frames are captured at: 1080p.
CANVAS = (1120, 630)
SCALE = 1080 / 630
FPS = 24
GIF_FPS = 12

#: Columns the player's terminal shows at its font size.
TERMINAL_COLUMNS = 78

# The timeline, in seconds. The stages share what the title cards leave.
DURATION = 45.0
INTRO = 3.0
OUTRO = 4.0
TYPE_RATE = 85.0  # characters per second
TYPE_BOUNDS = (0.45, 1.15)
LEAD_IN = 0.35
AFTER_TYPING = 0.22
LINE_INTERVAL = 0.018  # the player streams output at this pace
AFTER_OUTPUT = 0.35
AGENT_DELAY = 0.45
MIN_TAIL = 0.8

#: How much of the spare time each stage keeps on screen, by slug. Stages with
#: a record to read get more.
TAIL_WEIGHTS = {
    "01-install": 0.8,
    "02-research": 1.2,
    "03-decide": 1.4,
    "04-crossref": 1.5,
    "05-plan": 1.0,
    "06-execute": 1.0,
    "07-check": 0.8,
    "08-status": 1.0,
    "09-graph": 1.5,
}

TAGLINE = "Decision-driven harness for coding agents, and humans."
INTRO_LEAD = "One feature, from research to a traced graph, in real commands."
OUTRO_TITLE = "Start your first feature"
OUTRO_COMMAND = "uvx vaultspec-core install"
OUTRO_LINKS = (
    "github.com/nevenincs/vaultspec-core",
    "Works with Claude Code, Codex, Gemini CLI and Antigravity",
)

STAND_IN_NOTE = (
    "In this recording the judgments come from a local stand-in for the "
    "TypeSafe API. Set VAULTSPEC_CORE_TYPESAFE_API_KEY for live ones."
)

#: What ``install`` writes, grouped the way a reader thinks about it.
INSTALLED = (
    ((".vault/",), "decisions, plans and ledgers"),
    ((".vaultspec/",), "the shared policy: rules, skills, agents"),
    (("CLAUDE.md", "AGENTS.md", "GEMINI.md"), "entry points for each agent"),
    ((".mcp.json",), "the MCP server your agent calls"),
    ((".claude/", ".codex/", ".gemini/", ".agents/"), "per-agent configuration"),
    ((".pre-commit-config.yaml",), "the commit gate, when you enable it"),
)

_VERDICT = re.compile(r"(link|weak) (\d\.\d\d) (\S+) (\S+) \((\w+)\)")
_CHECK = re.compile(r"^\s*ok (\S+): clean")
_STATUS_ROW = re.compile(r"(>)?\s*\[(x| )\] (S\d+)\s+(.*)$")
_PROGRESS = re.compile(r"(\d+)/(\d+) steps")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TASK = re.compile(r"<li>\[( |x)\] ")
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


def ansi_html(lines: list[str]) -> list[str]:
    """Convert captured ANSI lines to HTML spans in the shared palette."""
    if not lines:
        return []
    console = Console(
        record=True,
        width=400,
        force_terminal=True,
        color_system="truecolor",
        highlight=False,
        soft_wrap=True,
        file=io.StringIO(),
    )
    for line in lines:
        console.print(Text.from_ansi(line), no_wrap=True, overflow="ignore")
    exported = console.export_html(
        theme=VAULTSPEC_THEME, inline_styles=True, code_format="{code}"
    )
    return exported.split("\n")[: len(lines)]


_MARKDOWN = MarkdownIt("commonmark", {"html": False})


def markdown_html(text: str) -> str:
    """Render a vault record's Markdown body, as a reader would see it."""
    body = _COMMENT.sub("", text)
    rendered = _MARKDOWN.render(body)
    return _TASK.sub(
        lambda m: (
            '<li class="task"><span class="box'
            + (' on"' if m[1] == "x" else '"')
            + "></span>"
        ),
        rendered,
    )


def _short(stem: str) -> str:
    return _DATE_PREFIX.sub("", stem.strip("[]"))


def _chips(tags: list[str], related: list[str], fresh: set[str]) -> str:
    chips = [f'<span class="chip tag">{html.escape(tag)}</span>' for tag in tags]
    for link in related:
        stem = link.strip("[]")
        kind = "chip new" if stem in fresh else "chip"
        chips.append(f'<span class="{kind}">&rarr; {html.escape(_short(stem))}</span>')
    return f'<div class="fm">{"".join(chips)}</div>'


def record_html(text: str, fresh: set[str] | None = None) -> str:
    """A record's frontmatter as chips, then its rendered body."""
    meta, body = parse_vault_metadata(text)
    return _chips(list(meta.tags), list(meta.related), fresh or set()) + (
        f'<div class="md">{markdown_html(body)}</div>'
    )


def _files_card(root: Path) -> str:
    present = {
        f"{entry.name}/" if entry.is_dir() else entry.name for entry in root.iterdir()
    }
    rows = [
        f'<div class="row"><span class="name">{html.escape(" ".join(shown))}'
        f'</span><span class="what">{html.escape(what)}</span></div>'
        for names, what in INSTALLED
        if (shown := [name for name in names if name in present])
    ]
    return '<div class="kicker">Written into the repository</div>' + (
        f'<div class="files">{"".join(rows)}</div>'
    )


def _crossref_card(stage: Stage, adr_count: int) -> str:
    plain = Text.from_ansi(stage.commands[0].output).plain
    verdicts = _VERDICT.findall(plain)
    rows = "".join(
        f'<div class="row"><div class="label"><span>{html.escape(_short(stem))}</span>'
        f"<span>{score}</span></div>"
        f'<div class="rel">{kind} &middot; {html.escape(relation.replace("_", " "))}'
        f" &middot; {mark}</div>"
        f'<div class="track"><div class="fill" data-fill="{score}"></div></div></div>'
        for kind, score, relation, stem, mark in verdicts
    )
    fresh = {stem for _kind, _score, _rel, stem, mark in verdicts if mark == "written"}
    meta, _body = parse_vault_metadata(stage.markdown or "")
    yaml_lines = ["related:"]
    for link in meta.related:
        stem = link.strip("[]")
        line = f'  - "[[{html.escape(stem)}]]"'
        yaml_lines.append(f'<span class="add">{line}</span>' if stem in fresh else line)
    return (
        f'<div class="kicker">Ranked against {adr_count} earlier decisions</div>'
        f'<div class="rank">{rows}</div>'
        '<div class="kicker">Written into the decision</div>'
        f'<div class="yaml">{"\n".join(yaml_lines)}</div>'
        f'<div class="note">{html.escape(STAND_IN_NOTE)}</div>'
    )


def _check_card(stage: Stage) -> str:
    plain = Text.from_ansi(stage.commands[0].output).plain.splitlines()
    names = [m[1] for line in plain if (m := _CHECK.match(line))]
    fixed = next(
        (line.strip() for line in plain if line.strip().startswith("Total")), ""
    )
    chips = "".join(
        f'<span class="chip">&#10003; {html.escape(n)}</span>' for n in names
    )
    return (
        f'<div class="big">{len(names)} checks clean</div>'
        f'<div class="sub">{html.escape(fixed)} &middot; structure, links, schema'
        " and more</div>"
        f'<div class="checks">{chips}</div>'
    )


def _status_card(stage: Stage) -> str:
    plain = Text.from_ansi(stage.commands[0].output).plain
    progress = _PROGRESS.search(plain)
    done, total = (int(progress[1]), int(progress[2])) if progress else (0, 1)
    rows: list[str] = []
    for line in plain.splitlines():
        if not (m := _STATUS_ROW.search(line)):
            continue
        nxt = '<span class="next">NEXT</span>' if m[1] else ""
        box = (
            '<span class="box on"></span>'
            if m[2] == "x"
            else '<span class="box"></span>'
        )
        rows.append(
            f'<div class="row md">{box}<span class="id">{m[3]}</span>'
            f"<span>{html.escape(m[4].strip())}</span>{nxt}</div>"
        )
    return (
        f'<div class="big">{done} of {total} Steps</div>'
        '<div class="sub">recorded in the plan and its ledger</div>'
        f'<div class="progress"><div class="fill" data-fill="{done / total:.3f}">'
        f'</div></div><div class="steps">{"".join(rows)}</div>'
    )


_GRAPH_SLOTS: dict[str, tuple[float, float]] = {
    "adr": (188, 128),
    "research": (78, 222),
    "plan": (298, 222),
    "exec": (298, 306),
    "reference": (78, 306),
    "audit": (78, 306),
}
_GRAPH_COLOURS = {
    "adr": "#4a7c74",
    "research": "#6a7a4d",
    "plan": "#a37a3a",
    "exec": "#7c6a9c",
}


def _graph_card(graph: dict[str, object]) -> str:
    """Draw the feature's records and the decisions they link, from graph JSON."""
    raw_nodes = cast("list[dict[str, object]]", graph["nodes"])
    # A feature graph lists the feature's records; the decisions they link in
    # other features appear only as link targets, drawn outlined above.
    own = {
        str(n["id"]): n
        for n in raw_nodes
        if n.get("feature") == FEATURE and n.get("doc_type") != "index"
    }
    edges = [
        (stem, str(target))
        for stem, n in own.items()
        for target in cast("list[str]", n.get("out_links", []))
    ]
    outside = sorted({t for _s, t in edges if t not in own})
    place: dict[str, tuple[float, float]] = {
        stem: _GRAPH_SLOTS[str(n.get("doc_type"))] for stem, n in own.items()
    }
    for index, stem in enumerate(outside):
        place[stem] = (78 + index * (220 / max(len(outside) - 1, 1)), 34)
    parts: list[str] = [
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#918981"/></marker></defs>'
    ]
    for source, target in edges:
        (x1, y1), (x2, y2) = place[source], place[target]
        length = math.hypot(x2 - x1, y2 - y1)
        # Stop the arrow at the target box's edge rather than its centre.
        ratio = max(length - 26, 1) / length
        x2, y2 = x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio
        crossref = target in outside
        colour, width = ("#4a7c74", 2.4) if crossref else ("#918981", 1.4)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{colour}" stroke-width="{width}" marker-end="url(#arrow)" '
            f'data-draw="{length:.1f}"/>'
        )
    for stem, (x, y) in place.items():
        ours = stem in own
        kind = str(own[stem].get("doc_type")) if ours else "adr"
        fill = _GRAPH_COLOURS.get(kind, "#5e564e") if ours else "#fffdf9"
        ink = "#ffffff" if ours else "#5e564e"
        label = html.escape(_short(stem))
        width = max(len(label) * 6.6 + 18, 70)
        parts.append(
            f'<rect x="{x - width / 2:.1f}" y="{y - 13}" width="{width:.1f}" '
            f'height="26" rx="13" fill="{fill}" stroke="#4a7c74" '
            f'stroke-width="{0 if ours else 1.4}" '
            f'stroke-dasharray="{"0" if ours else "4 3"}"/>'
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" fill="{ink}">'
            f"{label}</text>"
        )
    return (
        '<div class="kicker">The feature&rsquo;s records and their links</div>'
        '<svg class="graph" width="376" height="330" viewBox="0 0 376 330">'
        + "".join(parts)
        + "</svg>"
        '<div class="note">Teal links were written by the cross-reference step.</div>'
    )


def _execute_card(stage: Stage, root: Path) -> str:
    """The ledger's rows, then the plan's Steps with their new state."""
    ledgers = sorted((root / ".vault" / "exec").rglob("*-ledger.md"))
    rows: list[str] = []
    if ledgers:
        _meta, body = parse_vault_metadata(ledgers[0].read_text(encoding="utf-8"))
        rows = [
            line
            for line in _COMMENT.sub("", body).splitlines()
            if line.startswith("- `S")
        ]
    _meta, plan = parse_vault_metadata(stage.markdown or "")
    steps = [line for line in plan.splitlines() if line.startswith("- [")]
    return (
        '<div class="kicker">Appended to the ledger</div>'
        f'<div class="md">{markdown_html(chr(10).join(rows))}</div>'
        '<div class="kicker">The plan&rsquo;s Steps</div>'
        f'<div class="md">{markdown_html(chr(10).join(steps))}</div>'
    )


@dataclass(frozen=True)
class _Card:
    path: str
    badge: str
    html: str
    agent: bool = False
    scroll: bool = False


def card_for(stage: Stage, root: Path, graph: dict[str, object]) -> _Card:
    """The right-hand card for *stage*."""
    record = stage.record or ""
    if stage.slug == "01-install":
        return _Card("~/code/search-api", "written by install", _files_card(root))
    if stage.slug in ("02-research", "03-decide"):
        body = record_html(stage.markdown or "")
        return _Card(record, "drafted by your agent", body, agent=True, scroll=True)
    if stage.slug == "04-crossref":
        adrs = len(list((root / ".vault" / "adr").glob("*.md"))) - 1
        return _Card(record, "ranked by TypeSafe", _crossref_card(stage, adrs))
    if stage.slug == "05-plan":
        body = record_html(stage.markdown or "")
        return _Card(record, "Steps by vaultspec-core", body, scroll=True)
    if stage.slug == "06-execute":
        return _Card(record, "closed by vaultspec-core", _execute_card(stage, root))
    if stage.slug == "07-check":
        return _Card(".vault/", "vault check", _check_card(stage))
    if stage.slug == "08-status":
        return _Card(f"status {FEATURE}", "progress", _status_card(stage))
    return _Card(f"#{FEATURE}", "vault graph", _graph_card(graph))


# ---------------------------------------------------------------------------
# The storyboard
# ---------------------------------------------------------------------------


def _type_time(chars: int) -> float:
    low, high = TYPE_BOUNDS
    return min(max(chars / TYPE_RATE, low), high)


def _schedule_stage(
    stage: Stage, start: float
) -> tuple[list[dict[str, object]], float]:
    """Time one stage's commands from *start*; return them and when output ends."""
    t = start + LEAD_IN
    commands: list[dict[str, object]] = []
    for command in stage.commands:
        lines = wrap_command(command, TERMINAL_COLUMNS)
        type_end = t + _type_time(sum(len(line) for line in lines))
        out_at = type_end + AFTER_TYPING
        output = ansi_html(output_lines(command.output))
        commands.append(
            {
                "lines": lines,
                "typeStart": round(t, 3),
                "typeEnd": round(type_end, 3),
                "outAt": round(out_at, 3),
                "output": output,
            }
        )
        t = out_at + min(len(output) * LINE_INTERVAL, 0.6) + AFTER_OUTPUT
    return commands, t


def storyboard(
    stages: list[Stage], root: Path, graph: dict[str, object]
) -> dict[str, object]:
    """Lay the stages out on the timeline and collect everything the player shows."""
    timed: list[tuple[Stage, list[dict[str, object]], float, _Card, float]] = []
    busy = 0.0
    for stage in stages:
        commands, done = _schedule_stage(stage, 0.0)
        card = card_for(stage, root, graph)
        card_at = done + (AGENT_DELAY if card.agent else 0.0)
        active = card_at + 0.4
        timed.append((stage, commands, done, card, card_at))
        busy += active
    spare = DURATION - INTRO - OUTRO - busy
    weights = sum(TAIL_WEIGHTS.get(stage.slug, 1.0) for stage in stages)
    if spare < MIN_TAIL * len(stages):
        raise SystemExit(
            f"error: the stages need {busy:.1f}s of a {DURATION - INTRO - OUTRO:.1f}s "
            "budget with too little left to read; raise TYPE_RATE or DURATION"
        )
    out: list[dict[str, object]] = []
    start = INTRO
    for number, (stage, commands, _done, card, card_at) in enumerate(timed, start=1):
        length = card_at + 0.4 + spare * TAIL_WEIGHTS.get(stage.slug, 1.0) / weights
        for command in commands:
            for key in ("typeStart", "typeEnd", "outAt"):
                command[key] = round(cast("float", command[key]) + start, 3)
        out.append(
            {
                "slug": stage.slug,
                "number": number,
                "title": stage.title,
                "caption": stage.caption,
                "start": round(start, 3),
                "end": round(start + length, 3),
                "commands": commands,
                "card": {
                    "at": round(start + card_at, 3),
                    "path": card.path,
                    "badge": card.badge,
                    "html": card.html,
                    "agent": card.agent,
                    "scroll": card.scroll,
                },
            }
        )
        start += length
    logo = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    return {
        "duration": DURATION,
        "intro": {"end": INTRO},
        "outro": {"start": round(start, 3)},
        "stages": out,
        "logo": f"data:image/png;base64,{logo}",
        "tagline": TAGLINE,
        "introLead": INTRO_LEAD,
        "outroTitle": OUTRO_TITLE,
        "outroCommand": OUTRO_COMMAND,
        "outroLinks": list(OUTRO_LINKS),
    }


def player_html(story: dict[str, object]) -> str:
    """The player page with *story* embedded."""
    template = PLAYER.read_text(encoding="utf-8")
    data = json.dumps(story).replace("</", "<\\/")
    return template.replace("/*STORYBOARD*/null", data)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


class DevTools:
    """A headless Chromium driven over the DevTools protocol on a pipe."""

    def __init__(self, chrome: str) -> None:
        to_chrome_r, self._to_chrome = os.pipe()
        self._from_chrome, from_chrome_w = os.pipe()

        def wire() -> None:  # runs in the child, before exec
            # Either end may already sit on 3 or 4, where a dup2 onto itself
            # is a no-op that keeps close-on-exec: move both clear first.
            ends = (os.dup(to_chrome_r), os.dup(from_chrome_w))
            for fd, end in zip((3, 4), ends, strict=True):
                os.dup2(end, fd)
                os.set_inheritable(fd, True)

        # --no-sandbox: the page is this renderer's own local file.
        self._process = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--remote-debugging-pipe",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                "--font-render-hinting=none",
                "about:blank",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=False,
            preexec_fn=wire,
        )
        os.close(to_chrome_r)
        os.close(from_chrome_w)
        self._buffer = b""
        self._next_id = 0
        self._session: str | None = None

    def call(
        self, method: str, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Send one command and return its result, skipping events."""
        self._next_id += 1
        message: dict[str, object] = {"id": self._next_id, "method": method}
        if params:
            message["params"] = params
        if self._session is not None:
            message["sessionId"] = self._session
        os.write(self._to_chrome, json.dumps(message).encode("utf-8") + b"\0")
        while True:
            reply = self._read()
            if reply.get("id") != self._next_id:
                continue
            if "error" in reply:
                raise RuntimeError(f"{method}: {reply['error']}")
            return cast("dict[str, object]", reply.get("result", {}))

    def _read(self) -> dict[str, object]:
        while b"\0" not in self._buffer:
            chunk = os.read(self._from_chrome, 1 << 20)
            if not chunk:
                raise RuntimeError("the browser closed the DevTools pipe")
            self._buffer += chunk
        raw, _, self._buffer = self._buffer.partition(b"\0")
        return cast("dict[str, object]", json.loads(raw))

    def open(self, url: str, size: tuple[int, int], scale: float) -> None:
        """Open *url* in a new page sized *size* CSS pixels at *scale*."""
        target = self.call("Target.createTarget", {"url": "about:blank"})
        attached = self.call(
            "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
        )
        self._session = str(attached["sessionId"])
        width, height = size
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": scale,
                "mobile": False,
            },
        )
        self.call("Page.navigate", {"url": url})
        self.evaluate(
            "new Promise(r => { const go = () => document.fonts.ready.then(r);"
            " document.readyState === 'complete' ? go()"
            " : addEventListener('load', go); })"
        )

    def evaluate(self, expression: str) -> None:
        result = self.call(
            "Runtime.evaluate", {"expression": expression, "awaitPromise": True}
        )
        if "exceptionDetails" in result:
            raise RuntimeError(f"player error: {result['exceptionDetails']}")

    def screenshot(self) -> bytes:
        shot = self.call("Page.captureScreenshot", {"format": "png"})
        return base64.b64decode(str(shot["data"]))

    def close(self) -> None:
        self._session = None
        with contextlib.suppress(RuntimeError):
            self.call("Browser.close")
        self._process.wait(timeout=30)
        os.close(self._to_chrome)
        os.close(self._from_chrome)


def capture(page: Path, frames: Path, chrome: str) -> int:
    """Screenshot every frame of the player into *frames*; return the count."""
    count = round(DURATION * FPS)
    browser = DevTools(chrome)
    try:
        browser.open(page.as_uri(), CANVAS, SCALE)
        for index in range(count):
            browser.evaluate(f"renderAt({index / FPS:.4f})")
            (frames / f"{index:05d}.png").write_bytes(browser.screenshot())
    finally:
        browser.close()
    return count


def encode(frames: Path, outdir: Path, ffmpeg: str) -> None:
    """Encode the frames as the MP4 and the README GIF."""
    source = ["-framerate", str(FPS), "-i", str(frames / "%05d.png")]
    quiet = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    mp4 = outdir / "feature-cycle.mp4"
    h264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p"]
    streaming = ["-movflags", "+faststart"]
    subprocess.run([*quiet, *source, *h264, *streaming, str(mp4)], check=True)
    # The README shows its own title right above the GIF, so the GIF opens on
    # the first stage and keeps the closing card as its call to action.
    gif = outdir / "feature-cycle.gif"
    gif_source = ["-start_number", str(round(INTRO * FPS)), *source]
    width = CANVAS[0]
    graph = (
        f"fps={GIF_FPS},scale={width}:-1:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=96:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    subprocess.run([*quiet, *gif_source, "-vf", graph, str(gif)], check=True)
    for path in (mp4, gif):
        print(f"wrote {path} ({path.stat().st_size // 1024} KiB)")


def _tool(variable: str, names: tuple[str, ...]) -> str:
    found = os.environ.get(variable) or next(
        (path for name in names if (path := shutil.which(name))), None
    )
    if not found:
        sys.exit(f"error: {names[0]} not found on PATH (set {variable}=<path>)")
    return found


def main() -> None:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets").resolve()
    chrome = _tool("CHROMIUM", ("chromium", "chromium-browser", "google-chrome"))
    ffmpeg = _tool("FFMPEG", ("ffmpeg",))
    with tempfile.TemporaryDirectory(prefix="vaultspec-video-") as tmp:
        work = Path(tmp)
        with walkthrough() as stages:
            root = Path.cwd()
            graph_json = json.loads(
                run_core(["vault", "graph", "--feature", FEATURE, "--json"])
            )
            story = storyboard(
                stages, root, cast("dict[str, object]", graph_json["data"])
            )
        page = work / "feature-cycle.html"
        page.write_text(player_html(story), encoding="utf-8")
        frames = work / "frames"
        frames.mkdir()
        count = capture(page, frames, chrome)
        print(f"captured {count} frames")
        outdir.mkdir(parents=True, exist_ok=True)
        encode(frames, outdir, ffmpeg)


if __name__ == "__main__":
    main()
