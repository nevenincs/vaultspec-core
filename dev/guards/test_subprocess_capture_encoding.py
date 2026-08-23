"""Every capture of the vaultspec CLI must decode as UTF-8, not as the locale.

The CLI reconfigures its own stdout to UTF-8 the moment it starts
(:func:`vaultspec_core.console.configure_stdio`), precisely so a Windows
console on a legacy codepage cannot make it crash on a non-ASCII character.
That is a promise about the bytes it writes, and a caller that captures those
bytes has to decode them the same way.

``subprocess.run(..., text=True)`` does not. Without an explicit ``encoding``
it decodes with :func:`locale.getencoding`, which is ``cp1252`` on the Windows
CI runners. The two contracts then disagree, and the disagreement is invisible
until the child happens to emit a byte outside cp1252 - at which point
``communicate()`` raises ``UnicodeDecodeError`` on a pipe-reader thread, the
captured output comes back empty, and the call looks like the child failed.

Issue #321 is what surfaced this. A concurrent-CLI test reported one child
with empty output and a non-zero status, on two unrelated pull requests,
passing on every rerun. The empty output was the decode fault: the captured
text never survived the pipe-reader thread.

Being precise about what that does and does not establish - the decode fault
destroyed the *evidence*, and this guard stops that recurring. It is not known
to be why the child failed, and probably was not: the byte in the CI log was
``0x90``, undefined in cp1252 and invalid as standalone UTF-8 but valid in
cp437 and cp850, which points at an OS-level message from a child that died
rather than at anything this CLI wrote. Keeping the encoding honest is worth
doing on its own terms; it is not a fix for whatever killed that process.

This guard makes the mismatch impossible to reintroduce quietly. It is
deliberately narrow: it fires only on calls that spawn *this* CLI, where the
UTF-8 promise is documented and therefore the mismatch is provable. Capturing
``git`` or a bare ``python -c`` snippet is a weaker case - those write in
whatever encoding the platform hands them - and forcing a decision there would
turn a real invariant into a style rule nobody trusts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Trees carrying committed Python, matching the other guards in this package.
SOURCE_ROOTS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "dev",
    PROJECT_ROOT / "docs",
)

#: Tokens that identify a command line as spawning this project's CLI. The
#: module form is how the tests invoke it; the script form is how an installed
#: environment does.
_CLI_TOKENS = ("vaultspec_core", "vaultspec-core")

#: The subprocess constructors that capture output.
_SPAWNERS = ("run", "Popen", "check_output")


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        files.extend(root.rglob("*.py"))
    return sorted(set(files))


def _is_spawn_call(node: ast.Call) -> bool:
    """Return whether *node* constructs a subprocess."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in _SPAWNERS
    if isinstance(func, ast.Name):
        return func.id in _SPAWNERS
    return False


def _spawns_this_cli(node: ast.Call) -> bool:
    """Return whether *node*'s command line names this project's CLI.

    Reads the unparsed call rather than only its first argument: the argv is
    frequently built inline as a list literal, and sometimes assembled from a
    name plus a splat, so a structural walk would miss more than it caught.
    """
    rendered = ast.unparse(node)
    return any(token in rendered for token in _CLI_TOKENS)


def _captures_output(node: ast.Call) -> bool:
    """Return whether *node* asks for the child's output as text."""
    keywords = {kw.arg for kw in node.keywords}
    return "text" in keywords or "universal_newlines" in keywords


def test_cli_captures_decode_as_utf8() -> None:
    """A capture of this CLI names its encoding rather than inheriting one."""
    offenders: list[str] = []

    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - a parse failure is its own bug
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (_is_spawn_call(node) and _spawns_this_cli(node)):
                continue
            if not _captures_output(node):
                continue
            if "encoding" in {kw.arg for kw in node.keywords}:
                continue
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            offenders.append(f"{relative}:{node.lineno}")

    assert not offenders, (
        "These calls capture the vaultspec CLI but decode with the locale "
        "codec, which is cp1252 on the Windows runners while the CLI writes "
        'UTF-8. Add encoding="utf-8" (and errors="replace"), as '
        "src/vaultspec_core/mcp_server/tools/gateway.py already does:\n  - "
        + "\n  - ".join(offenders)
    )
