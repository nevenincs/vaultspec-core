"""Only trusted pull requests reach the self-hosted fleet.

Every job in this repository runs on a self-hosted runner, so a job a pull
request can start runs the pull request's code on a machine that also serves
releases. Such a job may run only when the pull request's branch lives in this
repository AND its author is the owner, a collaborator, or the fleet release
App. A `ci:full` label is not a way around that: it additionally needs a user,
not a bot, to have applied it.

The trust clause is byte-identical across the fleet's repositories, so it is
pinned here as text. Text alone cannot show that the clause guards the job -
`untrusted || CLAUSE` contains it too - so every condition is also evaluated,
with a small evaluator for the expression subset the workflows use, against
the pull requests that must never reach the fleet.

The verdict job is withheld like every other job, and a skipped required check
counts as passed. So a withheld verdict must report under a name other than the
required check's, which leaves the required check expected and the pull request
unmergeable.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

pytestmark = [pytest.mark.repo]

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
REPOSITORY = "nevenincs/vaultspec-core"

#: The check the `main` ruleset requires.
REQUIRED_CHECK = "Check: Merge gate (Linux)"

SAME_REPOSITORY = "github.event.pull_request.head.repo.full_name == github.repository"

#: Byte-identical across the fleet; never reformat or reorder it.
TRUSTED_AUTHOR = (
    "(github.event.pull_request.author_association == 'OWNER' || "
    "github.event.pull_request.author_association == 'COLLABORATOR' || "
    "github.event.pull_request.user.login == 'nevenincs-release[bot]')"
)

LABEL_BY_USER = "github.event.sender.type == 'User'"

PULL_REQUEST_EVENTS = frozenset({"pull_request", "pull_request_target"})


# ---------------------------------------------------------------------------
# Workflow loading


def _load(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _events(document: Mapping[Any, Any]) -> dict[str, Any]:
    """Read triggers under PyYAML, which parses the key ``on`` as ``True``."""
    raw = document.get("on", document.get(True))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return dict.fromkeys(cast("list[str]", raw))
    return cast("dict[str, Any]", raw or {})


def _workflow_paths() -> list[Path]:
    paths = sorted(WORKFLOWS.glob("*.yml"))
    assert paths, f"no workflow files found under {WORKFLOWS}"
    return paths


def _pull_request_reachable() -> dict[str, dict[str, Any]]:
    """Every workflow a pull request event can run, called workflows included."""
    documents = {path.name: _load(path) for path in _workflow_paths()}
    pending = [
        name
        for name, document in documents.items()
        if PULL_REQUEST_EVENTS & set(_events(document))
    ]
    assert pending, "no workflow runs on pull requests; the corpus resolved wrong"
    reachable: dict[str, dict[str, Any]] = {}
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable[name] = documents[name]
        jobs = cast("dict[str, dict[str, Any]]", documents[name].get("jobs") or {})
        for job in jobs.values():
            uses = str(job.get("uses", ""))
            if uses.startswith("./.github/workflows/"):
                pending.append(uses.rsplit("/", 1)[-1])
    return reachable


def _fleet_jobs() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Every pull-request-reachable job that takes a runner.

    The repository forbids GitHub-hosted runners, so every job with a
    `runs-on` is a fleet job.
    """
    for name, document in sorted(_pull_request_reachable().items()):
        jobs = cast("dict[str, dict[str, Any]]", document.get("jobs") or {})
        for job_id, job in jobs.items():
            if "runs-on" in job:
                yield name, job_id, job


# ---------------------------------------------------------------------------
# Expression evaluation: the subset of the GitHub Actions expression language
# the workflows use. Anything outside it raises rather than guessing.

_TOKEN = re.compile(
    r"\s*(?:(?P<string>'(?:[^']|'')*')|(?P<number>\d+)"
    r"|(?P<op>==|!=|&&|\|\||[!(),])|(?P<name>[A-Za-z_][A-Za-z0-9_\-]*"
    r"(?:\.[A-Za-z_][A-Za-z0-9_\-]*)*))"
)
_EMBEDDED = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)

Function = Callable[..., object]


