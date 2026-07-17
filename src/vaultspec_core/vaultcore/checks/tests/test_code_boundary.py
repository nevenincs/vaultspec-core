"""Real-filesystem tests for the opt-in ``code-boundary`` source scanner.

Builds real on-disk workspaces (a vault plus source files) with no test
doubles and asserts the scanner's contract: stem and wiki-link hits are
WARNING diagnostics, the literal vault path string alone never matches,
vault, harness, and provider directories are excluded, the feature filter
narrows the needle set, undecodable and oversized files are skipped, and
findings never raise the error count that drives the CLI exit code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .._base import Severity
from ..code_boundary import _MAX_FILE_BYTES, check_code_boundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-07-16"
STEM = f"{DATE}-my-feat-adr"


def _write_vault_doc(root: Path, doc_type: str, feature: str) -> Path:
    fm = (
        f"---\ntags:\n  - '#{doc_type}'\n  - '#{feature}'\n"
        f"date: '{DATE}'\nmodified: '{DATE}'\nrelated: []\n---\n"
    )
    path = root / ".vault" / doc_type / f"{DATE}-{feature}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{fm}\n# {feature} {doc_type}\n", encoding="utf-8")
    return path


class TestCheckCodeBoundary:
    def test_stem_hit_in_source_file_is_warning(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        src = tmp_path / "src" / "module.py"
        src.parent.mkdir(parents=True)
        src.write_text(f"# decided in {STEM}\nVALUE = 1\n", encoding="utf-8")

        result = check_code_boundary(tmp_path)

        assert result.warning_count == 1
        assert result.error_count == 0
        diag = result.diagnostics[0]
        assert diag.severity == Severity.WARNING
        assert STEM in diag.message
        assert diag.path is not None and diag.path.name == "module.py"

    def test_wiki_link_form_is_reported(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        doc = tmp_path / "docs" / "guide.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(f"See [[{STEM}]] for the decision.\n", encoding="utf-8")

        result = check_code_boundary(tmp_path)

        assert result.warning_count == 1
        assert STEM in result.diagnostics[0].message

    def test_literal_vault_path_alone_is_not_a_finding(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        src = tmp_path / "workspace.py"
        src.write_text('VAULT_DIR = root / ".vault"\n', encoding="utf-8")

        result = check_code_boundary(tmp_path)

        assert result.is_clean

    def test_vault_harness_and_provider_dirs_are_excluded(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        for dirname in (".vault", ".vaultspec", ".claude", ".gemini", ".agents"):
            f = tmp_path / dirname / "notes.md"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"[[{STEM}]]\n", encoding="utf-8")

        result = check_code_boundary(tmp_path)

        assert result.is_clean

    def test_feature_filter_narrows_needles(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        _write_vault_doc(tmp_path, "adr", "other-feat")
        src = tmp_path / "module.py"
        src.write_text(f"# {DATE}-other-feat-adr\n", encoding="utf-8")

        assert check_code_boundary(tmp_path, feature="my-feat").is_clean
        assert check_code_boundary(tmp_path, feature="other-feat").warning_count == 1

    def test_feature_filter_rejects_prefix_and_substring_collisions(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat-two")
        src = tmp_path / "module.py"
        src.write_text(f"# {DATE}-my-feat-two-adr\n", encoding="utf-8")

        # A feature that is a prefix of another must not adopt its documents,
        # and a bare letter must not match every stem containing it.
        assert check_code_boundary(tmp_path, feature="my-feat").is_clean
        assert check_code_boundary(tmp_path, feature="a").is_clean
        assert check_code_boundary(tmp_path, feature="my-feat-two").warning_count == 1

    def test_undecodable_and_oversized_files_are_skipped(self, tmp_path):
        _write_vault_doc(tmp_path, "adr", "my-feat")
        binary = tmp_path / "blob.bin"
        binary.write_bytes(b"\xff\xfe" + STEM.encode("utf-16-le"))
        big = tmp_path / "bundle.js"
        big.write_text(
            STEM + "x" * _MAX_FILE_BYTES,
            encoding="utf-8",
        )

        result = check_code_boundary(tmp_path)

        assert result.is_clean

    def test_index_stem_is_a_needle(self, tmp_path):
        index = tmp_path / ".vault" / "index" / "my-feat.index.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "---\ntags:\n  - '#index'\n  - '#my-feat'\n"
            f"date: '{DATE}'\nrelated: []\n---\n",
            encoding="utf-8",
        )
        src = tmp_path / "module.py"
        src.write_text('INDEX = "my-feat.index"\n', encoding="utf-8")

        result = check_code_boundary(tmp_path)

        assert result.warning_count == 1

    def test_no_vault_means_clean(self, tmp_path):
        (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        assert check_code_boundary(tmp_path).is_clean
