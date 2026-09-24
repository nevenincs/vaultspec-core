"""Build one feature end to end and record what every command prints.

This is the one scripted feature build the README renders draw from: the
per-stage terminal stills (:mod:`docs._render.render_readme_walkthrough`), the
terminal tape (:mod:`docs._render.render_readme_demo`) and the feature-cycle
video (:mod:`docs._render.render_readme_video`). Rendering all three from one
run is what keeps them telling the same story with the same output.

The story is the README's own example. A project that already records three
decisions (``storage-layer``, ``api-pagination``, ``request-auth``) adds
full-text search under the feature tag ``search-api``: research, a decision,
its cross-references, a plan, one executed Step, then the check, status and
graph views. Every command shown runs in-process through the real Typer
application against a throwaway git repository, and its output is the
command's own, captured by swapping a recording console into the shared
console singleton (:func:`vaultspec_core.console.override_console`).

Two things stand in for the parts a terminal cannot show:

- **The agent's prose.** A coding agent writes the research findings, the
  decision and the plan's description. Here fixed texts do, written through
  ``vaultspec-core vault set-body`` exactly as an agent's edit would be, so the
  records a stage leaves behind are the same kind the workflow produces.
- **The TypeSafe API.** ``vault adr crossref`` needs a TypeSafe key and sends
  ADR text to ``api.typesafe.ai``. A render must not depend on either, so the
  provider is a local HTTP server
  (:class:`vaultspec_core.search.tests.scripted_provider.ScriptedProvider`)
  whose judgment is a stated rule: a candidate decision that governs the same
  code artifacts as the source is a link, and more shared artifacts mean a
  stronger one. The client, the engine, the link writer and the CLI renderer
  are the shipped code. The one substitution is the client's default
  endpoint, redirected for the duration of that command only; the product
  itself has no endpoint setting, by design. Captions that show this command
  say that its judgments come from the stand-in.

The only edits to captured output are cosmetic: the temporary directory is
redacted to ``~/code/search-api``.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from rich.console import Console

import vaultspec_core.console as vsconsole

if TYPE_CHECKING:
    from collections.abc import Generator

    from vaultspec_core.search.tests.scripted_provider import Received, Reply

#: Force colour even under shells that export ``NO_COLOR``: the recording
#: consoles below are never a real terminal.
os.environ.pop("NO_COLOR", None)

FEATURE = "search-api"
REDACTED = "~/code/search-api"
#: The throwaway repository's directory prefix; no published output shows it.
TEMP_PREFIX = "vaultspec-walkthrough-"
#: Terminal width the commands are captured at.
WIDTH = 100

#: The stand-in provider's credential. It never leaves this process.
STAND_IN_KEY = "walkthrough-stand-in"
#: Model-facing text maps backticks to this character before it is sent.
_TICK = "\N{LEFT SINGLE QUOTATION MARK}"
_ARTIFACT = re.compile(f"{_TICK}([^{_TICK}]+){_TICK}")


@dataclass(frozen=True)
class Stems:
    """The feature's record stems, dated the day the walkthrough runs.

    The commands shown carry no ``--date``, so they are exactly what a reader
    would type; the records are therefore dated by the scaffolder's clock and
    the stems are read back from the first record it writes.
    """

    day: str

    @property
    def research(self) -> str:
        return f"{self.day}-{FEATURE}-research"

    @property
    def adr(self) -> str:
        return f"{self.day}-{FEATURE}-adr"

    @property
    def plan(self) -> str:
        return f"{self.day}-{FEATURE}-plan"


@dataclass(frozen=True)
class Command:
    """One command as typed at the prompt, with what it printed.

    Attributes:
        args: The arguments after ``vaultspec-core``.
        output: The command's captured output, with ANSI styling.
    """

    args: tuple[str, ...]
    output: str

    @property
    def shown(self) -> str:
        """The command line a reader would type."""
        return " ".join(["vaultspec-core", *(quote(arg) for arg in self.args)])

    def groups(self) -> list[str]:
        """The command line split where a shell line may break.

        The first group is the command and its positional arguments; each
        later group is one option with its value, so a wrapped line never
        parts an option from what it sets.
        """
        groups = ["vaultspec-core"]
        for arg in self.args:
            if arg.startswith("-"):
                groups.append(quote(arg))
            else:
                groups[-1] += f" {quote(arg)}"
        return groups


@dataclass(frozen=True)
class Stage:
    """One stage of the feature build.

    Attributes:
        slug: File-name stem for the stage's still, such as ``01-install``.
        title: The stage's name, such as ``Decide``.
        caption: One sentence on what the stage does.
        commands: The commands the stage runs, in order.
        record: The vault-relative path of the record the stage wrote or
            changed, if any.
        markdown: That record's text once the stage is done.
        stand_in: Whether the stage's output depends on the stand-in provider.
    """

    slug: str
    title: str
    caption: str
    commands: tuple[Command, ...]
    record: str | None = None
    markdown: str | None = None
    stand_in: bool = False


# ---------------------------------------------------------------------------
# The prose an agent would write
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Decision:
    """An accepted decision already on record before the walkthrough starts."""

    feature: str
    date: str
    title: str
    problem: str
    implementation: str


_PRIOR_DECISIONS = (
    _Decision(
        "storage-layer",
        "2026-06-02",
        "keep postgres as the system of record",
        "Items, accounts and audit events need one transactional store.",
        "Every table is declared in `src/db/schema.sql` and reached through the "
        "pool in `src/db/pool.py`, configured by `DATABASE_URL`.",
    ),
    _Decision(
        "api-pagination",
        "2026-06-18",
        "paginate list endpoints with opaque cursors",
        "Offset pages skip and repeat rows while items are written.",
        "List routes such as `src/api/routes/items.py` page through the helper in "
        "`src/api/pagination.py`, which returns an opaque `next_cursor`.",
    ),
    _Decision(
        "request-auth",
        "2026-07-09",
        "authenticate requests with scoped API tokens",
        "Partners call the API from servers, not browsers.",
        "`src/api/auth.py` checks the `X-Api-Token` header against hashed, "
        "scoped tokens before any route runs.",
    ),
)


def _adr_body(feature: str, title: str, sections: dict[str, str]) -> str:
    """Render an accepted ADR body: its H1, then each section in order."""
    head = f"# `{feature}` adr: `{title}` | (**status:** `accepted`)\n"
    return head + "".join(f"\n## {name}\n\n{text}\n" for name, text in sections.items())


def _prior_body(decision: _Decision) -> str:
    return _adr_body(
        decision.feature,
        decision.title,
        {
            "Problem Statement": decision.problem,
            "Considerations": "The team already operates this stack in production.",
            "Considered options": "The adopted approach, and doing nothing.",
            "Constraints": "No new service may be introduced for this.",
            "Implementation": decision.implementation,
            "Rationale": "It is the smallest change that meets the need.",
            "Consequences": "Later decisions that touch these files build on it.",
        },
    )


_RESEARCH_BODY = f"""\
# `{FEATURE}` research: `full-text search options`

