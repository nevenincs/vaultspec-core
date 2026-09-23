"""Hosted vault search against the live TypeSafe API.

Deselected by default: select with ``-m typesafe``. The key is resolved for
this checkout as the product resolves it: ``VAULTSPEC_CORE_TYPESAFE_API_KEY``
from the environment, else from the workspace ``.env``. Selecting it without a
key fails rather than passing vacuously, because a green run must mean the
provider answered.

The vault is synthetic and small, written so that each question has exactly
one record that owns its answer and several that only touch the subject: a
decision, the research that preceded it, the plan that carried it out, and an
unrelated record. The assertions are the claims the feature makes - the owning
record ranks first, its excerpt is the file's own text at the reported lines
and contains the answering sentence, and a question the vault cannot answer
is reported as unanswered - not scores copied from a run.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.search import SearchStatus, search_vault
from vaultspec_core.search._credential import CREDENTIAL_VARIABLE, resolve_credential
from vaultspec_core.vaultcore.models import DocType

from .test_corpus import file_lines, write_record

if TYPE_CHECKING:
    from vaultspec_core.search import SearchOutcome

pytestmark = [pytest.mark.typesafe]

#: The checkout this suite runs from, whose ``.env`` may hold the key.
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

#: The sentence the decision record owns; the question below paraphrases it.
ANSWER = (
    "An idle timeout was rejected because it kills long-lived quiet sessions "
    "or waits too long to reap an orphaned server."
)

DECISION = f"""\
# `stdio-lifetime` adr: `reap orphaned stdio servers` | (**status:** `accepted`)

## Problem Statement

A stdio MCP server can outlive the client that launched it, and the orphan
keeps its lock on the vault until someone kills it by hand.

## Considered options

- **Client watchdog (chosen).** Watch the launching process and exit the
  moment it disappears.
- **Idle timeout.** {ANSWER}
- **Heartbeat file.** Needs a writer the client does not provide.

## Consequences

Servers exit within a second of their client; no configuration is needed.
"""

RESEARCH = """\
# `stdio-lifetime` research: `orphaned stdio servers`

## Findings

Orphaned servers were observed on Windows after the client crashed. Several
mechanisms could reap them: a client watchdog, a timeout, or a heartbeat.
"""

PLAN = """\
# `stdio-lifetime` plan

## Steps

- [x] `S01` - Add the client watchdog to the stdio launcher.
- [x] `S02` - Test that the server exits when its client dies.
"""

UNRELATED = """\
# `release-notes` adr: `group changes into fewer releases` | (**status:** `accepted`)

## Problem Statement

Every fix shipped as its own release, and the changelog became unreadable.

## Considered options

- **Batch fixes per week (chosen).** One release collects the week's changes.
"""


@pytest.fixture
def environ() -> dict[str, str]:
    # Resolved for this checkout exactly as the product resolves it - the
    # process environment first, then the workspace .env - so the live run
    # also proves the key loads from where a contributor keeps it.
    credential = resolve_credential(WORKSPACE_ROOT)
    if credential is None:
        pytest.fail(
            f"the typesafe marker needs {CREDENTIAL_VARIABLE} in the environment "
            f"or in {WORKSPACE_ROOT / '.env'}"
        )
    return {CREDENTIAL_VARIABLE: credential.key}


@pytest.fixture
def vault(tmp_path: Path) -> dict[str, Path]:
    feature = "stdio-lifetime"
    return {
        "decision": write_record(
            tmp_path,
            DocType.ADR,
            "2026-07-16-stdio-lifetime-adr",
            DECISION,
            feature=feature,
        ),
        "research": write_record(
            tmp_path,
            DocType.RESEARCH,
            "2026-07-16-stdio-lifetime-research",
            RESEARCH,
            feature=feature,
        ),
        "plan": write_record(
            tmp_path,
            DocType.PLAN,
            "2026-07-17-stdio-lifetime-plan",
            PLAN,
            feature=feature,
        ),
        "unrelated": write_record(
            tmp_path,
            DocType.ADR,
            "2026-08-01-release-notes-adr",
            UNRELATED,
            feature="release-notes",
        ),
    }


def _search(root: Path, query: str, environ: dict[str, str]) -> SearchOutcome:
    outcome = search_vault(root, query, environ=environ)
    assert outcome.status is SearchStatus.OK, outcome.reason
    return outcome


def test_the_owning_record_ranks_first_with_its_verbatim_excerpt(
    tmp_path: Path, vault: dict[str, Path], environ: dict[str, str]
) -> None:
    outcome = _search(
        tmp_path,
        "why didn't we just use an idle timeout to clean up stdio servers "
        "whose client went away?",
        environ,
    )

    assert outcome.answered is True
    top = outcome.hits[0]
    assert top.name == vault["decision"].stem
    assert top.excerpt is not None
    assert "kills long-lived quiet sessions" in top.excerpt.text
    assert top.excerpt.text == file_lines(
        vault["decision"], top.excerpt.line_start, top.excerpt.line_end
    )
    assert outcome.usage is not None
    assert outcome.usage.requests > 0


@pytest.mark.usefixtures("vault")
def test_a_question_the_vault_cannot_answer_is_reported_unanswered(
    tmp_path: Path, environ: dict[str, str]
) -> None:
    outcome = _search(
        tmp_path, "how are the server's log files rotated and retained?", environ
    )

    assert outcome.answered is False


@pytest.mark.usefixtures("vault")
def test_the_key_never_appears_in_the_outcome(
    tmp_path: Path, environ: dict[str, str]
) -> None:
    outcome = _search(tmp_path, "which option was chosen to reap servers?", environ)

    assert environ[CREDENTIAL_VARIABLE] not in repr(outcome)
