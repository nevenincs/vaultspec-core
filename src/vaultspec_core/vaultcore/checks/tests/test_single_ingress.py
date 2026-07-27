"""Enforce the single-ingress contract for the check pipeline.

The contract: on a non-mutating ``run_all_checks`` pass, every read of the
vault corpus happens during ingress (the graph build plus
``ensure_raw_texts``), and the calculate phase - every checker - runs
entirely from the shared snapshot and raw-text map. The enforcement here is
physical, not mocked: after ingress completes, every document in the corpus
is *deleted from disk*, and the calculate phase must still produce exactly
the diagnostics it produced against the intact corpus. Any checker that
silently re-ingests the corpus mid-calculate would either crash or lose its
findings, failing the equality assertion.

``check_rename_integrity`` reads ``.vaultspec/`` workspace resources (not
the vault corpus) and the archive probe in ``check_exec_mapping`` targets
``_archive/`` (excluded from the corpus scan by design); neither touches
the scanned corpus, so the lockdown does not affect them.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from ....testing.synthetic import build_synthetic_vault
from .. import (
    CheckResult,
    check_annotations,
    check_body_sections,
    check_encoding,
    check_exec_mapping,
    check_feature_rename_integrity,
    check_features,
    check_markdown,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    reset_config()
    build_synthetic_vault(
        tmp_path,
        n_docs=30,
        seed=21,
        pathologies=["cycle", "stem_collision"],
    )
    return tmp_path


def _as_comparable(result: CheckResult) -> list[tuple[str, str, str]]:
    return [(str(d.path), d.message, str(d.severity)) for d in result.diagnostics]


def _calculate_phase(
    root: Path, graph: VaultGraph
) -> dict[str, list[tuple[str, str, str]]]:
    """Run every converted checker from the shared ingress state."""
    snapshot = graph.to_snapshot()
    raw_texts = graph.raw_texts
    return {
        "annotations": _as_comparable(
            check_annotations(root, fix=False, raw_texts=raw_texts)
        ),
        "markdown": _as_comparable(
            check_markdown(root, fix=False, raw_texts=raw_texts)
        ),
        "encoding": _as_comparable(check_encoding(root, graph=graph)),
        "features": _as_comparable(check_features(root, snapshot=snapshot)),
        "exec-mapping": _as_comparable(
            check_exec_mapping(root, snapshot=snapshot, raw_texts=raw_texts)
        ),
        "body-sections": _as_comparable(check_body_sections(root, snapshot=snapshot)),
        "feature-rename-integrity": _as_comparable(
            check_feature_rename_integrity(root, snapshot=snapshot)
        ),
    }


class TestSingleIngress:
    def test_calculate_phase_survives_corpus_deletion(self, vault_root: Path) -> None:
        # Ingress: one build, one raw-text pass. Everything after this line
        # must run without the corpus.
        graph = VaultGraph(vault_root, use_cache=False)
        graph.ensure_raw_texts()
        assert graph.raw_texts, "ingress must retain the corpus text"

        baseline = _calculate_phase(vault_root, graph)

        # Physically remove the corpus. A checker that re-reads any document
        # now sees an empty vault and diverges from the baseline.
        docs_dir = vault_root / ".vault"
        assert docs_dir.exists()
        shutil.rmtree(docs_dir)
        assert not docs_dir.exists()

        after_deletion = _calculate_phase(vault_root, graph)

        assert after_deletion == baseline

    def test_undecodable_plan_reference_stays_disk_free(self, vault_root: Path) -> None:
        # A valid exec record pointing at a plan that failed to decode
        # during ingress must not trigger a disk fallback: the plan is
        # classified as unparseable from ingress state alone, and the
        # finding survives corpus deletion.
        bad_plan = vault_root / ".vault" / "plan" / "2026-01-01-badplan-plan.md"
        bad_plan.write_bytes(b"\xff\xfe\x00not a utf-8 plan")
        exec_dir = vault_root / ".vault" / "exec" / "2026-01-01-badplan"
        exec_dir.mkdir(parents=True)
        record = exec_dir / "2026-01-01-badplan-S01.md"
        record.write_text(
            "---\n"
            "tags:\n"
            "  - '#exec'\n"
            "  - '#badplan'\n"
            "date: '2026-01-01'\n"
            "step_id: 'S01'\n"
            "related:\n"
            "  - '[[2026-01-01-badplan-plan]]'\n"
            "---\n\n# badplan S01\n\nBody.\n",
            encoding="utf-8",
        )

        graph = VaultGraph(vault_root, use_cache=False)
        graph.ensure_raw_texts()
        snapshot = graph.to_snapshot()
        raw_texts = graph.raw_texts
        assert bad_plan not in raw_texts

        baseline = check_exec_mapping(
            vault_root, snapshot=snapshot, raw_texts=raw_texts
        )
        messages = [d.message for d in baseline.diagnostics]
        assert any("could not be parsed" in m and "S01" in m for m in messages)

        shutil.rmtree(vault_root / ".vault")
        after = check_exec_mapping(vault_root, snapshot=snapshot, raw_texts=raw_texts)
        assert _as_comparable(after) == _as_comparable(baseline)

    def test_encoding_diagnostics_survive_via_ingress_facts(
        self, vault_root: Path
    ) -> None:
        # A non-UTF-8 file must be reported from the ingress-recorded facts,
        # not a disk walk: plant one, ingest, delete the corpus, and the
        # finding must still be present.
        bad = vault_root / ".vault" / "research" / "2026-01-01-bad-encoding.md"
        bad.write_bytes(b"\xff\xfe\x00broken utf-16-ish bytes")

        graph = VaultGraph(vault_root, use_cache=False)
        graph.ensure_raw_texts()
        shutil.rmtree(vault_root / ".vault")

        result = check_encoding(vault_root, graph=graph)
        messages = [d.message for d in result.diagnostics]
        assert any("not valid UTF-8" in m for m in messages)
