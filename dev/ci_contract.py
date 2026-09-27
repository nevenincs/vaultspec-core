"""THE canonical CI/justfile coupling contract. One implementation, five repos.

WHY THIS IS A DEPLOYED COPY AND NOT A REUSABLE ACTION. Same reason as the
runner preflight: the source lives in a PRIVATE repository and every consuming
repo is PUBLIC, and a public repository cannot resolve an action or a reusable
workflow out of a private one. So the sharing model is DEPLOYMENT - one source
is rendered into each consumer's `dev/`, and a parity check fails when a
deployed copy drifts from it.

WHAT IT ASSERTS, AND WHY EACH RULE EARNS ITS PLACE.

1. A `run:` step that names a tool is a bug. The recipe is the deterministic,
   platform-agnostic entry point; a gate re-listed in YAML cannot be proven to
   match the gate it claims to run. vaultspec-dashboard measured this: a job
   naming three npm scripts by hand stood in for `just check-frontend`, which
   runs nine, so six gates never ran on a pull request at all. Only three
   shapes are permitted - `just <recipe>`, `gh ...` (release and issue
   bookkeeping, which is CI-plane and has no local meaning), and an entry
   named in `.github/ci-contract-allow.txt` with a reason.

2. Every workflow that calls `just` installs it the SAME way. Before this
   file the fleet carried two different actions, three pinned versions
   (1.46.0, 1.57.0, and "whatever is latest"), two bespoke Windows paths, and
   only two of five repos pinned by SHA - all running the same justfiles. A
   recipe that passes on one repo's `just` can fail on another's.

3. Every `just <recipe>` names a recipe that exists. This rule was added
   after a rename landed in a justfile and left one workflow step calling the
   old name: `check-knip` became `audit-knip` because the target is advisory
   and its group moved, nothing else in the repository referenced the old
   name, and the only survivor was a `run:` line that no gate could see. A
   workflow is the one caller a repo-wide rename sweep does not compile.

4. The pin is the FLOOR version, exactly. The floor is a real constraint:
   the fleet's justfiles use `[group]` attributes and `just --list` grouping,
   which is 1.38 behaviour. Pinning "latest" would let a runner silently
   drift below or above what the guards were written against.

5. Every job runs on the self-hosted fleet. GitHub-hosted runners are
   forbidden, with no carve-out: a `runs-on:` that does not name
   `self-hosted`, a matrix leg it resolves to that does not, and any GitHub
   hosted image label (`ubuntu-latest`, `ubuntu-24.04-arm`, `windows-2022`,
   `macos-15`, ...) written as a workflow value are all violations. The
   allowlist cannot excuse one. A hosted leg crept back into the fleet more
   than once through a matrix entry nobody re-read, which is why the matrix
   values are read and not only the `runs-on:` line. A runner expression
   passes only in the two literal shapes that provably stay on the fleet,
   and a job calling a reusable workflow outside the repository fails,
   because where that workflow runs cannot be read here.
   `--runner-placement-only` runs this rule alone, as the runner-policy gate.

Stdlib only, and no YAML parser: these repos hold their `dev/` dispatch core
to the standard library so it behaves identically on every platform, and a
line-oriented reader is enough to answer the questions above.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import override

#: The one `just` version the whole fleet installs. See rule 3 above.
JUST_VERSION = "1.38.0"

#: The one action, pinned by commit. taiki-e/install-action fetches the
#: upstream release for every runner OS, which is what retires the bespoke
#: Windows paths (a hand-rolled pwsh download, and an unpinned `scoop install`).
#: The commit is the one the action's `just` tag points at; a `# v2` comment
#: beside it would name a tag this commit is not on.
JUST_ACTION_SHA = "6012bba2f8e3e666a2b212f8823c06831704ce92"
JUST_INSTALL_USES = f"taiki-e/install-action@{JUST_ACTION_SHA}"
JUST_INSTALL_TOOL = f"just@{JUST_VERSION}"

#: Installations this file exists to abolish. Each was live in the fleet.
BANNED_INSTALLS = (
    ("extractions/setup-just", "a second setup action; the fleet uses one"),
    ("taiki-e/install-action@just", "floating tag - pin the commit and the version"),
    ("casey/just/releases/download", "hand-rolled download; use the pinned action"),
    ("scoop install just", "unpinned, and Windows-only; use the pinned action"),
)

#: A `run:` step may start with one of these and nothing else.
#: `just`     - the recipe, which is the whole point.
#: `gh`       - release/issue/dispatch bookkeeping. It has no local meaning:
#:              there is no `gh release upload` to run on a laptop, so there is
#:              no recipe it could be hiding.
ALLOWED_COMMANDS = ("just", "gh")

#: The one step the runner-policy gate runs. It is exempt from the shape
#: rule because it is the gate itself, and it needs nothing beyond the
#: standard library.
RUNNER_POLICY_COMMAND = (
    "uv run --isolated --no-project --python 3.13 "
    "dev/ci_contract.py --runner-placement-only"
)

ALLOWLIST_NAME = "ci-contract-allow.txt"

#: A recipe name is the first token of a line that starts at column zero. What
#: separates a recipe from an assignment is checked below, not here: a
#: parameter list may hold `=`, quotes and spaces, so the name pattern stays
#: permissive and the line shape decides.
_RECIPE = re.compile(r"^([a-zA-Z0-9_][a-zA-Z0-9_-]*)")


class Finding:
    """One violation, addressed by file and line so it can be fixed."""

    def __init__(self, path: Path, line: int, rule: str, detail: str) -> None:
        """Record one violation at `path:line` under `rule`."""
        self.path = path
        self.line = line
        self.rule = rule
        self.detail = detail

    @override
    def __str__(self) -> str:
        """Render the finding in the `path:line: [rule] detail` form."""
        return f"{self.path.as_posix()}:{self.line}: [{self.rule}] {self.detail}"


def _load_allowlist(github: Path) -> set[str]:
    """Return the `workflow.yml:line-anchor` entries still permitted.

    The allowlist is how an unconverted lane stays HONEST rather than
    invisible: every inline step that has not become a recipe yet is named
    here with the reason, so the count is a number someone can burn down
    instead of a silence.
    """
    allow = github / ALLOWLIST_NAME
    if not allow.is_file():
        return set()
    entries: set[str] = set()
    for raw in allow.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            entries.add(line)
    return entries


def _run_commands(text: str) -> list[tuple[int, str, str]]:
    """Return `(line number, step name, first command)` for every `run:` step.

    The NAME is what an allowlist entry is keyed on. A line number would be
    keyed on the one property of a step that changes every time anything above
    it is edited, so an allowlist written against line numbers goes stale on
    the first unrelated commit and starts excusing the wrong step.

    A block scalar (`run: |`) contributes its first non-comment command line;
    the shape rule is about what a step INVOKES, and a step that opens with
    `just` and then pipes into `awk` is a shell step wearing a recipe's name.
    """
    found: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    index = 0
    name = ""
    while index < len(lines):
        line = lines[index]
        named = re.match(r"^\s*-?\s*name:\s*(\S.*?)\s*$", line)
        if named:
            name = named.group(1)
        match = re.match(r"^(\s*)-?\s*run:\s*(\S.*)?$", line)
        if not match:
            index += 1
            continue
        indent, rest = match.group(1), (match.group(2) or "").strip()
        if rest and rest not in {"|", ">", "|-", ">-", "|+", ">+"}:
            found.append((index + 1, name, rest))
            index += 1
            continue
        # Block scalar: the first line of the body that is a command.
        body = index + 1
        while body < len(lines):
            candidate = lines[body]
            if candidate.strip() and not candidate.startswith(indent + " "):
                break
            stripped = candidate.strip()
            if stripped and not stripped.startswith("#"):
                found.append((body + 1, name, stripped))
                break
            body += 1
        index = body + 1
    return found


def _recipes(root: Path) -> set[str]:
    """Return every recipe name the repository's justfile defines.

    Empty when there is no justfile, which disables rule 3 rather than
    failing every step: a repo without one has nothing to check against, and a
    checker that reports a violation it cannot substantiate is noise.
    """
    for name in ("justfile", "Justfile", ".justfile"):
        path = root / name
        if not path.is_file():
            continue
        names: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _RECIPE.match(line)
            if not match:
                continue
            if line.startswith(("set ", "mod ", "import ", "export ")):
                continue
            # A recipe line is `name [parameters]: [dependencies]`. Neither
            # half can be excluded by shape: a parameter list holds `=`, quotes
            # and spaces (`test-unit durations="":`), and a dependency list
            # puts a name AFTER the colon (`test-runner-image:
            # build-runner-image`), so requiring the line to END in `:` misses
            # every recipe that depends on another. What actually separates a
            # recipe from an assignment is `:=`, and that is the only test.
            head = line.split("#", 1)[0].rstrip()
            if ":=" in head or ":" not in head:
                continue
            names.add(match.group(1))
        return names
    return set()


def _first_word(command: str) -> str:
    """Return the executable a command line invokes, ignoring env prefixes.

    `VAR=x just test-unit` is not a `just` step on Windows - the POSIX env
    prefix is a parse error under both `cmd.exe` and PowerShell - so the
    prefix is reported rather than skipped past.
    """
    return command.split(maxsplit=1)[0] if command.split() else ""


#: A workflow step may provision `just` through a composite action stored in
#: this repository rather than inline. The pin then lives in that action's
#: `action.yml`, not in the workflow, and a per-file text search cannot see it.
#: Reading the local actions a workflow `uses:` is what makes the install rule
#: measure provisioning rather than proximity: a repository that pins the tool
#: once in a shared action satisfies the rule more strongly than one repeating
#: the pin in every workflow, and must not be reported for doing so.
_LOCAL_ACTION_USES = re.compile(r"uses:\s*\./(\.github/actions/[^\s#]+)")


def _local_action_texts(text: str, root: Path) -> list[str]:
    """Return the text of every local composite action ``text`` uses."""
    texts: list[str] = []
    for relative in dict.fromkeys(_LOCAL_ACTION_USES.findall(text)):
        directory = root / relative
        for name in ("action.yml", "action.yaml"):
            candidate = directory / name
            if candidate.is_file():
                texts.append(candidate.read_text(encoding="utf-8"))
                break
    return texts


HOSTED_FORBIDDEN = (
    "GitHub-hosted runners are forbidden; run the job on [self-hosted, ...]"
)
PLACEMENT = "runner-placement"

#: GitHub's hosted image vocabulary: an OS family plus a version or channel,
#: optionally a size or architecture suffix. Fleet capability labels such as
#: `windows-x64` or `macos-arm64` carry no version and do not match.
_HOSTED_LABEL = re.compile(
    r"^(ubuntu|windows|macos)-(latest|slim|\d+(\.\d+)?)(-[a-z0-9]+)*$", re.IGNORECASE
)
_RUNS_ON = re.compile(r"^(\s*)runs-on:\s*(.*?)\s*$")
_VALUE = re.compile(r"^\s*(?:-\s+)?(?:[\w-]+:\s*)?(.*?)\s*$")


def _indent(line: str) -> int:
    """Return the column the line's content starts at."""
    return len(line) - len(line.lstrip())