Clients can filter items only by exact field values. This compares two ways to add
ranked full-text search to the item API; the evidence favours staying inside Postgres.

## Findings

### Postgres full-text search covers the query shapes we need

A generated `tsvector` column with a GIN index answers prefix, phrase and weighted
queries, and `ts_rank` orders the results inside the store that already holds items
(`src/db/schema.sql`).

### An external engine adds a second store to keep in sync

A dedicated search service needs its own index pipeline and deployment, and every item
write would have to reach two stores.

## Sources

- https://www.postgresql.org/docs/current/textsearch.html
- `src/db/schema.sql`
"""


def _decision_body(stems: Stems) -> str:
    return _adr_body(
        FEATURE,
        "rank item search with postgres full-text search",
        {
            "Problem Statement": (
                "Clients need ranked keyword search over items; exact-field filters "
                f"cannot express it (`{stems.research}`)."
            ),
            "Considerations": (
                "Items already live in Postgres, and list endpoints already page with "
                "cursors."
            ),
            "Considered options": (
                "Postgres full-text search, chosen. A hosted search engine, rejected: "
                "a second store to keep in sync."
            ),
            "Constraints": "Search must not add a service or a second copy of items.",
            "Implementation": (
                "Add a generated `tsvector` column and a GIN index in "
                "`src/db/schema.sql`. Serve `GET /items/search` from "
                "`src/api/routes/search.py`, ordered by `ts_rank`, and page the "
                "results through `src/api/pagination.py` so clients follow the same "
                "`next_cursor` as every other list."
            ),
            "Rationale": "It reuses the store and the pagination clients know.",
            "Consequences": (
                "Ranking quality is bounded by Postgres; a later engine would need its "
                "own decision."
            ),
        },
    )


def _plan_body(stems: Stems) -> str:
    return f"""\
# `{FEATURE}` plan

Add ranked full-text search to the item API.

## Description

Approved {stems.day}. Implements `{stems.adr}`, grounded in `{stems.research}`.

