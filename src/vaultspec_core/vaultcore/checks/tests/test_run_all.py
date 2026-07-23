"""Integration tests for the ``run_all_checks`` suite registration.

Confirms the two validators added for the vault-check-validators feature -
``exec-mapping`` and ``body-sections`` - are registered in the aggregate check
in both the read-only and ``--fix`` branches, and that both remain read-only
(``fixed_count`` zero) because neither defect has a safe automatic repair. No
mocks, patches, or skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from .. import run_all_checks

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_NEW_CHECKERS = {"exec-mapping", "body-sections"}


@pytest.fixture(autouse=True)
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _skeleton(root: Path) -> None:
    for sub in ("adr", "plan", "exec"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)


def _seed_exec_and_plan(root: Path) -> None:
    plan = root / ".vault" / "plan" / "2026-02-04-feat-plan.md"
    plan.write_text(
        "---\ntags:\n  - '#plan'\n  - '#feat'\n"
        "date: '2026-02-04'\nmodified: '2026-02-04'\ntier: L1\nrelated: []\n---\n\n"
        "# `feat` plan\n\n## Description\n\np\n\n## Steps\n\n"
        "- [ ] `S01` - do; `src/a.py`.\n\n## Parallelization\n\np\n\n"
        "## Verification\n\np\n",
        encoding="utf-8",
    )
    exec_doc = root / ".vault" / "exec" / "2026-02-04-feat" / "2026-02-04-feat-S01.md"
    exec_doc.parent.mkdir(parents=True, exist_ok=True)
    exec_doc.write_text(
        "---\ntags:\n  - '#exec'\n  - '#feat'\n"
        "date: '2026-02-04'\nmodified: '2026-02-04'\nstep_id: 'S01'\n"
        "related:\n  - '[[2026-02-04-feat-plan]]'\n---\n\n"
        "# Step record\n\n## Description\n\nDone.\n## Outcome\n\nok\n## Notes\n\nn\n",
        encoding="utf-8",
    )


class TestRunAllRegistration:
    def test_new_checkers_registered_in_readonly_branch(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _seed_exec_and_plan(tmp_path)

        results = run_all_checks(tmp_path, fix=False)
        names = {r.check_name for r in results}

        assert names >= _NEW_CHECKERS

    def test_new_checkers_registered_in_fix_branch(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _seed_exec_and_plan(tmp_path)

        results = run_all_checks(tmp_path, fix=True)
        by_name = {r.check_name: r for r in results}

        assert set(by_name) >= _NEW_CHECKERS
        for name in _NEW_CHECKERS:
            # Read-only: the fix branch must never rewrite for these checkers.
            assert by_name[name].supports_fix is False
            assert by_name[name].fixed_count == 0

    def test_new_checkers_appear_exactly_once(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _seed_exec_and_plan(tmp_path)

        results = run_all_checks(tmp_path, fix=False)
        for name in _NEW_CHECKERS:
            count = sum(1 for r in results if r.check_name == name)
            assert count == 1, f"{name} registered {count} times, expected 1"
