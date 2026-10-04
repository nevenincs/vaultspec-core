"""MCP cannot import host files; explicit local CLI imports remain available."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.mcp_server.tools.gateway import register_gateway_tools

from .conftest import data_of, vault_root

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit]

_RESOURCES = ("rules", "skills", "agents")
_SENTINEL = "private host file content\n"
_BODY_VERBS = ("vault set-body", "vault edit", "vault adr crossref")


def _body_document(root: Path) -> Path:
    path = root / ".vault" / "adr" / "2026-01-01-import-probe-adr.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntags: ['#adr', '#import-probe']\ndate: '2026-01-01'\n"
        "modified: '2026-01-01'\nrelated: []\n---\n\nOriginal body.\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("verb", _BODY_VERBS)
async def test_gateway_rejects_body_file_import(vault_root: Path, verb: str) -> None:
    document = _body_document(vault_root)
    original = document.read_bytes()
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    async with Client(_server()) as client:
        for key in ("body-file", "body_file", "--body-file", "--body_file"):
            for value in (str(source), "../private.md", [str(source)]):
                result = await client.call_tool(
                    "invoke",
                    {
                        "verb": verb,
                        "positionals": [document.stem],
                        "arguments": {key: value},
                    },
                )
                assert result.is_error
                text = " ".join(
                    item.text
                    for item in result.content
                    if isinstance(item, TextContent)
                )
                assert "not available through the gateway" in text
                assert _SENTINEL not in text
                assert document.read_bytes() == original
        result = await client.call_tool("discover", {"query": verb, "limit": 50})
        entry = next(item for item in data_of(result)["verbs"] if item["verb"] == verb)
        assert "--body-file" not in {flag["name"] for flag in entry["flags"]}


@pytest.mark.parametrize("verb", _BODY_VERBS)
@pytest.mark.parametrize("source_exists", (True, False))
def test_gateway_child_refuses_body_file_before_reading(
    vault_root: Path, verb: str, source_exists: bool
) -> None:
    document = _body_document(vault_root)
    original = document.read_bytes()
    source = vault_root.parent / "private.md"
    if source_exists:
        source.write_text(_SENTINEL, encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "--target",
            str(vault_root),
            *verb.split(),
            document.stem,
            "--body-file",
            str(source),
            "--json",
        ],
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == (2 if verb.endswith("crossref") else 1), result.output
    assert "unavailable through MCP" in result.output
    assert "Cannot read" not in result.output
    assert _SENTINEL not in result.output
    assert document.read_bytes() == original


@pytest.mark.parametrize("verb", ("set-body", "edit"))
@pytest.mark.parametrize("channel", ("local-file", "gateway-stdin"))
def test_body_edit_keeps_authorized_channels(
    vault_root: Path, verb: str, channel: str
) -> None:
    document = _body_document(vault_root)
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    use_stdin = channel == "gateway-stdin"
    result = CliRunner().invoke(
        app,
        [
            "--target",
            str(vault_root),
            "vault",
            verb,
            document.stem,
            *(["--body-stdin"] if use_stdin else ["--body-file", str(source)]),
            "--no-check",
            "--json",
        ],
        input=_SENTINEL.replace("\n", "\r\n") if use_stdin else None,
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"} if use_stdin else {},
    )
    assert result.exit_code == 0, result.output
    assert _SENTINEL in document.read_text(encoding="utf-8")
    assert b"\r\r\n" not in document.read_bytes()


def _server() -> MCPServer[None]:
    server = MCPServer(name="file-import-boundary")
    register_gateway_tools(server)
    return server


def _resource_path(root: Path, resource: str, name: str) -> Path:
    if resource == "triggers":
        return root / ".vaultspec" / "triggers" / f"{name}.yaml"
    base = root / ".vaultspec" / resource
    return base / name / "SKILL.md" if resource == "skills" else base / f"{name}.md"


@pytest.mark.parametrize("resource", _RESOURCES)
async def test_gateway_rejects_file_import(vault_root: Path, resource: str) -> None:
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    async with Client(_server()) as client:
        for key in ("from-file", "from_file", "--from-file", "--from_file"):
            for value in (str(source), "../private.md", [str(source)]):
                result = await client.call_tool(
                    "invoke",
                    {
                        "verb": f"spec {resource} add",
                        "positionals": ["import-probe"],
                        "arguments": {key: value},
                    },
                )
                shown = await client.call_tool(
                    "invoke",
                    {"verb": f"spec {resource} show", "positionals": ["import-probe"]},
                )
                assert result.is_error, data_of(shown)
                text = " ".join(
                    item.text
                    for item in result.content
                    if isinstance(item, TextContent)
                )
                assert "not available through the gateway" in text
                assert data_of(shown)["ok"] is False
                assert not _resource_path(vault_root, resource, "import-probe").exists()


async def test_gateway_rejects_template_file_import(vault_root: Path) -> None:
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    async with Client(_server()) as client:
        for value in (str(source), "../../../private.md"):
            result = await client.call_tool(
                "invoke",
                {
                    "verb": "spec skills add",
                    "positionals": ["template-probe"],
                    "arguments": {"template": value},
                },
            )
            shown = await client.call_tool(
                "invoke",
                {"verb": "spec skills show", "positionals": ["template-probe"]},
            )
            assert result.is_error, data_of(shown)
            assert data_of(shown)["ok"] is False
            assert not _resource_path(vault_root, "skills", "template-probe").exists()


async def test_discovery_hides_file_import_options(vault_root: Path) -> None:
    async with Client(_server()) as client:
        for resource in _RESOURCES:
            result = await client.call_tool(
                "discover", {"query": f"spec {resource} add", "limit": 50}
            )
            entry = next(
                item
                for item in data_of(result)["verbs"]
                if item["verb"] == f"spec {resource} add"
            )
            flags = {flag["name"] for flag in entry["flags"]}
            assert "--body" in flags
            assert "--from-file" not in flags
            assert "--template" not in flags


@pytest.mark.parametrize("resource", (*_RESOURCES, "triggers"))
@pytest.mark.parametrize("source_exists", (True, False))
def test_gateway_child_refuses_file_import_before_reading(
    vault_root: Path, resource: str, source_exists: bool
) -> None:
    source = vault_root.parent / "private.md"
    if source_exists:
        source.write_text(_SENTINEL, encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "--target",
            str(vault_root),
            "spec",
            resource,
            "add",
            "child-probe",
            "--from-file",
            str(source),
        ],
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == 2, result.output
    assert "unavailable through MCP" in result.output
    assert "File not found" not in result.output
    assert _SENTINEL not in result.output
    assert not _resource_path(vault_root, resource, "child-probe").exists()


@pytest.mark.parametrize("extra", ([], ["--body", "inline"], ["--dry-run"]))
def test_gateway_child_refuses_template_import(
    vault_root: Path, extra: list[str]
) -> None:
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "--target",
            str(vault_root),
            "spec",
            "skills",
            "add",
            "child-probe",
            "--template",
            str(source),
            *extra,
        ],
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == 2, result.output
    assert "unavailable through MCP" in result.output
    assert not _resource_path(vault_root, "skills", "child-probe").exists()


@pytest.mark.parametrize("resource", _RESOURCES)
async def test_gateway_keeps_inline_bodies_and_default_preview(
    vault_root: Path, resource: str
) -> None:
    async with Client(_server()) as client:
        for name, body in (
            ("inline-probe", "--from-file=private.md --template=x"),
            ("repeated-body-probe", ["first body", "--from-file"]),
        ):
            result = await client.call_tool(
                "invoke",
                {
                    "verb": f"spec {resource} add",
                    "positionals": [name],
                    "arguments": {"body": body},
                },
            )
            added = data_of(result)
            assert added["ok"] is True, added.get("stdout") or str(added)
            shown = await client.call_tool(
                "invoke", {"verb": f"spec {resource} show", "positionals": [name]}
            )
            payload = data_of(shown)
            assert payload["ok"] is True
            expected = body[-1] if isinstance(body, list) else body
            assert expected in payload["data"]["data"]["content"]
        preview = await client.call_tool(
            "invoke",
            {
                "verb": f"spec {resource} add",
                "positionals": ["default-probe"],
                "arguments": {"dry-run": True},
            },
        )
        assert data_of(preview)["ok"] is True
        assert not _resource_path(vault_root, resource, "default-probe").exists()


@pytest.mark.parametrize("resource", _RESOURCES)
def test_gateway_child_keeps_default_body(vault_root: Path, resource: str) -> None:
    result = CliRunner().invoke(
        app,
        ["--target", str(vault_root), "spec", resource, "add", "default-probe"],
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == 0, result.output
    assert _resource_path(vault_root, resource, "default-probe").is_file()


@pytest.mark.parametrize("resource", (*_RESOURCES, "triggers"))
def test_local_cli_keeps_file_import(vault_root: Path, resource: str) -> None:
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    runner = CliRunner()
    added = runner.invoke(
        app,
        [
            "--target",
            str(vault_root),
            "spec",
            resource,
            "add",
            "local-probe",
            "--from-file",
            str(source),
        ],
    )
    assert added.exit_code == 0, added.output
    shown = runner.invoke(
        app, ["--target", str(vault_root), "spec", resource, "show", "local-probe"]
    )
    assert shown.exit_code == 0, shown.output
    assert _SENTINEL in shown.output


@pytest.mark.parametrize("template_kind", ("path", "name"))
def test_local_cli_keeps_template_import(vault_root: Path, template_kind: str) -> None:
    source = vault_root.parent / "private.md"
    source.write_text(_SENTINEL, encoding="utf-8")
    template = str(source)
    if template_kind == "name":
        template = "local-template"
        (vault_root / ".vaultspec" / "templates" / f"{template}.md").write_text(
            _SENTINEL, encoding="utf-8"
        )
    result = CliRunner().invoke(
        app,
        [
            "--target",
            str(vault_root),
            "spec",
            "skills",
            "add",
            "local-probe",
            "--template",
            template,
        ],
    )
    assert result.exit_code == 0, result.output
    assert _SENTINEL in _resource_path(vault_root, "skills", "local-probe").read_text(
        encoding="utf-8"
    )
