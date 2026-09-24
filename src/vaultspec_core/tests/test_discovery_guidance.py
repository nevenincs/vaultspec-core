"""Tests holding builtin content to one home for the discovery sequence.

The sequence (locate by meaning, read the epicenter whole, confirm with grep)
and the two facts it rests on (how ``vaultspec-rag`` is invoked, what to do
when it is absent) are defined once, in ``rules/vaultspec-discovery.builtin.md``.
Every other entry point cites the rule by name. The two curation roles may
name rag to keep its code index current, and cite the rule for the rest.

Decision and vault-fact questions are routed by one state-free sentence:
core's ``search``, and when it declines or fails, the next step its reply
names. That sentence and every hosted-search invocation live in the rule
alone; other builtins cite the rule. No builtin offers rag's vault search
itself; the reply does, when the workspace provisions rag.

No test here counts anything. Each asserts a relation between the registry in
``core.discovery_guidance`` and the tree:
the home defines every canonical sentence and quotes every negative search
verdict the way the search package words it, citers cite, any rag or
hosted-search invocation anywhere is spelled the canonical way, and rag is
invoked only for code.
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
    DISCOVERY_RULE,
    DISCOVERY_SEQUENCE_MARKER,
    MCP_ONLY_CAPABILITIES,
    RAG_INDEX_CHECKERS,
    RAG_SEARCH_FLAGS,
    SEARCH_CODE,
    SEARCH_VAULT,
)
from vaultspec_core.search import SearchVerdict

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_BUILTINS = builtins_root()
_RAG = "vaultspec-rag"
_RAG_SEARCH = re.compile(r"`vaultspec-rag search [^`]*`")
# An invocation carries a quoted question; the bare verb name and its usage
# signature are references, not instructions, and are not held to a spelling.
_VAULT_SEARCH = re.compile(r'`vaultspec-core vault search "[^`]*`')


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

    def test_every_registered_index_checker_exists_and_names_rag(
        self, entry_points: dict[str, str]
    ):
        """An index checker that stopped naming rag is a stale registry entry."""
        stale = [
            r
            for r in sorted(RAG_INDEX_CHECKERS)
            if r not in entry_points or _RAG not in entry_points[r]
        ]
        assert not stale, f"registered index checkers that do not name rag: {stale}"


class TestSequenceHasOneHome:
    def test_non_restaters_cite_the_rule_and_do_not_spell_rag(
        self, entry_points: dict[str, str]
    ):
        """Outside the home and the index checkers, rag is never named.

        A file that uses the sequence vocabulary must name the rule; a file
        that names rag has grown a second definition of the tool contract.
        """
        offenders: list[tuple[str, str]] = []
        for rel, body in entry_points.items():
            if rel == DISCOVERY_HOME or rel in RAG_INDEX_CHECKERS:
                continue
            if _RAG in body:
                offenders.append((rel, f"spells {_RAG}; cite `{DISCOVERY_RULE}`"))
            if DISCOVERY_SEQUENCE_MARKER in body and f"`{DISCOVERY_RULE}`" not in body:
                offenders.append(
                    (rel, f"restates the sequence without citing `{DISCOVERY_RULE}`")
                )
        assert not offenders, f"second homes for the discovery sequence: {offenders}"

    def test_every_rag_naming_entry_point_cites_the_rule(
        self, entry_points: dict[str, str]
    ):
        """Wherever rag is named outside the home, the rule covers its absence.

        The fallback lives in the rule alone; a file that names rag and does
        not cite the rule leaves its reader without it.
        """
        offenders = [
            rel
            for rel, body in entry_points.items()
            if rel != DISCOVERY_HOME
            and _RAG in body
            and f"`{DISCOVERY_RULE}`" not in body
        ]
        assert not offenders, f"{_RAG} named without citing the rule: {offenders}"

    def test_code_search_and_fallback_are_spelled_only_in_the_home(self):
        """The invocation and the fallback have one home; others cite the rule."""
        offenders = [
            (_rel(p), sentence)
            for p in _builtin_docs()
            if _rel(p) != DISCOVERY_HOME
            for sentence in (SEARCH_CODE, DISCOVERY_FALLBACK)
            if _normalized(sentence) in _read(p)
        ]
        assert not offenders, f"restated outside {DISCOVERY_HOME}: {offenders}"


#: A quoted verdict sentence as guidance spells it: every search verdict the
#: CLI prints for a page without an answer ends this way.
_QUOTED_VERDICT = re.compile(r'"([^"]* answers this)"')

#: The verdicts a reader must act on; ``answered`` needs no instruction.
_NEGATIVE_VERDICTS = [v for v in SearchVerdict if v is not SearchVerdict.ANSWERED]


class TestVerdictsMatchTheSearchPackage:
    """Quoted verdicts are the search package's own words, with the wire value.

    The CLI prints the sentence; MCP and ``--json`` carry the value. A rule
    that quotes a sentence the package no longer prints, or omits the value an
    MCP reader sees, leaves its reader unable to match the reply.
    """

    @pytest.mark.parametrize("verdict", _NEGATIVE_VERDICTS, ids=lambda v: v.value)
    def test_home_quotes_each_negative_verdict_with_its_value(
        self, entry_points: dict[str, str], verdict: SearchVerdict
    ):
        home = entry_points[DISCOVERY_HOME]
        assert f'"{verdict.sentence}" (`{verdict.value}`)' in home, (
            f"{DISCOVERY_HOME} does not quote {verdict.value!r} with its sentence"
        )

    def test_every_quoted_verdict_is_a_search_verdict_with_its_value(self):
        by_sentence = {v.sentence: v for v in SearchVerdict}
        offenders: list[tuple[str, str]] = []
        for p in _builtin_docs():
            body = _read(p)
            for quoted in _QUOTED_VERDICT.findall(body):
                verdict = by_sentence.get(quoted)
                if verdict is None or f"`{verdict.value}`" not in body:
                    offenders.append((_rel(p), quoted))
        assert not offenders, f"quoted verdicts off the search package: {offenders}"


#: A sentence that names ``status`` and hosted search together: the shape of a
#: route chosen from orientation state.
_STATUS_GATE = re.compile(r"`status`[^.;]*hosted search|hosted search[^.;]*`status`")


class TestRoutingIsStateFree:
    def test_no_entry_point_routes_discovery_on_status(
        self, entry_points: dict[str, str]
    ):
        """Discovery routing never waits on what ``status`` reports.

        A dispatched worker or a read-only session skips orientation, and a
        configured key can still be rejected, so a route chosen from ``status``
        is chosen from state the reader may not have. The search reply names
        the next step instead.
        """
        offenders = [
            rel for rel, body in entry_points.items() if _STATUS_GATE.search(body)
        ]
        assert not offenders, f"discovery routed on status: {offenders}"


class TestVaultSearchHasOneHome:
    def test_hosted_search_is_invoked_only_in_the_home(self):
        """Outside the rule, vault search is cited through the rule, never invoked.

        A second copy of the routing sentence drifts from the first the next
        time the degradation chain changes, and a reader holding the stale copy
        cannot tell.
        """
        offenders = [
            _rel(p)
            for p in _builtin_docs()
            if _rel(p) != DISCOVERY_HOME and _VAULT_SEARCH.search(_read(p))
        ]
        assert not offenders, f"hosted search invoked outside the rule: {offenders}"


class TestInvocationsAreCanonical:
    def test_every_rag_search_invocation_is_the_code_search(self):
        """Any ``vaultspec-rag search`` span, anywhere, is SEARCH_CODE.

        Vault questions go to core's ``search``, whose reply names a rag vault
        search when the workspace provisions rag, over the record types asked
        for. A builtin that offered one itself would choose a route from state
        it cannot see. Covers references too: a playbook read beside its
        SKILL.md still instructs the search it names, and a variant query
        string teaches a different query.
        """
        offenders = [
            (_rel(p), span)
            for p in _builtin_docs()
            for span in _RAG_SEARCH.findall(_read(p))
            if span != SEARCH_CODE
        ]
        assert not offenders, f"non-code rag invocations: {offenders}"

    def test_every_hosted_search_invocation_is_the_canonical_spelling(self):
        """Any hosted-search invocation with a question, anywhere, is SEARCH_VAULT."""
        offenders = [
            (_rel(p), span)
            for p in _builtin_docs()
            for span in _VAULT_SEARCH.findall(_read(p))
            if span != SEARCH_VAULT
        ]
        assert not offenders, f"non-canonical hosted-search invocations: {offenders}"

    def test_no_builtin_spells_an_mcp_only_capability_as_a_cli_flag(self):
        """Intent ranking, feedback, and domain filters have no CLI flag.

        Scoped to paragraphs that name rag: an invocation wraps across lines,
        and a reference documenting core's own ``--intent`` elsewhere in the
        same file is not describing rag.
        """
        offenders = [
            (_rel(p), flag)
            for p in _builtin_docs()
            for paragraph in re.split(r"\n\s*\n", p.read_text(encoding="utf-8"))
            if _RAG in paragraph
            for flag in MCP_ONLY_CAPABILITIES
            if re.search(rf"{re.escape(flag)}\b", paragraph)
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
