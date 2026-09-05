"""Tests holding builtin content to one home for the discovery sequence.

The sequence (locate by meaning, read the epicenter whole, confirm with grep)
and the two facts it rests on (how ``vaultspec-rag`` is invoked, what to do
when it is absent) are defined once, in ``rules/vaultspec-discovery.builtin.md``.
Every other entry point cites the rule by name; the four roles whose job is
search itself are registered restaters and carry the invocation verbatim.

No test here counts anything. Each asserts a relation between the registry in
``core.discovery_guidance`` and the tree:
the home defines every canonical sentence, restaters restate, citers cite,
and any rag invocation anywhere is spelled the canonical way.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.builtins import builtins_root
from vaultspec_core.core.discovery_guidance import (
    DISCOVERY_CANONICAL_SENTENCES,
    DISCOVERY_FALLBACK,
    DISCOVERY_HOME,
    DISCOVERY_RESTATERS,
    DISCOVERY_RULE,
    DISCOVERY_SEQUENCE_MARKER,
    MCP_ONLY_CAPABILITIES,
    RAG_SEARCH_FLAGS,
    SEARCH_ADR,
    SEARCH_CODE,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_BUILTINS = builtins_root()
_RAG = "vaultspec-rag"
_RAG_SEARCH = re.compile(r"`vaultspec-rag search [^`]*`")


def _rel(path: Path) -> str:
    return path.relative_to(_BUILTINS).as_posix()


def _normalized(text: str) -> str:
    """Collapse whitespace so a line-wrapped sentence matches as one unit."""
    return re.sub(r"\s+", " ", text)


def _read(path: Path) -> str:
    return _normalized(path.read_text(encoding="utf-8"))


def _builtin_docs() -> list[Path]:
    return sorted(_BUILTINS.rglob("*.md"))


def _entry_point_docs() -> list[Path]:
    """Builtins a model loads standing alone: system parts, rules, agents, SKILL.md.

    A reference under a skill's ``references/`` is read in the context of the
    SKILL.md that points at it, so the citation contract does not apply there.
    The canonical-spelling contract does: a wrong flag is wrong wherever it is.
    """
    return [
        p
        for p in _builtin_docs()
        if p.parent.name in ("system", "rules", "agents") or p.name == "SKILL.md"
    ]


@pytest.fixture(scope="module")
def entry_points() -> dict[str, str]:
    """Relative path -> whitespace-normalized text. Fails loudly when empty."""
    docs = {_rel(p): _read(p) for p in _entry_point_docs()}
    assert docs, f"no entry-point builtins under {_BUILTINS}"
    assert DISCOVERY_HOME in docs, (
        f"discovery home {DISCOVERY_HOME} is not an entry point"
    )
    return docs


class TestRegistryIsGrounded:
    """The registry describes the tree. A stale registry fails before any prose does."""

    def test_home_defines_every_canonical_sentence(self, entry_points: dict[str, str]):
        home = entry_points[DISCOVERY_HOME]
        missing = [
            s for s in DISCOVERY_CANONICAL_SENTENCES if _normalized(s) not in home
        ]
        assert not missing, f"{DISCOVERY_HOME} no longer defines: {missing}"

    def test_every_registered_restater_exists_and_restates(
        self, entry_points: dict[str, str]
    ):
        """A restater that stopped mentioning rag is a stale registry entry."""
        stale = [
            r
            for r in sorted(DISCOVERY_RESTATERS)
            if r not in entry_points or _RAG not in entry_points[r]
        ]
        assert not stale, f"registered restaters that do not restate: {stale}"


class TestSequenceHasOneHome:
    def test_non_restaters_cite_the_rule_and_do_not_spell_rag(
        self, entry_points: dict[str, str]
    ):
        """Outside the home and the restaters, rag is cited, never invoked.

        A file that uses the sequence vocabulary must name the rule; a file
        that names rag has grown a second definition of the tool contract.
        """
        offenders: list[tuple[str, str]] = []
        for rel, body in entry_points.items():
            if rel == DISCOVERY_HOME or rel in DISCOVERY_RESTATERS:
                continue
            if _RAG in body:
                offenders.append((rel, f"spells {_RAG}; cite `{DISCOVERY_RULE}`"))
            if DISCOVERY_SEQUENCE_MARKER in body and f"`{DISCOVERY_RULE}`" not in body:
                offenders.append(
                    (rel, f"restates the sequence without citing `{DISCOVERY_RULE}`")
                )
        assert not offenders, f"second homes for the discovery sequence: {offenders}"

    def test_every_rag_mentioning_entry_point_states_the_fallback(
        self, entry_points: dict[str, str]
    ):
        """Wherever rag is spelled out standing alone, its absence is covered.

        Restated verbatim: the fallback names core's own discovery verbs, and a
        paraphrase that names only grep describes a narrower path than the
        one core ships.
        """
        canonical = _normalized(DISCOVERY_FALLBACK)
        offenders = [
            rel
            for rel, body in entry_points.items()
            if _RAG in body and canonical not in body
        ]
        assert not offenders, (
            f"{_RAG} spelled without the canonical fallback: {offenders}"
        )


class TestInvocationsAreCanonical:
    def test_every_rag_search_invocation_is_a_canonical_spelling(self):
        """Any ``vaultspec-rag search`` span, anywhere, is SEARCH_CODE or SEARCH_ADR.

        Covers references too: the ADR spelling carries the ``--doc-type adr``
        filter for a recall reason, and a variant query string teaches a
        different query.
        """
        allowed = {SEARCH_CODE, SEARCH_ADR}
        offenders = [
            (_rel(p), span)
            for p in _builtin_docs()
            for span in _RAG_SEARCH.findall(_read(p))
            if span not in allowed
        ]
        assert not offenders, f"non-canonical rag invocations: {offenders}"

    def test_no_builtin_spells_an_mcp_only_capability_as_a_cli_flag(self):
        """Intent ranking, feedback, and domain filters have no CLI flag."""
        offenders = [
            (_rel(p), flag)
            for p in _builtin_docs()
            for body in [p.read_text(encoding="utf-8")]
            if _RAG in body
            for flag in MCP_ONLY_CAPABILITIES
            if re.search(rf"{re.escape(flag)}\b", body)
        ]
        assert not offenders, f"MCP-only capability spelled as a CLI flag: {offenders}"

    def test_every_rag_flag_on_an_invocation_line_exists(self):
        """A flag beside ``vaultspec-rag`` is one rag's parser accepts."""
        offenders = sorted(
            {
                (_rel(p), flag)
                for p in _builtin_docs()
                for line in p.read_text(encoding="utf-8").splitlines()
                if _RAG in line
                for flag in re.findall(r"--[a-z][a-z-]*", line)
                if flag not in RAG_SEARCH_FLAGS
            }
        )
        assert not offenders, f"rag flag that does not exist: {offenders}"