def _meaningful(line: str) -> bool:
    """Whether a line carries YAML content rather than a blank or a comment."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _strip_comment(value: str) -> str:
    """Drop a trailing ` # comment` from a YAML value."""
    return value.split(" #", 1)[0].strip()


def _labels(value: str) -> list[str]:
    """Return the labels a scalar or flow-sequence value names."""
    value = _strip_comment(value)
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [part.strip().strip("'\"") for part in value.split(",") if part.strip()]


def _block(lines: list[str], index: int) -> list[int]:
    """Return the indices of the lines nested under the line at `index`."""
    owner = _indent(lines[index])
    nested: list[int] = []
    for number in range(index + 1, len(lines)):
        if not _meaningful(lines[number]):
            continue
        if _indent(lines[number]) <= owner:
            break
        nested.append(number)
    return nested


def _job_header(lines: list[str], index: int) -> int:
    """Return the index of the job key that owns the line at `index`."""
    own = _indent(lines[index])
    for number in range(index - 1, -1, -1):
        if _meaningful(lines[number]) and _indent(lines[number]) < own:
            return number
    return 0


def _matrix_values(
    lines: list[str], index: int, keys: set[str]
) -> list[tuple[int, str]]:
    """Return `(line index, value)` for every matrix entry of `keys` in this job.

    Only the job's `strategy:` block is read, so a step input that happens to
    share a matrix key's name is never mistaken for a leg.
    """
    own = _indent(lines[index])
    job = _block(lines, _job_header(lines, index))
    strategy = next(
        (
            n
            for n in job
            if _indent(lines[n]) == own and lines[n].strip() == "strategy:"
        ),
        None,
    )
    if strategy is None:
        return []
    found: list[tuple[int, str]] = []
    body = _block(lines, strategy)
    for number in body:
        match = re.match(r"^\s*(?:-\s+)?([\w-]+):\s*(.*?)\s*$", lines[number])
        if not match or match.group(1) not in keys:
            continue
        value = _strip_comment(match.group(2))
        if value:
            found.append((number, value))
            continue
        for item in _block(lines, number):
            listed = re.match(r"^\s*-\s+(.*?)\s*$", lines[item])
            if listed:
                found.append((item, _strip_comment(listed.group(1))))
    return found


_GUARDED_MATRIX = re.compile(
    r"\$\{\{ startsWith\(toJSON\((matrix\.[\w-]+)\), '\['\)"
    r" && contains\(\1, 'self-hosted'\)"
    r" && \1 \|\| fromJSON\('\[\"self-hosted\",\"unmapped-fleet-runner\"\]'\) \}\}"
)
_CLOSED_MAPPING = re.compile(
    r"\$\{\{ fromJSON\((?:matrix\.[\w-]+ == '[^']+' && '\[[^']+\]' \|\| )+"
    r"format\('\[[^']+\]', matrix\.[\w-]+\)\) \}\}"
)
_MATRIX_ONLY = re.compile(r"\$\{\{\s*matrix\.([A-Za-z_][\w-]*)\s*\}\}")


def _names_self_hosted(labels: list[str]) -> bool:
    """Whether `self-hosted` is one of the labels, exactly."""
    return "self-hosted" in {label.lower() for label in labels}


def _closed_mapping(value: str) -> bool:
    """A literal token-to-labels mapping whose every branch is self-hosted.

    Generated release workflows route a runner token through such a mapping.
    It passes only when its shape is exactly a chain of literal arrays ending
    in a literal fallback, and every one of those arrays names `self-hosted`.
    """
    if not _CLOSED_MAPPING.fullmatch(value):
        return False
    arrays = re.findall(r"'(\[[^']+\])'", value)
    try:
        return bool(arrays) and all(
            _names_self_hosted([str(label) for label in json.loads(array)])
            for array in arrays
        )
    except (ValueError, TypeError):
        return False


def _nested_labels(lines: list[str], index: int) -> list[str]:
    """Return every label a block-style `runs-on:` lists beneath it."""
    labels: list[str] = []
    for number in _block(lines, index):
        keyed = _VALUE.match(lines[number])
        labels.extend(_labels(keyed.group(1) if keyed else ""))
    return labels


def _external_reusable_jobs(lines: list[str]) -> list[tuple[int, str]]:
    """Return `(line index, target)` for every job that calls a workflow elsewhere.

    A job-level `uses:` names a reusable workflow; one outside this repository
    chooses its own runners, so its placement cannot be read here.
    """
    top = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if top is None:
        return []
    found: list[tuple[int, str]] = []
    body = _block(lines, top)
    if not body:
        return []
    job_indent = _indent(lines[body[0]])
    for header in (n for n in body if _indent(lines[n]) == job_indent):
        fields = _block(lines, header)
        if not fields:
            continue
        field_indent = _indent(lines[fields[0]])
        for number in fields:
            line = lines[number]
            if _indent(line) != field_indent or not line.strip().startswith("uses:"):
                continue
            target = _strip_comment(line.strip()[len("uses:") :]).strip("'\"")
            if not target.startswith("./.github/workflows/"):
                found.append((number, target))
    return found


def runner_placement(path: Path, text: str) -> list[Finding]:
    """Return every job placement in `text` not proven to run self-hosted."""
    lines = text.splitlines()
    findings: list[Finding] = []

    def refuse(index: int, detail: str) -> None:
        findings.append(
            Finding(path, index + 1, PLACEMENT, f"{detail}. {HOSTED_FORBIDDEN}")
        )

    for index, line in enumerate(lines):
        if not _meaningful(line):
            continue
        keyed = _VALUE.match(line)
        for label in _labels(keyed.group(1) if keyed else ""):
            if _HOSTED_LABEL.match(label):
                refuse(index, f"`{label}` is a GitHub-hosted image label")

    for index, target in _external_reusable_jobs(lines):
        refuse(
            index,
            f"`{target}` is an external reusable workflow; "
            "its placement is unobservable",
        )

    for index, line in enumerate(lines):
        match = _RUNS_ON.match(line)
        if not match or not _meaningful(line):
            continue
        value = _strip_comment(match.group(2))
        if not value:
            if not _names_self_hosted(_nested_labels(lines, index)):
                refuse(index, "runs-on names no self-hosted label")
            continue
        if value.startswith("{"):
            listed = re.search(r"labels:\s*(\[[^\]]*\]|[^,}]+)", value)
            if not listed or not _names_self_hosted(_labels(listed.group(1))):
                refuse(index, "runs-on names no self-hosted label")
            continue
        if value.startswith("[") or "${{" not in value:
            if not _names_self_hosted(_labels(value)):
                refuse(index, f"runs-on `{value[:60]}` names no self-hosted label")
            continue
        if _GUARDED_MATRIX.fullmatch(value) or _closed_mapping(value):
            continue
        only = _MATRIX_ONLY.fullmatch(value)
        legs = _matrix_values(lines, index, {only.group(1)}) if only else []
        if not legs:
            refuse(
                index,
                f"runs-on `{value[:60]}` is an unresolved expression; "
                "it cannot be proven self-hosted",
            )
            continue
        for number, leg in legs:
            if not _names_self_hosted(_labels(leg)):
                refuse(number, f"matrix leg `{leg[:60]}` names no self-hosted label")
    return findings


def audit(root: Path) -> list[Finding]:
    """Return every contract violation under `root/.github/workflows`."""
    github = root / ".github"
    workflows = sorted((github / "workflows").glob("*.yml")) + sorted(
        (github / "workflows").glob("*.yaml")
    )
    allowlist = _load_allowlist(github)
    recipes = _recipes(root)
    findings: list[Finding] = []

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        name = path.name
        findings.extend(runner_placement(path, text))

        for needle, why in BANNED_INSTALLS:
            for number, line in enumerate(text.splitlines(), start=1):
                if needle in line and not line.lstrip().startswith("#"):
                    findings.append(
                        Finding(path, number, "install", f"{needle}: {why}")
                    )

        calls_just = any(
            _first_word(command) == "just" for _, _, command in _run_commands(text)
        )
        if calls_just:
            provisioning = "\n".join([text, *_local_action_texts(text, root)])
            if JUST_INSTALL_USES not in provisioning:
                findings.append(
                    Finding(
                        path,
                        1,
                        "install",
                        f"calls `just`, but installs it without {JUST_INSTALL_USES}",
                    )
                )
            elif JUST_INSTALL_TOOL not in provisioning:
                findings.append(
                    Finding(
                        path,
                        1,
                        "install",
                        f"installs `just` off the floor pin {JUST_INSTALL_TOOL}",
                    )
                )

        for number, step, command in _run_commands(text):
            if command.strip() == RUNNER_POLICY_COMMAND:
                continue
            key = f"{name}:{step}"
            if key in allowlist or name in allowlist:
                continue
            word = _first_word(command)
            if word == "just":
                called = command.split()[1] if len(command.split()) > 1 else ""
                if recipes and called and called not in recipes:
                    findings.append(
                        Finding(
                            path,
                            number,
                            "recipe",
                            f"`just {called}` names no recipe in the justfile",
                        )
                    )
                continue
            if word in ALLOWED_COMMANDS:
                continue
            findings.append(
                Finding(
                    path,
                    number,
                    "shape",
                    f"`{command[:60]}` names a tool; call a recipe, "
                    f"or name `{key}` in .github/{ALLOWLIST_NAME}",
                )
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    """Report every violation and return 1 when any is found, else 0."""
    # A step NAME may hold any character a human typed - the fleet has an
    # arrow in one - and the default Windows console encoding is cp1252. A
    # checker that raises UnicodeEncodeError while reporting a finding has
    # turned a fixable finding into a crash, so the stream is widened first.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    args = list(sys.argv[1:] if argv is None else argv)
    placement_only = "--runner-placement-only" in args
    args = [arg for arg in args if arg != "--runner-placement-only"]
    root = Path(args[0]) if args else Path.cwd()
    if placement_only:
        workflows = root / ".github" / "workflows"
        paths = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
        if not paths:
            print("FAIL: no workflows found", file=sys.stderr)
            return 1
        findings = [
            finding
            for path in paths
            for finding in runner_placement(path, path.read_text(encoding="utf-8"))
        ]
    else:
        findings = audit(root)
    for finding in findings:
        print(str(finding))
    if findings:
        print(
            f"\n{len(findings)} CI-contract violation(s). Every job runs on the "
            "self-hosted fleet, and a `run:` step may only call a just recipe, run "
            f"`gh` bookkeeping, or be named in .github/{ALLOWLIST_NAME} with the "
            "reason it is not a recipe yet.",
            file=sys.stderr,
        )
        return 1
    print(
        "PASS: every workflow runs self-hosted."
        if placement_only
        else "PASS: every workflow runs self-hosted, calls recipes "
        "and installs one pinned `just`."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
