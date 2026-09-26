"""The next step, verdict and record-type filter every search surface reports.

The next step is resolved from a real ``.mcp.json`` on disk, rendered through
core's own launch renderer, so the rag and no-rag branches are reached from
the same input the companion probe reads in a real workspace.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY
from vaultspec_core.core.diagnosis.collectors_companion import RAG_DISTRIBUTION_NAME
from vaultspec_core.core.discovery_guidance import LIST_VAULT, RAG_VAULT_SEARCH
from vaultspec_core.core.enums import InstallMode, TypeSafeModel
from vaultspec_core.core.mcps_mode import render_launch_for_mode
from vaultspec_core.search import (
    SEARCHABLE_TYPES,
    NextStep,
    NextStepKind,
    SearchOutcome,
    SearchStatus,
    SearchUsage,
    SearchVerdict,
    UnavailableReason,
    UnsearchableTypeError,
    remediation,
)
from vaultspec_core.search._filters import record_types
from vaultspec_core.search._remediation import next_step
from vaultspec_core.vaultcore.models import DocType

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _provision_rag(root: Path) -> None:
    """Write the ``.mcp.json`` entry core renders for a tool-mode rag."""
    command, args = render_launch_for_mode(
        InstallMode.TOOL,
        RAG_DISTRIBUTION_NAME,
        "vaultspec_rag.server",
        tool_spec=f"{RAG_DISTRIBUTION_NAME}[mcp]",
    )
    servers = {RAG_DISTRIBUTION_NAME: {"command": command, "args": args}}
    (root / ".mcp.json").write_text(
        json.dumps({"mcpServers": servers}), encoding="utf-8"
    )


def _declined(step: NextStep, reason: UnavailableReason | None = None) -> SearchOutcome:
    status = SearchStatus.NOT_CONFIGURED if reason is None else SearchStatus.UNAVAILABLE
    return SearchOutcome(status=status, query="q", reason=reason, next_step=step)


_EVERY_TYPE = ",".join(sorted(SEARCHABLE_TYPES))


class TestNextStep:
    def test_without_rag_it_is_the_listing_verb_over_every_type(
        self, tmp_path: Path
    ) -> None:
        step = next_step(tmp_path, None)

        assert step.kind is NextStepKind.LISTING
        assert step.command == LIST_VAULT
        assert step.types == tuple(sorted(SEARCHABLE_TYPES))

    def test_one_requested_type_narrows_the_listing_verb(self, tmp_path: Path) -> None:
        step = next_step(tmp_path, frozenset({DocType.ADR}))

        assert step.command == f"{LIST_VAULT} adr"
        assert step.types == (DocType.ADR,)

    def test_a_rag_entry_that_does_not_parse_still_leaves_the_listing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".mcp.json").write_text("{not json", encoding="utf-8")

        assert next_step(tmp_path, None).kind is NextStepKind.LISTING

    def test_with_rag_it_is_a_rag_vault_search_over_every_type(
        self, tmp_path: Path
    ) -> None:
        _provision_rag(tmp_path)

        step = next_step(tmp_path, None)

        assert step.kind is NextStepKind.RAG_SEARCH
        assert step.command == f"{RAG_VAULT_SEARCH} --doc-type {_EVERY_TYPE}"

    def test_with_rag_the_doc_type_union_is_the_requested_types(
        self, tmp_path: Path
    ) -> None:
        _provision_rag(tmp_path)

        step = next_step(tmp_path, frozenset({DocType.PLAN, DocType.ADR}))

        assert step.command == f"{RAG_VAULT_SEARCH} --doc-type adr,plan"
        assert step.types == (DocType.ADR, DocType.PLAN)

    def test_with_rag_the_search_keeps_the_feature_and_date(
        self, tmp_path: Path
    ) -> None:
        _provision_rag(tmp_path)

        step = next_step(
            tmp_path, frozenset({DocType.ADR}), feature="#Search", date="2026-09-23"
        )

        assert step.command == (
            f"{RAG_VAULT_SEARCH} --doc-type adr --feature search --date 2026-09-23"
        )

    def test_the_listing_verb_keeps_the_feature_and_date(self, tmp_path: Path) -> None:
        step = next_step(tmp_path, None, feature="search", date="2026-09-23")

        assert step.command == f"{LIST_VAULT} --feature search --date 2026-09-23"

    def test_a_malformed_filter_never_reaches_the_command(self, tmp_path: Path) -> None:
        step = next_step(tmp_path, None, feature="x; rm -rf .", date="soon")

        assert step.command == LIST_VAULT

    def test_types_are_held_as_record_types_in_name_order(self) -> None:
        step = NextStep(
            kind=NextStepKind.LISTING, types=(DocType.PLAN, DocType.ADR), command="c"
        )

        assert step.types == (DocType.ADR, DocType.PLAN)
        assert all(isinstance(doc_type, DocType) for doc_type in step.types)


class TestRemediation:
    def test_a_ranked_outcome_needs_no_remediation(self) -> None:
        assert remediation(SearchOutcome(status=SearchStatus.OK, query="q")) is None

    def test_not_configured_names_the_variable_and_the_rag_search(
        self, tmp_path: Path
    ) -> None:
        _provision_rag(tmp_path)
        step = next_step(tmp_path, None)

        text = remediation(_declined(step))

        assert text is not None
        assert VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name in text
        assert f"`{step.command}`" in text

    def test_without_rag_it_names_the_listing_find_and_grep(
        self, tmp_path: Path
    ) -> None:
        text = remediation(_declined(next_step(tmp_path, None)))

        assert text is not None
        assert f"`{LIST_VAULT}`" in text
        assert "`find`" in text
        assert "grep `.vault/`" in text

    def test_one_type_narrows_the_grep_to_its_folder(self, tmp_path: Path) -> None:
        text = remediation(_declined(next_step(tmp_path, frozenset({DocType.ADR}))))

        assert text is not None
        assert "grep `.vault/adr/`" in text

    @pytest.mark.parametrize("reason", list(UnavailableReason))
    def test_every_unavailable_reason_ends_with_the_next_step(
        self, tmp_path: Path, reason: UnavailableReason
    ) -> None:
        step = next_step(tmp_path, None)

        text = remediation(_declined(step, reason))

        assert text is not None
        assert text.endswith("for the passage.")
        assert f"`{step.command}`" in text

    def test_unavailable_sentences_are_distinct(self, tmp_path: Path) -> None:
        step = next_step(tmp_path, None)
        texts = {remediation(_declined(step, r)) for r in UnavailableReason}

        assert len(texts) == len(UnavailableReason)


class TestOutcomeInvariant:
    def test_a_decline_without_a_next_step_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must name its next step"):
            SearchOutcome(status=SearchStatus.NOT_CONFIGURED, query="q")

    def test_a_ranked_outcome_with_a_next_step_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="carries no next step"):
            SearchOutcome(
                status=SearchStatus.OK, query="q", next_step=next_step(tmp_path, None)
            )


class TestVerdict:
    @staticmethod
    def _ranked(*, answered: bool, unscored: int) -> SearchOutcome:
        usage = SearchUsage(TypeSafeModel.JEV, 1, 1, 1, unscored)
        return SearchOutcome(
            status=SearchStatus.OK, query="q", answered=answered, usage=usage
        )

    def test_a_decline_has_no_verdict(self, tmp_path: Path) -> None:
        assert _declined(next_step(tmp_path, None)).verdict is None

    @pytest.mark.parametrize(
        ("answered", "unscored", "verdict"),
        [
            (True, 0, SearchVerdict.ANSWERED),
            (True, 2, SearchVerdict.ANSWERED),
            (False, 0, SearchVerdict.NOTHING_ANSWERS),
            (False, 2, SearchVerdict.NONE_READ_ANSWERS),
        ],
    )
    def test_the_verdict_is_only_as_wide_as_what_was_read(
        self, *, answered: bool, unscored: int, verdict: SearchVerdict
    ) -> None:
        assert self._ranked(answered=answered, unscored=unscored).verdict is verdict

    def test_only_the_whole_vault_verdict_claims_nothing_answers(self) -> None:
        claims = [v for v in SearchVerdict if "nothing in the vault" in v.sentence]

        assert claims == [SearchVerdict.NOTHING_ANSWERS]


class TestRecordTypes:
    @pytest.mark.parametrize("names", [None, []])
    def test_no_names_is_no_filter(self, names: list[str] | None) -> None:
        assert record_types(names) is None

    def test_names_resolve_to_record_types(self) -> None:
        assert record_types(["adr", DocType.EXEC]) == {DocType.ADR, DocType.EXEC}

    @pytest.mark.parametrize("name", ["index", "memo"])
    def test_an_unsearchable_name_is_refused_with_the_choices(self, name: str) -> None:
        with pytest.raises(UnsearchableTypeError) as refused:
            record_types(["adr", name])

        message = str(refused.value)
        assert name in message
        for searchable in SEARCHABLE_TYPES:
            assert searchable.value in message