## Steps

## Parallelization

The Steps run in order: each builds on the one before it.

## Verification

Each Step's tests pass, and a search request returns ranked, cursor-paged items.
"""


#: The plan's Steps: (action, scope).
STEPS = (
    ("Add a generated tsvector column and GIN index", "src/db/schema.sql"),
    ("Serve ranked search at GET /items/search", "src/api/routes/search.py"),
    ("Page search results with opaque cursors", "src/api/pagination.py"),
)


# ---------------------------------------------------------------------------
# Running commands
# ---------------------------------------------------------------------------


def _recording_console() -> Console:
    return Console(
        record=True,
        width=WIDTH,
        force_terminal=True,
        legacy_windows=False,
        highlight=False,
        soft_wrap=True,
        file=io.StringIO(),
    )


def run_core(args: list[str]) -> str:
    """Run a ``vaultspec-core`` command in-process and return its ANSI output.

    Raises:
        RuntimeError: If the command exits with a status other than ``0``; a
            walkthrough whose commands fail would publish a broken build.
    """
    from typer.testing import CliRunner

    from vaultspec_core.cli.root import app

    rec = _recording_console()
    with vsconsole.override_console(rec):
        result = CliRunner().invoke(app, args, catch_exceptions=False)
    # Most commands write through the shared console; the plan verbs echo
    # plain lines to stdout, which the runner captures instead.
    output = rec.export_text(styles=True) + result.output
    if result.exit_code != 0:
        raise RuntimeError(
            f"vaultspec-core {' '.join(args)} exited {result.exit_code}:\n{output}"
        )
    return output


def _set_body(ref: str, body: str, scratch: Path) -> None:
    """Write *body* into *ref* the way an agent's edit would."""
    source = scratch / f"{ref}.body.md"
    source.write_text(body, encoding="utf-8")
    run_core(["vault", "set-body", ref, "--body-file", str(source)])


# ---------------------------------------------------------------------------
# The stand-in TypeSafe provider
# ---------------------------------------------------------------------------


def _artifacts(text: str) -> set[str]:
    """Return the code spans in model-facing (sanitised) text."""
    return set(_ARTIFACT.findall(text))


def _relation(shared: int, relations: list[str]) -> dict[str, object]:
    chosen = (
        "depends_on" if shared > 1 else "shared_artifact" if shared else "unrelated"
    )
    probabilities = {name: (0.82 if name == chosen else 0.03) for name in relations}
    return {
        "type": "choice",
        "choice": chosen,
        "confidence": probabilities[chosen],
        "probabilities": probabilities,
    }


def _fields(value: object) -> dict[str, object]:
    """Narrow one decoded JSON object to its fields.

    Raises:
        TypeError: If *value* is not a JSON object.
    """
    fields = cast("dict[str, object]", value)
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object, got {type(value).__name__}")
    return fields


def _choice(
    criteria: dict[str, object], own: set[str], none_key: str
) -> dict[str, object]:
    """Pick the option that shares the most artifacts with the source."""
    overlap = {key: len(own & _artifacts(str(text))) for key, text in criteria.items()}
    best = max(overlap, key=lambda key: overlap[key])
    choice = best if overlap[best] else none_key
    probabilities = {key: (0.9 if key == choice else 0.01) for key in overlap}
    probabilities.setdefault(none_key, 0.01)
    return {
        "type": "choice",
        "choice": choice,
        "confidence": probabilities[choice],
        "probabilities": probabilities,
    }


def judge(
    payload: dict[str, object], relations: list[str], none_key: str
) -> dict[str, object]:
    """Answer one crossref request by the shared-artifact rule."""
    state = _fields(payload["state"])
    own = _artifacts(str(_fields(state["source"])["text"]))
    if "candidate" in state:
        theirs = _artifacts(str(_fields(state["candidate"])["text"]))
        shared = len(own & theirs)
        fraction = shared / max(len(theirs), 1)
        return {
            "need": {"type": "noul", "noul": 0.9 if shared else 0.12},
            "artifact": {"type": "noul", "noul": min(0.97, 0.55 + 0.4 * fraction)},
            "useless": {"type": "noul", "noul": 0.08 if shared else 0.88},
            "relation": _relation(shared, relations),
        }
    return {
        qid: _choice(_fields(_fields(question)["criteria"]), own, none_key)
        for qid, question in _fields(payload["questions"]).items()
    }


