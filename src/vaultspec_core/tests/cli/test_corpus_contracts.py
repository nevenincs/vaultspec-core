"""Contracts the builtin corpus owes the code it describes.

Replaces ``test_vaultspec_rule_contracts.py``, which held a list of
strings that once appeared in the prose and must not reappear. Those guards
could only fail on a wording someone had already typed; they said nothing
about a new wording that was equally wrong.

Each test here resolves what the prose names against the thing that owns it:
commands and flags against the Typer tree, MCP tool names against the server
catalog, skill and persona and rule names against the builtins tree, paths
against the seeded layout, template placeholders against the hydrator, and
the always-on layer against one declared budget. The denylist that remains is
small and every entry carries its reason.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.builtins import builtins_root
from vaultspec_core.cli import app
from vaultspec_core.core.corpus_contracts import (
    ALWAYS_ON_WORD_BUDGET,
    AUTHOR_FILLED_PLACEHOLDERS,
    EXTERNAL_VAULTSPEC_NAMES,
    FORBIDDEN_VOCABULARY,
    MACHINE_FILLED_PLACEHOLDERS,
    RUNTIME_VAULTSPEC_PATHS,
    SYNTHESIZED_RULES,
)
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.tests.cli.reference_contract import (
    collect_group_paths,
    collect_leaf_command_paths,
    command_options,
)
from vaultspec_core.vaultcore import parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_BUILTINS = builtins_root()
_REFERENCE_DIR = _BUILTINS / "reference"

_COMMAND_SPAN = re.compile(r"`vaultspec-core ([^`]+)`")
_VAULTSPEC_NAME = re.compile(r"\bvaultspec-[a-z][a-z-]*")
_DOTVAULTSPEC_PATH = re.compile(r"\.vaultspec/([A-Za-z0-9_./*-]*)")
_MCP_LINE_TOOL = re.compile(r"`([a-z_]+)`")
_PLACEHOLDER = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_*|-]*)\}")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_PLACEHOLDER_ARG = re.compile(r"^(<.*>|\{.*\}|\[.*\]|[SP]##|OLD|NEW|\.\.\.)$")


def _rel(path: Path) -> str:
    return path.relative_to(_BUILTINS).as_posix()


def _docs() -> list[Path]:
    docs = sorted(_BUILTINS.rglob("*.md"))
    assert docs, f"no builtin markdown under {_BUILTINS}"
    return docs


def _prose_docs() -> list[Path]:
    """Everything except the generated CLI reference, which has its own drift suite."""
    return [p for p in _docs() if p.parent != _REFERENCE_DIR]


@pytest.fixture(scope="module")
def live_paths() -> tuple[set[tuple[str, ...]], set[tuple[str, ...]]]:
    leaves = set(collect_leaf_command_paths(app))
    groups = set(collect_group_paths(app))
    assert leaves, "Typer app registered no commands"
    return leaves, groups


@pytest.fixture(scope="module")
def cli() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


@pytest.fixture(scope="module")
def mcp_tool_names() -> set[str]:
    names = {t.name for t in asyncio.run(create_server().list_tools())}
    assert names, "MCP server registered no tools"
    return names


# ---------------------------------------------------------------------------
# Commands and flags
# ---------------------------------------------------------------------------


def _alternatives(span: str) -> list[list[str]]:
    """Expand ``a b c | d | e`` and ``add/move/remove`` shorthands into token lists.

    ``|`` alternatives share the prefix before the first alternative's last
    token (``vault plan step | phase`` means ``vault plan step`` or
    ``vault plan phase``). ``/`` alternatives are within one token and may be
    line-wrapped, so whitespace is collapsed first.
    """
    span = re.sub(r"\s+", " ", span).strip()
    branches = [b.strip().split() for b in span.split(" | ")]
    prefix = branches[0][:-1] if len(branches) > 1 else []
    tails = [branches[0][-1:], *branches[1:]] if len(branches) > 1 else branches
    variants: list[list[str]] = []
    for tail in tails:
        expanded: list[list[str]] = [list(prefix)]
        for token in tail:
            choices = (
                [c for c in token.split("/") if c]
                if "/" in token and not token.startswith("<")
                else [token]
            )
            expanded = [[*p, c] for p in expanded for c in choices]
        variants.extend(expanded)
    return variants


def _resolve(
    tokens: list[str],
    leaves: set[tuple[str, ...]],
    groups: set[tuple[str, ...]],
) -> tuple[tuple[str, ...] | None, list[str]]:
    """Longest live prefix and the tokens left over."""
    path: tuple[str, ...] = ()
    rest = list(tokens)
    while rest:
        candidate = (*path, rest[0])
        if candidate in leaves or candidate in groups:
            path = candidate
            rest.pop(0)
            continue
        break
    return (path or None), rest


class TestCommandsNamedInProseExist:
    def test_every_vaultspec_core_span_resolves_to_a_live_command(
        self,
        live_paths: tuple[set[tuple[str, ...]], set[tuple[str, ...]]],
        cli: CliRunner,
    ):
        """Every backticked ``vaultspec-core ...`` names a command the app has,
        and every ``--flag`` in it is one that command accepts.

        Tokens that are placeholders (``<feature>``, ``S##``, ``OLD``) or
        positional arguments are not checked; the reference drift suite owns
        argument shape. Prefix-and-alternative spellings (``step | phase``,
        ``add/move/remove``) are expanded and each alternative must resolve.
        """
        leaves, groups = live_paths
        offenders: list[tuple[str, str, str]] = []
        for doc in _prose_docs():
            for span in _COMMAND_SPAN.findall(doc.read_text(encoding="utf-8")):
                if span.strip() == "<cmd>":
                    continue
                for tokens in _alternatives(span):
                    words = [t for t in tokens if not t.startswith("-")]
                    path, rest = _resolve(words, leaves, groups)
                    if path is None:
                        offenders.append((_rel(doc), span, "no such command"))
                        continue
                    unexpected = [
                        t
                        for t in rest
                        if not _PLACEHOLDER_ARG.match(t) and path not in leaves
                    ]
                    if unexpected:
                        offenders.append(
                            (_rel(doc), span, f"unknown subcommand {unexpected}")
                        )
                    if path in leaves:
                        accepted = command_options(cli, app, path)
                        for flag in (t for t in tokens if t.startswith("--")):
                            if flag not in accepted:
                                offenders.append(
                                    (_rel(doc), span, f"{' '.join(path)} has no {flag}")
                                )
        assert not offenders, "\n".join(
            f"{d}: `vaultspec-core {s}` -> {why}" for d, s, why in offenders
        )


class TestMcpToolsNamedInProseExist:
    def test_every_tool_named_on_an_mcp_line_is_registered(
        self, mcp_tool_names: set[str]
    ):
        """A backticked snake_case name on a line that says ``MCP`` is a tool name."""
        offenders = [
            (_rel(doc), name)
            for doc in _prose_docs()
            for line in doc.read_text(encoding="utf-8").splitlines()
            if "MCP" in line
            for name in _MCP_LINE_TOOL.findall(line)
            if name not in mcp_tool_names
        ]
        assert not offenders, (
            f"MCP tool names the server does not register: {offenders}"
        )


# ---------------------------------------------------------------------------
# Names and paths
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_names() -> set[str]:
    """Every ``vaultspec-*`` name the tree defines: skills, agents, rules."""
    names = {
        p.name for p in (_BUILTINS / "skills").iterdir() if (p / "SKILL.md").is_file()
    }
    names |= {p.stem for p in (_BUILTINS / "agents").glob("*.md")}
    names |= {
        p.name.removesuffix(".builtin.md")
        for p in (_BUILTINS / "rules").glob("*.builtin.md")
    }
    assert names, "builtins tree defines no skills, agents, or rules"
    return names | SYNTHESIZED_RULES | EXTERNAL_VAULTSPEC_NAMES


class TestNamesInProseExist:
    def test_every_vaultspec_name_is_a_skill_persona_rule_or_registered_external(
        self, corpus_names: set[str]
    ):
        offenders = sorted(
            {
                (_rel(doc), name)
                for doc in _docs()
                for name in _VAULTSPEC_NAME.findall(doc.read_text(encoding="utf-8"))
                if name not in corpus_names
            }
        )
        assert not offenders, f"vaultspec-* names with no file behind them: {offenders}"

    def test_every_dotvaultspec_path_is_seeded_or_registered_runtime(self):
        """``.vaultspec/<rel>`` resolves under the builtins root.

        Seeding copies the tree as-is, so the two layouts are identical.
        """
        offenders: list[tuple[str, str]] = []
        for doc in _docs():
            for rel in _DOTVAULTSPEC_PATH.findall(doc.read_text(encoding="utf-8")):
                rel = rel.rstrip("./")
                if not rel or rel in RUNTIME_VAULTSPEC_PATHS:
                    continue
                if "*" in rel:
                    parent = rel.split("*", 1)[0].rstrip("/")
                    if not (_BUILTINS / parent).is_dir():
                        offenders.append((_rel(doc), rel))
                    continue
                if not (_BUILTINS / rel).exists():
                    offenders.append((_rel(doc), rel))
        assert not offenders, (
            f".vaultspec paths that seeding does not create: {offenders}"
        )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TestTemplatePlaceholders:
    def test_every_placeholder_outside_hint_comments_is_filled_by_machine_or_author(
        self,
    ):
        """A placeholder the hydrator does not fill reaches the author unfilled.

        Placeholders inside ``<!-- -->`` are the template's own guidance and
        are removed by the annotations checker; they are not scanned.
        """
        allowed = MACHINE_FILLED_PLACEHOLDERS | AUTHOR_FILLED_PLACEHOLDERS
        templates = sorted((_BUILTINS / "templates").glob("*.md"))
        assert templates, "no templates shipped"
        offenders = sorted(
            {
                (t.name, name)
                for t in templates
                for name in _PLACEHOLDER.findall(
                    _HTML_COMMENT.sub("", t.read_text(encoding="utf-8"))
                )
                if name not in allowed
            }
        )
        assert not offenders, f"placeholders nothing fills: {offenders}"


# ---------------------------------------------------------------------------
# Always-on budget
# ---------------------------------------------------------------------------


def _always_on_docs() -> list[Path]:
    """What every session pays: shared system parts plus builtin rules.

    Mirrors the selection in ``core/system.py``.
    """
    shared = []
    for part in sorted((_BUILTINS / "system").glob("*.md")):
        meta, _body = parse_frontmatter(part.read_text(encoding="utf-8"))
        if meta.get("tool") is None and meta.get("pipeline") != "config":
            shared.append(part)
    return shared + sorted((_BUILTINS / "rules").glob("*.builtin.md"))


class TestAlwaysOnBudget:
    def test_always_on_layer_is_within_budget(self):
        docs = _always_on_docs()
        assert docs, "no always-on builtins found"
        counts = {
            _rel(p): len(parse_frontmatter(p.read_text(encoding="utf-8"))[1].split())
            for p in docs
        }
        total = sum(counts.values())
        report = "\n".join(
            f"  {n:6d}  {rel}"
            for rel, n in sorted(counts.items(), key=lambda kv: -kv[1])
        )
        assert total <= ALWAYS_ON_WORD_BUDGET, (
            f"always-on layer is {total} words, "
            f"budget {ALWAYS_ON_WORD_BUDGET}:\n{report}"
        )


# ---------------------------------------------------------------------------
# Forbidden vocabulary
# ---------------------------------------------------------------------------


class TestForbiddenVocabulary:
    @pytest.mark.parametrize(("needle", "reason"), sorted(FORBIDDEN_VOCABULARY.items()))
    def test_forbidden_vocabulary_is_absent(self, needle: str, reason: str):
        hits = [
            _rel(doc)
            for doc in _prose_docs()
            if needle in doc.read_text(encoding="utf-8")
        ]
        assert not hits, f"{needle!r} ({reason}) in {hits}"
