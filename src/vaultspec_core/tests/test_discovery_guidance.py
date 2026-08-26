"""Tests holding builtin content to one semantic-search vocabulary.

Builtin agents, skills, and rules stay authored documents with their own
role-specific framing - an executor's locate step and a curator's index-hygiene
step are genuinely different instructions and must not be flattened into one
block. What must not vary is the shared vocabulary: how rag's search is spelled,
and what a model should do when rag is absent.

Before this suite that fallback was stated in five different wordings across
seventeen files, two of which named only ``rg``/``fd`` and so described a
degraded path narrower than the one core actually ships.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

from vaultspec_core.core.discovery_guidance import (
    DISCOVERY_FALLBACK,
    MCP_ONLY_CAPABILITIES,
    RAG_SEARCH_FLAGS,
)

_BUILTINS = Path(__file__).resolve().parents[1] / "builtins"
_RAG = "vaultspec-rag"


def _builtin_docs() -> list[Path]:
    return sorted(_BUILTINS.rglob("*.md"))


def _entry_point_docs() -> list[Path]:
    """Builtins a model loads on its own: agents, skill roots, and rules.

    A nested reference under a skill's ``references/`` directory is read in the
    context of the ``SKILL.md`` that points at it, so requiring the fallback
    sentence there too would pad prose without informing anyone - the reader
    has already been told. Entry points are where the contract has to hold,
    because they are what gets loaded standing alone.
    """
    return [
        path
        for path in _builtin_docs()
        if path.parent.name in ("agents", "rules") or path.name == "SKILL.md"
    ]


def _mentions_rag(path: Path) -> bool:
    return _RAG in path.read_text(encoding="utf-8", errors="ignore")


def _normalized(text: str) -> str:
    """Collapse whitespace so a line-wrapped sentence matches as one unit."""
    return re.sub(r"\s+", " ", text)


class TestFallbackIsSingular:
    def test_every_rag_mentioning_builtin_states_the_canonical_fallback(self):
        """One wording, everywhere it is stated at all."""
        canonical = _normalized(DISCOVERY_FALLBACK)
        offenders: list[str] = []
        for path in _entry_point_docs():
            if not _mentions_rag(path):
                continue
            body = _normalized(path.read_text(encoding="utf-8"))
            if canonical not in body:
                offenders.append(path.name)
        assert not offenders, (
            f"builtins mentioning {_RAG} without the canonical fallback "
            f"sentence: {offenders}"
        )

    def test_no_superseded_fallback_wording_survives(self):
        """The old variants are gone, including the rg/fd-only ones.

        Those two were not merely differently worded - they were narrower than
        the truth, naming only grep tooling where core's own discovery verbs
        carry the orientation half of the sequence.
        """
        superseded = [
            "carry the locate",
            "fall back to the CLI discovery verbs",
            "`rg`/`fd` carry",
        ]
        offenders: list[tuple[str, str]] = []
        for path in _builtin_docs():
            body = _normalized(path.read_text(encoding="utf-8", errors="ignore"))
            for phrase in superseded:
                if _normalized(phrase) in body:
                    offenders.append((path.name, phrase))
        assert not offenders, f"superseded fallback wording still present: {offenders}"


class TestNoInventedFlags:
    def test_builtins_never_spell_an_mcp_only_capability_as_a_cli_flag(self):
        """rag's best capabilities have no CLI flag; prose must not invent one.

        ``intent`` ranking, relevance feedback, and the noise-domain filters
        are MCP-tool and inline-token only. A reader cannot detect an invented
        flag without going and reading rag's argument parser, so the check
        belongs here.
        """
        offenders: list[tuple[str, str]] = []
        for path in _builtin_docs():
            body = path.read_text(encoding="utf-8", errors="ignore")
            if _RAG not in body:
                continue
            for flag in MCP_ONLY_CAPABILITIES:
                if re.search(rf"{re.escape(flag)}\b", body):
                    offenders.append((path.name, flag))
        assert not offenders, (
            f"builtin names an MCP-only capability as a CLI flag: {offenders}"
        )

    def test_every_rag_flag_named_in_builtins_actually_exists(self):
        """No typo'd or hallucinated flag on a rag invocation line."""
        offenders: list[tuple[str, str]] = []
        for path in _builtin_docs():
            body = path.read_text(encoding="utf-8", errors="ignore")
            for line in body.splitlines():
                if _RAG not in line:
                    continue
                for flag in re.findall(r"--[a-z][a-z-]*", line):
                    if flag not in RAG_SEARCH_FLAGS:
                        offenders.append((path.name, flag))
        assert not offenders, (
            f"builtin names a rag flag that does not exist: {sorted(set(offenders))}"
        )


class TestCoverage:
    def test_the_suite_actually_inspects_something(self):
        """Guard against the whole suite passing vacuously."""
        mentioning = [p.name for p in _entry_point_docs() if _mentions_rag(p)]
        assert len(mentioning) >= 15, (
            f"expected the rag vocabulary across many builtins, found "
            f"{len(mentioning)}: {mentioning}"
        )
