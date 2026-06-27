"""Real-filesystem tests for the ``feature-rename-integrity`` checker.

Exercises the one drift class the checker owns - an exec folder whose feature
segment disagrees with the ``#feature`` tag of the records inside it - against
real on-disk vaults built with real bytes, with no test doubles.

The suite also locks in two deliberate non-behaviours so a future change cannot
silently reintroduce a false positive:

- An authored document whose filename narrative segment differs from its
  ``#feature`` tag is NOT flagged (narrative filenames are valid; that drift is
  structurally indistinguishable from legitimate naming without rename
  history).
- An exec record whose filename narrative segment differs from its folder is
  NOT flagged when its tag still matches the folder feature (the same narrative
  freedom applies to records); index/grammar findings owned by
  ``check_features``/``check_structure`` are NOT produced here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .._base import Severity
from ..feature_rename_integrity import check_feature_rename_integrity

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-06-27"


# ---------------------------------------------------------------------------
# Document builders (real bytes, schema-valid frontmatter).
# ---------------------------------------------------------------------------


def _authored(root: Path, doc_type: str, feature: str, *, stem_feature: str) -> Path:
    """Write an authored doc tagged ``#feature`` with a chosen filename stem.

    ``stem_feature`` controls the filename's narrative segment so a test can
    build a doc whose filename segment differs from its feature tag.
    """
    fm = (
        f"---\ntags:\n  - '#{doc_type}'\n  - '#{feature}'\n"
        f"date: '{DATE}'\nmodified: '{DATE}'\nrelated: []\n---\n"
    )
    body = f"# {feature} {doc_type}\n\nBody.\n"
    path = root / ".vault" / doc_type / f"{DATE}-{stem_feature}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{fm}\n{body}", encoding="utf-8")
    return path


def _exec_record(
    root: Path,
    folder_feature: str,
    record_stem: str,
    tag_feature: str,
    *,
    folder_date: str = DATE,
) -> Path:
    """Write an exec record into ``{folder_date}-{folder_feature}/``.

    ``record_stem`` is the record filename (without ``.md``); ``tag_feature``
    is the value of the record's ``#feature`` tag, which may differ from
    ``folder_feature`` to model drift.
    """
    fm = (
        f"---\ntags:\n  - '#exec'\n  - '#{tag_feature}'\n"
        f"date: '{folder_date}'\nmodified: '{folder_date}'\nrelated: []\n---\n"
    )
    body = "# step\n\nBody.\n"
    path = (
        root
        / ".vault"
        / "exec"
        / f"{folder_date}-{folder_feature}"
        / f"{record_stem}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{fm}\n{body}", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Clean vault
# ---------------------------------------------------------------------------


class TestCleanVault:
    def test_empty_vault_has_no_errors(self, tmp_path: Path):
        result = check_feature_rename_integrity(tmp_path)
        assert result.check_name == "feature-rename-integrity"
        assert result.supports_fix is False
        assert result.is_clean

    def test_consistent_folder_and_tags_pass(self, tmp_path: Path):
        # Folder feature matches every record's tag, even though the record
        # filenames use a narrative segment and a different date prefix.
        _exec_record(tmp_path, "alpha", f"{DATE}-alpha-P01-S01", "alpha")
        _exec_record(tmp_path, "alpha", "2026-06-28-scout-report-exec", "alpha")
        _authored(tmp_path, "adr", "alpha", stem_feature="alpha")

        result = check_feature_rename_integrity(tmp_path)
        assert result.error_count == 0
        assert result.is_clean


# ---------------------------------------------------------------------------
# Class 2: exec folder feature vs record tag
# ---------------------------------------------------------------------------


class TestExecFolderTagDrift:
    def test_record_tag_disagreeing_with_folder_is_error(self, tmp_path: Path):
        # Folder says feature 'old' but the record carries the '#new' tag.
        drifted = _exec_record(tmp_path, "old", f"{DATE}-old-P01-S01", "new")

        result = check_feature_rename_integrity(tmp_path)
        assert result.error_count == 1
        diag = result.diagnostics[0]
        assert diag.severity == Severity.ERROR
        assert diag.path is not None
        # The drifted folder is named, the example record is cited, and both
        # the observed folder feature and the conflicting tag appear.
        assert diag.path.name == f"{DATE}-old"
        assert "old" in diag.message
        assert "#new" in diag.message
        assert drifted.name in diag.message
        assert diag.fix_description is not None
        assert "vault feature rename old new" in diag.fix_description

    def test_one_error_per_folder_even_with_many_drifted_records(self, tmp_path: Path):
        _exec_record(tmp_path, "old", f"{DATE}-old-P01-S01", "new")
        _exec_record(tmp_path, "old", f"{DATE}-old-P01-S02", "new")
        _exec_record(tmp_path, "old", f"{DATE}-old-P02-S03", "new")

        result = check_feature_rename_integrity(tmp_path)
        assert result.error_count == 1, "drift is reported once per folder"

    def test_separate_drifted_folders_each_reported(self, tmp_path: Path):
        _exec_record(tmp_path, "old-a", f"{DATE}-old-a-P01-S01", "new-a")
        _exec_record(tmp_path, "old-b", f"{DATE}-old-b-P01-S01", "new-b")

        result = check_feature_rename_integrity(tmp_path)
        assert result.error_count == 2
        flagged = {d.path.name for d in result.diagnostics if d.path is not None}
        assert flagged == {f"{DATE}-old-a", f"{DATE}-old-b"}

    def test_mixed_folder_reports_only_when_a_real_tag_conflicts(self, tmp_path: Path):
        # A folder with one matching record and one drifted record is flagged
        # (the matching record does not mask the conflict).
        _exec_record(tmp_path, "old", f"{DATE}-old-P01-S01", "old")
        _exec_record(tmp_path, "old", f"{DATE}-old-P01-S02", "new")

        result = check_feature_rename_integrity(tmp_path)
        assert result.error_count == 1


# ---------------------------------------------------------------------------
# Skips: uncategorized / untagged / archive / obsidian / non-UTF-8 / symlink
# ---------------------------------------------------------------------------


class TestSkips:
    def test_uncategorized_records_do_not_trigger_drift(self, tmp_path: Path):
        # Legacy folders hold records tagged '#uncategorized' whose filenames
        # bear no relation to the folder; they must not be flagged.
        _exec_record(
            tmp_path, "test-quality", "2026-06-28-scout-alpha-exec", "uncategorized"
        )
        _exec_record(
            tmp_path, "test-quality", "2026-06-28-strict-verdict-exec", "uncategorized"
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean

    def test_archived_drift_is_skipped(self, tmp_path: Path):
        archived = (
            tmp_path
            / ".vault"
            / "_archive"
            / "exec"
            / f"{DATE}-old"
            / f"{DATE}-old-P01-S01.md"
        )
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_text(
            f"---\ntags:\n  - '#exec'\n  - '#new'\ndate: '{DATE}'\n"
            f"modified: '{DATE}'\nrelated: []\n---\n\n# step\n",
            encoding="utf-8",
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean, "drift under _archive must be skipped"

    def test_obsidian_subtree_is_skipped(self, tmp_path: Path):
        ob = (
            tmp_path
            / ".vault"
            / "exec"
            / ".obsidian"
            / f"{DATE}-old"
            / f"{DATE}-old-P01-S01.md"
        )
        ob.parent.mkdir(parents=True, exist_ok=True)
        ob.write_text(
            f"---\ntags:\n  - '#exec'\n  - '#new'\ndate: '{DATE}'\n"
            f"modified: '{DATE}'\nrelated: []\n---\n\n# step\n",
            encoding="utf-8",
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean, ".obsidian subtree must be skipped"

    def test_non_utf8_record_is_skipped(self, tmp_path: Path):
        rec = tmp_path / ".vault" / "exec" / f"{DATE}-old" / f"{DATE}-old-P01-S01.md"
        rec.parent.mkdir(parents=True, exist_ok=True)
        # A non-UTF-8 record has no parseable tag; it is surfaced by
        # check_encoding, not here.
        rec.write_bytes("# Café\n".encode("latin-1"))

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean

    def test_folder_without_date_feature_shape_is_skipped(self, tmp_path: Path):
        # A folder whose name lacks the {plan_date}-{feature} shape is a grammar
        # concern owned by check_structure, not drift here.
        bad = tmp_path / ".vault" / "exec" / "not-a-dated-folder" / "rec.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text(
            f"---\ntags:\n  - '#exec'\n  - '#new'\ndate: '{DATE}'\n"
            f"modified: '{DATE}'\nrelated: []\n---\n\n# step\n",
            encoding="utf-8",
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean


# ---------------------------------------------------------------------------
# Deferral guards: authored / record narrative naming and other-check domains
# ---------------------------------------------------------------------------


class TestDeferrals:
    def test_authored_narrative_filename_is_not_flagged(self, tmp_path: Path):
        # The canonical false positive this checker deliberately does NOT
        # produce: an authored doc whose filename narrative segment differs
        # from its feature tag is valid, not drift.
        _authored(tmp_path, "adr", "framework", stem_feature="environment-variable")
        _authored(tmp_path, "research", "framework", stem_feature="hardcoded-constants")
        _authored(
            tmp_path, "plan", "cli-architecture", stem_feature="cli-target-refactor"
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean, (
            "authored filename-segment vs tag is intentionally not checked"
        )

    def test_record_narrative_filename_with_matching_tag_is_not_flagged(
        self, tmp_path: Path
    ):
        # A record whose filename differs from its folder but whose tag matches
        # the folder feature is clean (record narrative naming is valid).
        _exec_record(
            tmp_path, "test-quality", "2026-06-28-scout-report-exec", "test-quality"
        )

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean

    def test_missing_index_is_not_flagged(self, tmp_path: Path):
        # A feature with docs but no index is check_features' domain; this
        # checker must stay silent on it.
        _authored(tmp_path, "adr", "lonely", stem_feature="lonely")
        _exec_record(tmp_path, "lonely", f"{DATE}-lonely-P01-S01", "lonely")

        result = check_feature_rename_integrity(tmp_path)
        assert result.is_clean


# ---------------------------------------------------------------------------
# Suite integration
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    def test_run_all_checks_includes_the_check(self, tmp_path: Path):
        from .. import run_all_checks

        _authored(tmp_path, "adr", "alpha", stem_feature="alpha")
        results = run_all_checks(tmp_path, fix=False)
        by_name = {r.check_name: r for r in results}
        assert "feature-rename-integrity" in by_name, (
            "run_all_checks must include the feature-rename-integrity check"
        )

    def test_run_all_checks_surfaces_the_drift(self, tmp_path: Path):
        from .. import run_all_checks

        _exec_record(tmp_path, "old", f"{DATE}-old-P01-S01", "new")
        results = run_all_checks(tmp_path, fix=False)
        by_name = {r.check_name: r for r in results}
        assert by_name["feature-rename-integrity"].error_count == 1

    def test_run_all_checks_fix_branch_includes_the_check(self, tmp_path: Path):
        from .. import run_all_checks

        _authored(tmp_path, "adr", "alpha", stem_feature="alpha")
        results = run_all_checks(tmp_path, fix=True)
        by_name = {r.check_name: r for r in results}
        assert "feature-rename-integrity" in by_name