@contextlib.contextmanager
def stand_in_provider() -> Generator[dict[str, str]]:
    """Serve crossref judgments locally and point the client's default at them.

    Yields the environment the command must run with: the stand-in key.
    """
    import vaultspec_core.crossref._questions as crossref_questions
    import vaultspec_core.search._questions as search_questions
    import vaultspec_core.search._transport as transport
    from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY, reset_config
    from vaultspec_core.search.tests.scripted_provider import Reply, ScriptedProvider

    relation_question = crossref_questions.PAIR_QUESTIONS["relation"]
    relations = list(_fields(relation_question["criteria"]))
    none_key = crossref_questions.NONE_KEY

    def respond(received: Received) -> Reply:
        payload = received.payload()
        answers = judge(payload, relations, none_key)
        usage = {"input_tokens": len(received.body) // 4, "output_tokens": 0}
        return Reply.json(
            {"model": search_questions.MODEL, "answers": answers, "usage": usage}
        )

    defaults = transport.JevClient.__init__.__kwdefaults__
    assert defaults is not None and "endpoint" in defaults
    variable = VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name
    saved_key = os.environ.get(variable)
    with ScriptedProvider(responder=respond) as provider:
        saved_endpoint = defaults["endpoint"]
        defaults["endpoint"] = provider.endpoint
        os.environ[variable] = STAND_IN_KEY
        reset_config()
        try:
            yield {variable: STAND_IN_KEY}
        finally:
            defaults["endpoint"] = saved_endpoint
            if saved_key is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = saved_key
            reset_config()


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def quote(arg: str) -> str:
    """Quote *arg* for a shell line: double quotes when it holds a space.

    Nothing else in the walkthrough's commands needs quoting.
    """
    return f'"{arg}"' if " " in arg else arg


class _Session:
    """Run commands in one project and collect them into stages."""

    def __init__(self, root: Path, scratch: Path) -> None:
        self.root = root
        self.scratch = scratch
        self.stages: list[Stage] = []
        self._commands: list[Command] = []

    def redact(self, text: str) -> str:
        for variant in (str(self.root), self.root.as_posix()):
            text = text.replace(variant, REDACTED)
        return text

    def run(self, args: list[str]) -> str:
        """Run a command that belongs to the current stage."""
        output = self.redact(run_core(args))
        self._commands.append(Command(tuple(args), output))
        return output

    def stage(
        self,
        slug: str,
        title: str,
        caption: str,
        record: str | None = None,
        *,
        stand_in: bool = False,
    ) -> None:
        """Close the current stage with the commands run since the last one."""
        markdown = None
        if record is not None:
            markdown = (self.root / record).read_text(encoding="utf-8")
        self.stages.append(
            Stage(
                slug,
                title,
                caption,
                tuple(self._commands),
                record,
                markdown,
                stand_in,
            )
        )
        self._commands = []


def _prior_research_body(decision: _Decision) -> str:
    return (
        f"# `{decision.feature}` research: `{decision.title}`\n\n"
        f"{decision.problem} This weighs the options the decision chose between.\n\n"
        "## Findings\n\n### The adopted approach fits the current stack\n\n"
        f"{decision.implementation}\n\n## Sources\n\n- `README.md`\n"
    )


def _seed_prior_decisions(session: _Session) -> None:
    """Record the decisions the project already had, each with its evidence."""
    for decision in _PRIOR_DECISIONS:
        research = f"{decision.date}-{decision.feature}-research"
        common = ["--feature", decision.feature, "--date", decision.date]
        run_core(["vault", "add", "research", *common, "--title", decision.title])
        _set_body(research, _prior_research_body(decision), session.scratch)
        adr = ["vault", "add", "adr", *common, "--related", research]
        run_core([*adr, "--title", decision.title])
        _set_body(
            f"{decision.date}-{decision.feature}-adr",
            _prior_body(decision),
            session.scratch,
        )


def _stage_install(session: _Session) -> None:
    session.run(["install"])
    session.stage(
        "01-install",
        "Install",
        "Write the rules, skills, agents and MCP server into the repository.",
    )


def _stage_research(session: _Session) -> Stems:
    title = ["--title", "full-text search options"]
    session.run(["vault", "add", "research", "--feature", FEATURE, *title])
    created = next((session.root / ".vault" / "research").glob(f"*-{FEATURE}-*.md"))
    stems = Stems(created.name.removesuffix(f"-{FEATURE}-research.md"))
    _set_body(stems.research, _RESEARCH_BODY, session.scratch)
    session.stage(
        "02-research",
        "Research",
        "Scaffold a research record; the agent writes the findings and sources.",
        f".vault/research/{stems.research}.md",
    )
    return stems


def _stage_decide(session: _Session, stems: Stems) -> None:
    title = "rank item search with postgres full-text search"
    grounding = ["--related", stems.research]
    session.run(
        ["vault", "add", "adr", "--feature", FEATURE, *grounding, "--title", title]
    )
    _set_body(stems.adr, _decision_body(stems), session.scratch)
    session.stage(
        "03-decide",
        "Decide",
        "Record the decision against its evidence, for your approval.",
        f".vault/adr/{stems.adr}.md",
    )


def _stage_crossref(session: _Session, stems: Stems) -> None:
    with stand_in_provider():
        session.run(["vault", "adr", "crossref", stems.adr, "--apply"])
    session.stage(
        "04-crossref",
        "Cross-reference",
        "TypeSafe ranks every earlier decision; the ones governing the same code "
        "are linked.",
        f".vault/adr/{stems.adr}.md",
        stand_in=True,
    )


def _stage_plan(session: _Session, stems: Stems) -> None:
    # Scaffolded off-screen: the command's next-step hint currently names a
    # retired option, and a published still must not teach it.
    run_core(["vault", "add", "plan", "--feature", FEATURE, "--related", stems.adr])
    _set_body(stems.plan, _plan_body(stems), session.scratch)
    for action, scope in STEPS:
        row = ["--action", action, "--scope", scope]
        session.run(["vault", "plan", "step", "add", FEATURE, *row])
    session.stage(
        "05-plan",
        "Plan",
        "Break the approved decision into verifiable Steps.",
        f".vault/plan/{stems.plan}.md",
    )


def _execute_step(session: _Session, stems: Stems, index: int, *, shown: bool) -> None:
    """Log one Step's ledger rows and close it."""
    step = f"S{index + 1:02d}"
    run = session.run if shown else run_core
    ledger = ["--feature", FEATURE, "--related", stems.plan, "--step", step]
    evidence = ["--row", f"M:{STEPS[index][1]}", "--verify", "pytest tests/search=pass"]
    run(["vault", "exec", "log", *ledger, *evidence])
    run(["vault", "plan", "step", "check", FEATURE, step])


def _stage_execute(session: _Session, stems: Stems) -> None:
    _execute_step(session, stems, 0, shown=True)
    # The second Step runs off-screen so the status view has progress to show.
    _execute_step(session, stems, 1, shown=False)
    session.stage(
        "06-execute",
        "Execute",
        "Log what each Step changed and how it was verified, then close it.",
        f".vault/plan/{stems.plan}.md",
    )


def _stage_views(session: _Session) -> None:
    run_core(["vault", "feature", "index"])
    session.run(["vault", "check", "all", "--fix"])
    session.stage("07-check", "Verify", "Check every record's structure and links.")
    session.run(["status", FEATURE])
    session.stage("08-status", "Track", "See progress and the next open Step.")
    session.run(["vault", "graph", "--feature", FEATURE])
    session.stage("09-graph", "Trace", "Follow the feature's records and their links.")


def build(root: Path) -> list[Stage]:
    """Build the ``search-api`` feature in the git repository at *root*.

    Returns:
        The stages, in order, with each command's genuine output.
    """
    scratch = root.parent / "bodies"
    scratch.mkdir(exist_ok=True)
    session = _Session(root, scratch)
    _stage_install(session)
    _seed_prior_decisions(session)
    stems = _stage_research(session)
    _stage_decide(session, stems)
    _stage_crossref(session, stems)
    _stage_plan(session, stems)
    _stage_execute(session, stems)
    _stage_views(session)
    return session.stages


@contextlib.contextmanager
def walkthrough() -> Generator[list[Stage]]:
    """Build the feature in a throwaway repository and yield its stages.

    The working directory is the repository while the build runs, as it is
    for a user, and is restored afterwards.
    """
    origin = Path.cwd()
    with tempfile.TemporaryDirectory(prefix=TEMP_PREFIX) as tmp:
        root = Path(tmp) / FEATURE
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        os.chdir(root)
        try:
            yield build(root)
        finally:
            os.chdir(origin)


def main() -> None:
    """Print every stage's commands and output: a quick look without rendering."""
    with walkthrough() as stages:
        for stage in stages:
            print(f"== {stage.slug}: {stage.title} - {stage.caption}")
            for command in stage.commands:
                print(f"$ {command.shown}")
                print(command.output)
        print(json.dumps([stage.slug for stage in stages]))


if __name__ == "__main__":
    main()
