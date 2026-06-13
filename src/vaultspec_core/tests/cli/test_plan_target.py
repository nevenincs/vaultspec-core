"""Integration tests for plan-target resolution across ``vault plan`` verbs.

Every ``vault plan`` command resolves its positional argument through the
shared resolver, so a plan stem, a ``stem.md``, a feature name, a
``#feature`` tag, or a real path all reach the same plan document; an
unresolvable argument yields a clean near-match error rather than a raw
``FileNotFoundError`` traceback.

Tests drive the real Typer app through ``CliRunner`` against genuine
``.vault/`` files on disk - no mocks, patches, or stubs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


def _build_vault(root: Path) -> dict[str, str]:
    """Write one feature's plan so resolution has a real target."""
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    feature = "widget"
    stem = f"2026-03-01-{feature}-plan"
    plan_dir = root / ".vault" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"{stem}.md").write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        f"  - '#{feature}'\n"
        "date: '2026-03-01'\n"
        "modified: '2026-03-01'\n"
        "tier: L2\n"
        "related:\n"
        "  - '[[2026-02-20-widget-adr]]'\n"
        "---\n"
        "\n"
        f"# `{feature}` plan\n"
        "\n"
        "### Phase `P01` - Build\n"
        "\n"
        "Phase intent.\n"
        "\n"
        "- [x] `P01.S01` - do the work; `src/a.py`.\n"
        "- [ ] `P01.S02` - do the rest; `src/b.py`.\n",
        encoding="utf-8",
    )
    return {"feature": feature, "stem": stem, "path": str(plan_dir / f"{stem}.md")}


def _run(root: Path, *args: str):
    runner = CliRunner(env={"NO_COLOR": "1"})
    return runner.invoke(app, ["-t", str(root), "vault", "plan", *args])


def _flat(output: str) -> str:
    """Flatten a Rich error panel: drop box rules and collapse whitespace.

    Typer renders an invalid-argument message inside a bordered panel that
    line-wraps the text, so a substring like "Did you mean" can straddle a
    box edge. Stripping the vertical rules and collapsing runs of
    whitespace restores the logical one-line message for assertions.
    """
    import re

    return re.sub(r"\s+", " ", output.replace("│", " ")).strip()


class TestStatusTargetForms:
    """``vault plan status`` accepts every target form the resolver knows."""

    @pytest.mark.parametrize("form", ["stem", "stem_md", "feature", "tag"])
    def test_accepted_forms_resolve_to_the_plan(
        self, tmp_path: Path, form: str
    ) -> None:
        ids = _build_vault(tmp_path)
        argument = {
            "stem": ids["stem"],
            "stem_md": f"{ids['stem']}.md",
            "feature": ids["feature"],
            "tag": f"#{ids['feature']}",
        }[form]

        result = _run(tmp_path, "status", argument)

        assert result.exit_code == 0, result.output
        assert "Tier: L2" in result.output

    def test_absolute_path_resolves(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, "status", ids["path"])

        assert result.exit_code == 0, result.output
        assert "Tier: L2" in result.output

    def test_relative_path_resolves(self, tmp_path: Path, monkeypatch) -> None:
        ids = _build_vault(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = _run(tmp_path, "status", f".vault/plan/{ids['stem']}.md")

        assert result.exit_code == 0, result.output
        assert "Tier: L2" in result.output

    def test_unknown_target_is_clean_error_not_traceback(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path, "status", "widg")

        assert result.exit_code != 0
        flat = _flat(result.output)
        assert "Traceback" not in result.output
        assert "could not resolve plan target 'widg'" in flat
        # 'widg' is a substring of the widget plan stem and tag.
        assert "Did you mean" in flat
        assert "widget" in flat

    def test_unknown_target_without_near_matches(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path, "status", "zzz-nothing-qqq")

        assert result.exit_code != 0
        flat = _flat(result.output)
        assert "Traceback" not in result.output
        assert "could not resolve plan target 'zzz-nothing-qqq'" in flat
        assert "Did you mean" not in flat


class TestEveryCommandResolves:
    """Stem and feature handles resolve uniformly across the plan verbs."""

    def test_query_accepts_stem_and_target_option(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, "query", ids["stem"], "--open")

        assert result.exit_code == 0, result.output
        # Exactly the one open step (S02) matches.
        assert "Matched 1 of 2 Steps" in result.output
        assert "P01.S02" in result.output

    def test_check_accepts_feature_handle(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, "check", ids["feature"])

        # A clean plan has no error findings; resolution succeeded (no crash).
        assert result.exit_code == 0, result.output
        assert "Traceback" not in result.output

    def test_step_toggle_accepts_stem(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, "step", "toggle", ids["stem"], "S02", "--dry-run")

        assert result.exit_code == 0, result.output
        # The dry-run diff flips S02 from open to closed.
        assert "S02" in result.output

    def test_step_toggle_unknown_plan_is_clean_error(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path, "step", "toggle", "no-such-plan", "S01", "--dry-run")

        assert result.exit_code != 0
        assert "Traceback" not in result.output
        assert "could not resolve plan target" in _flat(result.output)