def _tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    position = 0
    text = text.rstrip()
    while position < len(text):
        match = _TOKEN.match(text, position)
        assert match is not None and match.end() > position, (
            f"unsupported expression syntax at {text[position:]!r}"
        )
        kind = cast("str", match.lastgroup)
        tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


def _truthy(value: object) -> bool:
    return value not in (None, False, 0, "")


def _equal(left: object, right: object) -> bool:
    """GitHub compares strings case-insensitively."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return left == right


class _Evaluator:
    def __init__(
        self,
        text: str,
        context: Mapping[str, object],
        functions: Mapping[str, Function],
    ) -> None:
        self._tokens = _tokens(text)
        self._position = 0
        self._context = context
        self._functions = functions

    def run(self) -> object:
        value = self._or()
        assert self._position == len(self._tokens), (
            f"unparsed tail: {self._tokens[self._position :]}"
        )
        return value

    def _peek(self) -> str | None:
        if self._position < len(self._tokens):
            return self._tokens[self._position][1]
        return None

    def _take(self) -> tuple[str, str]:
        token = self._tokens[self._position]
        self._position += 1
        return token

    def _or(self) -> object:
        value = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            value = value if _truthy(value) else right
        return value

    def _and(self) -> object:
        value = self._comparison()
        while self._peek() == "&&":
            self._take()
            right = self._comparison()
            value = right if _truthy(value) else value
        return value

    def _comparison(self) -> object:
        value = self._unary()
        while self._peek() in ("==", "!="):
            operator = self._take()[1]
            right = self._unary()
            same = _equal(value, right)
            value = same if operator == "==" else not same
        return value

    def _unary(self) -> object:
        if self._peek() == "!":
            self._take()
            return not _truthy(self._unary())
        return self._primary()

    def _primary(self) -> object:
        kind, text = self._take()
        if text == "(" and kind == "op":
            value = self._or()
            assert self._take()[1] == ")", "unbalanced parenthesis"
            return value
        if kind == "string":
            return text[1:-1].replace("''", "'")
        if kind == "number":
            return int(text)
        assert kind == "name", f"unexpected token {text!r}"
        if self._peek() == "(":
            return self._call(text)
        literals: dict[str, object] = {"true": True, "false": False, "null": None}
        if text in literals:
            return literals[text]
        scope: Mapping[str, object] | None = self._context
        value: object = None
        for part in text.split("."):
            if scope is None:
                return None
            value = scope.get(part)
            mapping = isinstance(value, Mapping)
            scope = cast("Mapping[str, object]", value) if mapping else None
        return value

    def _call(self, name: str) -> object:
        self._take()
        arguments: list[object] = []
        while self._peek() != ")":
            arguments.append(self._or())
            if self._peek() == ",":
                self._take()
        self._take()
        assert name in self._functions, f"unsupported function {name}()"
        return self._functions[name](*arguments)


def _evaluate(expression: str, context: Mapping[str, object]) -> object:
    """Evaluate one condition, with or without its `${{ }}` wrapper."""
    text = expression.strip()
    whole = _EMBEDDED.fullmatch(text)
    functions: dict[str, Function] = {
        "cancelled": lambda: False,
        "always": lambda: True,
        "success": lambda: True,
        "failure": lambda: False,
    }
    return _Evaluator(whole.group(1) if whole else text, context, functions).run()


def _render(name: str, context: Mapping[str, object]) -> str:
    """The check name a job reports under, its expressions evaluated."""
    return _EMBEDDED.sub(lambda match: str(_evaluate(match.group(1), context)), name)


def _runs(job: dict[str, Any], context: Mapping[str, object]) -> bool:
    return _truthy(_evaluate(str(job.get("if", "success()")), context))


# ---------------------------------------------------------------------------
# Pull requests


def _pull_request(
    *,
    head: str = REPOSITORY,
    association: str = "OWNER",
    login: str = "nevenincs",
    action: str = "synchronize",
    draft: bool = False,
    label: str | None = None,
    sender: str = "User",
) -> dict[str, object]:
    event: dict[str, object] = {
        "action": action,
        "pull_request": {
            "head": {"repo": {"full_name": head}},
            "author_association": association,
            "user": {"login": login},
            "draft": draft,
            "number": 7,
        },
        "sender": {"type": sender},
    }
    if label is not None:
        event["label"] = {"name": label}
    return {
        "github": {
            "event_name": "pull_request",
            "repository": REPOSITORY,
            "event": event,
        }
    }


#: Pull requests that must never reach the fleet, whatever they do.
UNTRUSTED: dict[str, dict[str, object]] = {
    "contributor": {"association": "CONTRIBUTOR", "login": "outsider"},
    "first-timer": {"association": "FIRST_TIME_CONTRIBUTOR", "login": "outsider"},
    "no-association": {"association": "NONE", "login": "outsider"},
    "member": {"association": "MEMBER", "login": "outsider"},
    "dependabot": {"association": "NONE", "login": "dependabot[bot]"},
    "workflow-token-bot": {"association": "NONE", "login": "github-actions[bot]"},
    "owner-from-a-fork": {"head": "outsider/vaultspec-core"},
    "release-login-from-a-fork": {
        "head": "outsider/vaultspec-core",
        "association": "NONE",
        "login": "nevenincs-release[bot]",
    },
}

#: Every way a pull request event can arrive.
ARRIVALS: dict[str, dict[str, object]] = {
    "opened-ready": {"action": "opened"},
    "pushed-ready": {"action": "synchronize"},
    "pushed-draft": {"action": "synchronize", "draft": True},
    "marked-ready": {"action": "ready_for_review"},
    "ci-full-by-user": {"action": "labeled", "label": "ci:full", "draft": True},
    "ci-full-by-bot": {
        "action": "labeled",
        "label": "ci:full",
        "draft": True,
        "sender": "Bot",
    },
}


def _context(author: Mapping[str, object], arrival: Mapping[str, object]) -> Any:
    return _pull_request(**cast("dict[str, Any]", {**author, **arrival}))


# ---------------------------------------------------------------------------
# Contracts


def test_no_workflow_uses_pull_request_target() -> None:
    """`pull_request_target` runs with the base repository's secrets.

    Mutation proof: adding `pull_request_target:` to merge-gate.yml's triggers
    makes this fail naming it; removing it makes this pass.
    """
    offenders = [
        path.name
        for path in _workflow_paths()
        if "pull_request_target" in _events(_load(path))
    ]
    assert not offenders, f"these workflows use pull_request_target: {offenders}"


def test_every_fleet_job_a_pull_request_reaches_carries_the_trust_clause() -> None:
    """The same-repository and trusted-author clauses, byte for byte.

    Mutation proof: deleting `|| github.event.pull_request.user.login ==
    'nevenincs-release[bot]'` from `test-linux`'s condition makes this fail on
    `merge-gate.yml:test-linux`; restoring it makes this pass.
    """
    jobs = list(_fleet_jobs())
    assert jobs, "no pull-request-reachable fleet job was found"
    offenders = [
        f"{name}:{job_id}"
        for name, job_id, job in jobs
        if SAME_REPOSITORY not in str(job.get("if", ""))
        or TRUSTED_AUTHOR not in str(job.get("if", ""))
    ]
    assert not offenders, (
        "these jobs run pull request code on the self-hosted fleet without the "
        f"exact same-repository and trusted-author clauses: {offenders}"
    )
    labelled = [
        f"{name}:{job_id}"
        for name, job_id, job in jobs
        if "github.event.label.name" in str(job.get("if", ""))
        and LABEL_BY_USER not in str(job.get("if", ""))
    ]
    assert not labelled, f"these label paths accept a bot's label: {labelled}"


@pytest.mark.parametrize("arrival", sorted(ARRIVALS))
@pytest.mark.parametrize("author", sorted(UNTRUSTED))
def test_an_untrusted_pull_request_reaches_no_fleet_job(
    author: str, arrival: str
) -> None:
    """Forks, outside authors and bots run nothing, however they arrive.

    Mutation proof: replacing the verdict job's condition with
    `${{ !cancelled() }}` makes this fail on `merge-gate.yml:gate` for every
    untrusted author; restoring it makes this pass.
    """
    context = _context(UNTRUSTED[author], ARRIVALS[arrival])
    started = [
        f"{name}:{job_id}" for name, job_id, job in _fleet_jobs() if _runs(job, context)
    ]
    assert not started, f"{author} ({arrival}) starts fleet jobs: {started}"


@pytest.mark.parametrize("arrival", sorted(ARRIVALS))
@pytest.mark.parametrize("author", sorted(UNTRUSTED))
def test_a_withheld_verdict_never_reports_as_the_required_check(
    author: str, arrival: str
) -> None:
    """A skipped required check passes, so the withheld verdict is renamed.

    Mutation proof: replacing the verdict job's name expression with the plain
    string `Check: Merge gate (Linux)` makes this fail; restoring it makes this
    pass.
    """
    context = _context(UNTRUSTED[author], ARRIVALS[arrival])
    reported = [
        f"{name}:{job_id}"
        for name, job_id, job in _fleet_jobs()
        if _render(str(job.get("name", job_id)), context) == REQUIRED_CHECK
    ]
    assert not reported, (
        f"{author} ({arrival}) gets a skipped `{REQUIRED_CHECK}`, which GitHub "
        f"counts as passed: {reported}"
    )


@pytest.mark.parametrize(
    "author",
    [
        {"association": "OWNER", "login": "nevenincs"},
        {"association": "COLLABORATOR", "login": "collaborator"},
        {"association": "NONE", "login": "nevenincs-release[bot]"},
        {"association": "CONTRIBUTOR", "login": "nevenincs-release[bot]"},
    ],
    ids=["owner", "collaborator", "release-app", "release-app-contributor"],
)
def test_a_trusted_ready_pull_request_runs_the_full_gate(
    author: dict[str, object],
) -> None:
    """The release App's pull request is proven like the owner's.

    It is how the release pull request's required check reports at all, so a
    trust clause that dropped it would strand every release.
    """
    context = _context(author, ARRIVALS["pushed-ready"])
    gate = _load(WORKFLOWS / "merge-gate.yml")
    jobs = cast("dict[str, dict[str, Any]]", gate["jobs"])
    assert all(_runs(job, context) for job in jobs.values()), {
        job_id: _runs(job, context) for job_id, job in jobs.items()
    }
    reported = [
        job_id
        for job_id, job in jobs.items()
        if _render(str(job.get("name", job_id)), context) == REQUIRED_CHECK
    ]
    assert reported == ["gate"], reported


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_a_call_runs_the_full_gate_under_the_required_name(event: str) -> None:
    """The release cut and main's health check call the gate; it all runs."""
    context = {"github": {"event_name": event, "repository": REPOSITORY}}
    jobs = cast(
        "dict[str, dict[str, Any]]", _load(WORKFLOWS / "merge-gate.yml")["jobs"]
    )
    assert all(_runs(job, context) for job in jobs.values())
    assert _render(str(jobs["gate"]["name"]), context) == REQUIRED_CHECK


def test_a_bots_ci_full_label_counts_for_nothing() -> None:
    """A bot's `ci:full` starts exactly what an unrelated label starts.

    Mutation proof: deleting `&& github.event.sender.type == 'User'` from
    `test-linux`'s condition makes this fail on that job; restoring it makes
    this pass.
    """
    by_bot = _context({}, ARRIVALS["ci-full-by-bot"])
    unrelated = _context(
        {}, {"action": "labeled", "label": "documentation", "draft": True}
    )
    differs = [
        f"{name}:{job_id}"
        for name, job_id, job in _fleet_jobs()
        if _runs(job, by_bot) != _runs(job, unrelated)
    ]
    assert not differs, f"a bot's ci:full label changes what runs: {differs}"
    by_user = _context({}, ARRIVALS["ci-full-by-user"])
    jobs = cast(
        "dict[str, dict[str, Any]]", _load(WORKFLOWS / "merge-gate.yml")["jobs"]
    )
    assert _runs(jobs["test-linux"], by_user), (
        "a user's ci:full label no longer proves a trusted draft"
    )
