"""ADR cross-referencing against the live TypeSafe API.

Deselected by default: select with ``-m typesafe``. The key is resolved for
this checkout as the product resolves it: ``VAULTSPEC_CORE_TYPESAFE_API_KEY``
from the environment, else from the workspace ``.env``. Selecting it without a
key fails rather than passing vacuously, because a green run must mean the
provider answered.

The vault is synthetic and small, written so each claim has one right answer:
a source decision about reaping orphaned stdio servers; the decision that owns
the watchdog variable the source depends on; a decision in the same area that
governs nothing the source uses; an unrelated decision the source declares by
mistake; and fillers. The assertions are the claims the feature makes - the
governing decision is a link, the unrelated and the merely neighbouring ones
are not, the mistaken declared link is reported weak and kept, and the run
stays inside its ceilings - not scores copied from a run.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.crossref import CrossrefStatus, VerdictKind, crossref_adr
from vaultspec_core.crossref._engine import max_evaluations
from vaultspec_core.crossref._questions import SOURCE_DEADLINE
from vaultspec_core.search._credential import CREDENTIAL_VARIABLE, resolve_credential

from .vault import write_adr

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = [pytest.mark.typesafe]

#: The checkout this suite runs from, whose ``.env`` may hold the key.
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

SOURCE = "2026-07-16-stdio-lifetime-adr"
GOVERNING = "2026-06-02-stdio-watchdog-variable-adr"
NEIGHBOUR = "2026-06-20-mcp-tool-descriptions-adr"
UNRELATED = "2026-08-01-release-notes-adr"


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def environ() -> dict[str, str]:
    credential = resolve_credential(WORKSPACE_ROOT)
    if credential is None:
        pytest.fail(
            f"the typesafe marker needs {CREDENTIAL_VARIABLE} in the environment "
            f"or in {WORKSPACE_ROOT / '.env'}"
        )
    return {CREDENTIAL_VARIABLE: credential.key}


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    write_adr(
        tmp_path,
        SOURCE,
        feature="stdio-lifetime",
        title="reap orphaned stdio servers",
        problem=(
            "A stdio MCP server can outlive the client that launched it and keep "
            "its lock on the vault."
        ),
        implementation=(
            "The server starts the client watchdog in "
            "`src/vaultspec_core/mcp_server/watchdog.py` and exits the moment the "
            "launching process disappears. Operators disable it with "
            "`VAULTSPEC_STDIO_WATCHDOG=0`, whose accepted values this decision "
            "relies on rather than redefines."
        ),
        related=(UNRELATED,),
    )
    write_adr(
        tmp_path,
        GOVERNING,
        feature="stdio-watchdog",
        title="the watchdog switch and its accepted values",
        problem="Operators need one switch to turn the stdio watchdog off.",
        implementation=(
            "`VAULTSPEC_STDIO_WATCHDOG` is read once at server start by "
            "`src/vaultspec_core/mcp_server/watchdog.py`; `0`, `false`, `off` and "
            "`no` disable the watchdog and anything else leaves it on. Every "
            "decision that turns the watchdog on or off goes through this switch."
        ),
    )
    write_adr(
        tmp_path,
        NEIGHBOUR,
        feature="mcp-tool-descriptions",
        title="keep MCP tool descriptions short",
        problem="Long tool descriptions spend the model's context on every turn.",
        implementation=(
            "Each MCP tool description stays under 600 characters and names its "
            "arguments once."
        ),
    )
    write_adr(
        tmp_path,
        UNRELATED,
        feature="release-notes",
        title="group changes into fewer releases",
        problem="Every fix shipped as its own release and the changelog grew noisy.",
        implementation="One release collects the week's changes.",
    )
    for number, subject in enumerate(
        ("colour themes", "date formats", "licence headers", "commit trailers")
    ):
        write_adr(
            tmp_path,
            f"2026-05-0{number + 1}-filler-{number}-adr",
            feature=f"filler-{number}",
            title=subject,
            problem=f"A decision about {subject}.",
        )
    return tmp_path


def test_the_governing_decision_is_linked_and_the_others_are_not(
    vault: Path, environ: dict[str, str]
) -> None:
    outcome = crossref_adr(vault, SOURCE, environ=environ)

    assert outcome.status is CrossrefStatus.OK, outcome.reason
    links = {verdict.stem for verdict in outcome.links}
    assert GOVERNING in links
    assert NEIGHBOUR not in links
    assert UNRELATED not in links
    weak = [v for v in outcome.verdicts if v.kind is VerdictKind.WEAK]
    assert [v.stem for v in weak] == [UNRELATED]
    assert weak[0].declared

    assert outcome.usage is not None
    assert outcome.usage.unscored == 0
    assert outcome.usage.requests <= max_evaluations()
    assert outcome.usage.elapsed_ms <= SOURCE_DEADLINE * 1000
