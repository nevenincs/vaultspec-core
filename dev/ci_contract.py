"""THE canonical CI/justfile coupling contract. One implementation, five repos.

WHY THIS IS A DEPLOYED COPY AND NOT A REUSABLE ACTION. Same reason as
`preflight.sh` beside it: ci-fleet is PRIVATE and every consuming repo is
PUBLIC, and a public repository cannot resolve an action or a reusable
workflow out of a private one. So the sharing model is DEPLOYMENT - this file
is the source, `fleetctl ci contract` renders it into a consumer's `dev/`, and
`tests/test_ci_contract_parity.py` fails when a deployed copy drifts.

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

3. The pin is the FLOOR version, exactly. The floor is a real constraint:
   the fleet's justfiles use `[group]` attributes and `just --list` grouping,
   which is 1.38 behaviour. Pinning "latest" would let a runner silently
   drift below or above what the guards were written against.

Stdlib only, and no YAML parser: these repos hold their `dev/` dispatch core
to the standard library so it behaves identically on every platform, and a
line-oriented reader is enough to answer the three questions above.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: The one `just` version the whole fleet installs. See rule 3 above.
JUST_VERSION = "1.38.0"

#: The one action, pinned by commit. taiki-e/install-action fetches the
#: upstream release for every runner OS, which is what retires the bespoke
#: Windows paths (a hand-rolled pwsh download, and an unpinned `scoop install`).
JUST_ACTION_SHA = "d56249f532886d210664917b882ad7e152e17d68"
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

ALLOWLIST_NAME = "ci-contract-allow.txt"


class Finding:
    """One violation, addressed by file and line so it can be fixed."""

    def __init__(self, path: Path, line: int, rule: str, detail: str) -> None:
        self.path = path
        self.line = line
        self.rule = rule
        self.detail = detail

    def __str__(self) -> str:
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


def _first_word(command: str) -> str:
    """Return the executable a command line invokes, ignoring env prefixes.

    `VAR=x just test-unit` is not a `just` step on Windows - the POSIX env
    prefix is a parse error under both `cmd.exe` and PowerShell - so the
    prefix is reported rather than skipped past.
    """
    return command.split(maxsplit=1)[0] if command.split() else ""


def audit(root: Path) -> list[Finding]:
    """Return every contract violation under `root/.github/workflows`."""
    github = root / ".github"
    workflows = sorted((github / "workflows").glob("*.yml")) + sorted(
        (github / "workflows").glob("*.yaml")
    )
    allowlist = _load_allowlist(github)
    findings: list[Finding] = []

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        name = path.name

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
            if JUST_INSTALL_USES not in text:
                findings.append(
                    Finding(
                        path,
                        1,
                        "install",
                        "calls `just` but does not install it with "
                        f"{JUST_INSTALL_USES}",
                    )
                )
            elif JUST_INSTALL_TOOL not in text:
                findings.append(
                    Finding(
                        path,
                        1,
                        "install",
                        "installs `just` without the fleet floor pin "
                        f"{JUST_INSTALL_TOOL}",
                    )
                )

        for number, step, command in _run_commands(text):
            key = f"{name}:{step}"
            if key in allowlist or name in allowlist:
                continue
            if _first_word(command) in ALLOWED_COMMANDS:
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
    root = Path(args[0]) if args else Path.cwd()
    findings = audit(root)
    for finding in findings:
        print(str(finding))
    if findings:
        print(
            f"\n{len(findings)} CI-contract violation(s). A `run:` step may only call "
            "a just recipe, run `gh` bookkeeping, or be named in "
            f".github/{ALLOWLIST_NAME} with the reason it is not a recipe yet.",
            file=sys.stderr,
        )
        return 1
    print("PASS: every workflow calls recipes and installs one pinned `just`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
