"""Tests for diagnostic signal collectors and the diagnose orchestrator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vaultspec_core.core.diagnosis.collectors import (
    collect_builtin_version_state,
    collect_config_state,
    collect_content_integrity,
    collect_framework_presence,
    collect_gitignore_state,
    collect_manifest_coherence,
    collect_mcp_config_state,
    collect_provider_dir_state,
    collect_vault_content_state,
)
from vaultspec_core.core.diagnosis.diagnosis import diagnose
from vaultspec_core.core.diagnosis.signals import (
    BuiltinVersionSignal,
    ConfigSignal,
    ContentSignal,
    FrameworkSignal,
    GitignoreSignal,
    ManifestEntrySignal,
    ProviderDirSignal,
    VaultContentSignal,
)
from vaultspec_core.core.enums import Tool
from vaultspec_core.core.gitignore import DEFAULT_ENTRIES, MARKER_BEGIN, MARKER_END

pytestmark = [pytest.mark.unit]


def _write_manifest(root: Path, installed: list[str]) -> None:
    """Write a minimal valid providers.json manifest."""
    path = root / ".vaultspec" / "providers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "2.0", "installed": installed, "serial": 1}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_gitignore(root: Path, content: str) -> None:
    gi = root / ".gitignore"
    gi.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# collect_framework_presence
# ---------------------------------------------------------------------------
class TestFrameworkPresence:
    def test_missing(self, tmp_path: Path) -> None:
        assert collect_framework_presence(tmp_path) == FrameworkSignal.MISSING

    def test_corrupted_no_manifest(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        assert collect_framework_presence(tmp_path) == FrameworkSignal.CORRUPTED

    def test_corrupted_invalid_json(self, tmp_path: Path) -> None:
        d = tmp_path / ".vaultspec"
        d.mkdir()
        (d / "providers.json").write_text("{bad", encoding="utf-8")
        assert collect_framework_presence(tmp_path) == FrameworkSignal.CORRUPTED

    def test_corrupted_no_installed_key(self, tmp_path: Path) -> None:
        d = tmp_path / ".vaultspec"
        d.mkdir()
        (d / "providers.json").write_text('{"version": "2.0"}', encoding="utf-8")
        assert collect_framework_presence(tmp_path) == FrameworkSignal.CORRUPTED

    def test_present(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ["claude"])
        assert collect_framework_presence(tmp_path) == FrameworkSignal.PRESENT


# ---------------------------------------------------------------------------
# collect_manifest_coherence
# ---------------------------------------------------------------------------
class TestManifestCoherence:
    def test_coherent(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ["claude"])
        (tmp_path / ".claude").mkdir()
        result = collect_manifest_coherence(tmp_path)
        assert result["claude"] == ManifestEntrySignal.COHERENT

    def test_orphaned(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ["claude"])
        result = collect_manifest_coherence(tmp_path)
        assert result["claude"] == ManifestEntrySignal.ORPHANED

    def test_untracked(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, [])
        (tmp_path / ".claude").mkdir()
        result = collect_manifest_coherence(tmp_path)
        assert result["claude"] == ManifestEntrySignal.UNTRACKED

    def test_not_installed(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, [])
        result = collect_manifest_coherence(tmp_path)
        assert result["claude"] == ManifestEntrySignal.NOT_INSTALLED

    def test_shared_agents_dir_owned_by_gemini_is_not_antigravity_untracked(
        self, tmp_path: Path
    ) -> None:
        _write_manifest(tmp_path, ["gemini"])
        (tmp_path / ".gemini").mkdir()
        (tmp_path / ".agents").mkdir()

        result = collect_manifest_coherence(tmp_path)

        assert result["gemini"] == ManifestEntrySignal.COHERENT
        assert result["antigravity"] == ManifestEntrySignal.NOT_INSTALLED

    def test_shared_agents_dir_owned_by_codex_is_not_antigravity_untracked(
        self, tmp_path: Path
    ) -> None:
        _write_manifest(tmp_path, ["codex"])
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".agents").mkdir()

        result = collect_manifest_coherence(tmp_path)

        assert result["codex"] == ManifestEntrySignal.COHERENT
        assert result["antigravity"] == ManifestEntrySignal.NOT_INSTALLED

    def test_unowned_agents_dir_is_untracked_antigravity(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, [])
        (tmp_path / ".agents").mkdir()

        result = collect_manifest_coherence(tmp_path)

        assert result["antigravity"] == ManifestEntrySignal.UNTRACKED


# ---------------------------------------------------------------------------
# collect_vault_content_state
# ---------------------------------------------------------------------------
class TestVaultContentState:
    def test_no_vault(self, tmp_path: Path) -> None:
        assert collect_vault_content_state(tmp_path) == (
            VaultContentSignal.NO_VAULT,
            0,
            0,
        )

    def test_clean_vault(self, tmp_path: Path) -> None:
        doc = tmp_path / ".vault" / "research" / "2026-05-15-clean.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "---\n"
            "tags:\n"
            "  - '#research'\n"
            "  - '#clean-vault'\n"
            "date: '2026-05-15'\n"
            "related: []\n"
            "---\n"
            "\n"
            "# Clean vault\n",
            encoding="utf-8",
        )

        assert collect_vault_content_state(tmp_path) == (
            VaultContentSignal.CLEAN,
            0,
            0,
        )

    def test_annotations_include_malformed_standalone_syntax(
        self, tmp_path: Path
    ) -> None:
        doc = tmp_path / ".vault" / "research" / "2026-05-15-annotated.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "---\n"
            "tags:\n"
            "  - '#research'\n"
            "  - '#annotated-vault'\n"
            "date: '2026-05-15'\n"
            "related: []\n"
            "---\n"
            "\n"
            "<-- Malformed generated annotation. -->\n",
            encoding="utf-8",
        )

        assert collect_vault_content_state(tmp_path) == (
            VaultContentSignal.ANNOTATIONS,
            1,
            0,
        )

    def test_skips_internal_and_archive_documents(self, tmp_path: Path) -> None:
        for rel_path in (
            ".vault/.obsidian/internal.md",
            ".vault/_archive/old.md",
        ):
            path = tmp_path / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<-- Ignored generated annotation. -->\n", encoding="utf-8")

        assert collect_vault_content_state(tmp_path) == (
            VaultContentSignal.CLEAN,
            0,
            0,
        )

    def test_unreadable_vault_markdown(self, tmp_path: Path) -> None:
        doc = tmp_path / ".vault" / "research" / "2026-05-15-unreadable.md"
        doc.parent.mkdir(parents=True)
        doc.write_bytes(b"\xff\xfe\xfa")

        assert collect_vault_content_state(tmp_path) == (
            VaultContentSignal.UNREADABLE,
            0,
            1,
        )


# ---------------------------------------------------------------------------
# collect_provider_dir_state
# ---------------------------------------------------------------------------
class TestProviderDirState:
    def test_missing(self, tmp_path: Path) -> None:
        assert (
            collect_provider_dir_state(tmp_path, "claude") == ProviderDirSignal.MISSING
        )

    def test_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        assert collect_provider_dir_state(tmp_path, "claude") == ProviderDirSignal.EMPTY

    def test_partial_without_context(self, tmp_path: Path) -> None:
        """Without an active WorkspaceContext, a non-empty dir is PARTIAL.

        Uses a factory-built workspace without init_paths so the
        contextvar is genuinely unset for the target path.
        """
        d = tmp_path / ".claude"
        d.mkdir()
        (d / "some_file.txt").write_text("x", encoding="utf-8")

        # The collector catches LookupError and also handles the case
        # where get_context() returns a context for a DIFFERENT target.
        # When cfg is None (no tool config for this target), returns PARTIAL.
        result = collect_provider_dir_state(tmp_path, "claude")
        assert result in (ProviderDirSignal.PARTIAL, ProviderDirSignal.MIXED)

    def test_complete(self, synthetic_project: Path) -> None:
        """With a full test project, claude provider should be COMPLETE."""
        result = collect_provider_dir_state(synthetic_project, "claude")
        assert result in (ProviderDirSignal.COMPLETE, ProviderDirSignal.PARTIAL)

    def test_host_native_file_is_not_mixed(self, synthetic_project: Path) -> None:
        """Host-tool-native files must not classify the dir as MIXED (issue #122).

        Claude Code creates ``.claude/settings.local.json`` during normal use;
        its presence previously made ``spec doctor`` report MIXED and exit 1,
        which blocked every markdown commit via the bundled spec-check hook.
        """
        baseline = collect_provider_dir_state(synthetic_project, "claude")
        claude_dir = synthetic_project / ".claude"
        (claude_dir / "settings.local.json").write_text("{}\n", encoding="utf-8")
        (claude_dir / "settings.json").write_text("{}\n", encoding="utf-8")
        (claude_dir / ".gitignore").write_text("*.local\n", encoding="utf-8")

        after = collect_provider_dir_state(synthetic_project, "claude")
        assert after != ProviderDirSignal.MIXED
        assert after == baseline

    def test_unmanaged_file_is_still_mixed(self, synthetic_project: Path) -> None:
        """A genuinely unmanaged extra file still classifies as MIXED.

        Only allow-listed host-native files are benign; the MIXED signal must
        remain meaningful for everything else.
        """
        (synthetic_project / ".claude" / "stray-foreign.bin").write_text(
            "x", encoding="utf-8"
        )
        assert (
            collect_provider_dir_state(synthetic_project, "claude")
            == ProviderDirSignal.MIXED
        )

    def test_unknown_tool(self, tmp_path: Path) -> None:
        assert (
            collect_provider_dir_state(tmp_path, "nonexistent")
            == ProviderDirSignal.MISSING
        )

    def test_provider_native_mcp_config_is_not_mixed(
        self, synthetic_project: Path
    ) -> None:
        """A provider-native mcp_config.json (and its .lock) is not foreign.

        The MCP writer deploys mcp_config.json into providers such as
        Antigravity's .agents/ dir; the doctor must read the same ToolConfig
        field the writer uses instead of flagging the framework's own artefact
        as MIXED.
        """
        from vaultspec_core.core.types import get_context

        ctx = get_context()
        tool = next(
            (
                t
                for t, cfg in ctx.tool_configs.items()
                if cfg.mcp_config_file is not None
            ),
            None,
        )
        assert tool is not None, "expected a provider with a native MCP config"
        mcp_path = ctx.tool_configs[tool].mcp_config_file
        assert mcp_path is not None

        baseline = collect_provider_dir_state(synthetic_project, tool.value)
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text('{"mcpServers": {}}\n', encoding="utf-8")
        (mcp_path.parent / f"{mcp_path.name}.lock").write_text("", encoding="utf-8")

        after = collect_provider_dir_state(synthetic_project, tool.value)
        assert after != ProviderDirSignal.MIXED
        assert after == baseline


# ---------------------------------------------------------------------------
# collect_builtin_version_state
# ---------------------------------------------------------------------------
class TestBuiltinVersionState:
    def test_no_snapshots(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir(parents=True)
        assert (
            collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.NO_SNAPSHOTS
        )

    def test_current(self, tmp_path: Path) -> None:
        vs = tmp_path / ".vaultspec"
        snap = vs / "_snapshots" / "rules"
        snap.mkdir(parents=True)
        rules = vs / "rules"
        rules.mkdir(parents=True)

        (snap / "test.builtin.md").write_text("content", encoding="utf-8")
        (rules / "test.builtin.md").write_text("content", encoding="utf-8")

        assert collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.CURRENT

    def test_modified(self, tmp_path: Path) -> None:
        vs = tmp_path / ".vaultspec"
        snap = vs / "_snapshots" / "rules"
        snap.mkdir(parents=True)
        rules = vs / "rules"
        rules.mkdir(parents=True)

        (snap / "test.builtin.md").write_text("original", encoding="utf-8")
        (rules / "test.builtin.md").write_text("changed", encoding="utf-8")

        assert collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.MODIFIED

    def test_deleted(self, tmp_path: Path) -> None:
        vs = tmp_path / ".vaultspec"
        snap = vs / "_snapshots" / "rules"
        snap.mkdir(parents=True)
        (vs / "rules").mkdir(parents=True)

        (snap / "test.builtin.md").write_text("original", encoding="utf-8")
        # No corresponding file in rules/

        assert collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.DELETED

    def test_prune_orphan_snapshots_recovers_from_deleted(self, tmp_path: Path) -> None:
        """Pruning an orphan snapshot returns builtin_version from DELETED to clean.

        A builtin retired from the framework leaves its snapshot behind, which
        pins builtin_version at DELETED forever. prune_orphan_snapshots removes
        the snapshot whose live builtin is gone, restoring a clean state.
        """
        from vaultspec_core.core.revert import prune_orphan_snapshots

        vs = tmp_path / ".vaultspec"
        snap = vs / "_snapshots" / "rules"
        snap.mkdir(parents=True)
        rules = vs / "rules"
        rules.mkdir(parents=True)

        # A live builtin (kept) and an orphan snapshot (retired builtin).
        (snap / "live.builtin.md").write_text("content", encoding="utf-8")
        (rules / "live.builtin.md").write_text("content", encoding="utf-8")
        (snap / "retired.builtin.md").write_text("gone", encoding="utf-8")

        assert collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.DELETED

        removed = prune_orphan_snapshots(vs)
        assert removed == 1
        assert not (snap / "retired.builtin.md").exists()
        assert (snap / "live.builtin.md").exists()
        assert collect_builtin_version_state(tmp_path) == BuiltinVersionSignal.CURRENT


# ---------------------------------------------------------------------------
# collect_config_state
# ---------------------------------------------------------------------------
class TestConfigState:
    def test_missing_no_context(self, tmp_path: Path) -> None:
        """Without WorkspaceContext, config is always MISSING."""
        assert collect_config_state("claude") == ConfigSignal.MISSING

    def test_ok_with_marker(self, synthetic_project: Path) -> None:
        """After install, CLAUDE.md should have the AUTO-GENERATED marker."""
        result = collect_config_state("claude")
        assert result == ConfigSignal.OK

    def test_foreign_without_marker(self, synthetic_project: Path) -> None:
        """Overwriting config content without marker yields FOREIGN."""
        from vaultspec_core.core.types import get_context

        cfg = get_context().tool_configs[Tool.CLAUDE]
        assert cfg.config_file is not None
        cfg.config_file.write_text("# My custom config\n", encoding="utf-8")
        assert collect_config_state("claude") == ConfigSignal.FOREIGN


# ---------------------------------------------------------------------------
# collect_mcp_config_state
# ---------------------------------------------------------------------------
class TestMcpConfigState:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert collect_mcp_config_state(tmp_path) == ConfigSignal.PARTIAL_MCP

    def test_no_vaultspec_entry(self, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {}}', encoding="utf-8")
        assert collect_mcp_config_state(tmp_path) == ConfigSignal.PARTIAL_MCP

    def test_ok(self, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        payload = {"mcpServers": {"vaultspec-core": {"command": "uv"}}}
        mcp.write_text(json.dumps(payload), encoding="utf-8")
        assert collect_mcp_config_state(tmp_path) == ConfigSignal.OK

    def test_user_mcp(self, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        payload = {
            "mcpServers": {
                "vaultspec-core": {"command": "uv"},
                "other-server": {"command": "node"},
            }
        }
        mcp.write_text(json.dumps(payload), encoding="utf-8")
        assert collect_mcp_config_state(tmp_path) == ConfigSignal.USER_MCP


# ---------------------------------------------------------------------------
# collect_gitignore_state
# ---------------------------------------------------------------------------
class TestGitignoreState:
    def test_no_file(self, tmp_path: Path) -> None:
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.NO_FILE

    def test_no_entries(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, "node_modules/\n*.pyc\n")
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.NO_ENTRIES

    def test_complete(self, tmp_path: Path) -> None:
        entries = "\n".join(DEFAULT_ENTRIES)
        content = f"node_modules/\n\n{MARKER_BEGIN}\n{entries}\n{MARKER_END}\n"
        _write_gitignore(tmp_path, content)
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.COMPLETE

    def test_partial(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        content = f"{MARKER_BEGIN}\nsome/other/path\n{MARKER_END}\n"
        _write_gitignore(tmp_path, content)
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.PARTIAL

    def test_corrupted_only_begin(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, f"{MARKER_BEGIN}\nentry\n")
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.CORRUPTED

    def test_corrupted_only_end(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, f"entry\n{MARKER_END}\n")
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.CORRUPTED


# ---------------------------------------------------------------------------
# collect_content_integrity
# ---------------------------------------------------------------------------
class TestContentIntegrity:
    def test_empty_without_context(self, tmp_path: Path) -> None:
        result = collect_content_integrity("claude")
        assert result == {}

    def test_clean_stale_missing(self, synthetic_project: Path) -> None:
        """With a real project, rule files synced from source are CLEAN."""
        from vaultspec_core.core.types import get_context

        ctx = get_context()
        cfg = ctx.tool_configs.get(Tool.CLAUDE)
        assert cfg is not None and cfg.rules_dir is not None

        result = collect_content_integrity("claude")
        # All files present in both source and dest should be CLEAN
        for name, signal in result.items():
            if signal == ContentSignal.CLEAN:
                assert (cfg.rules_dir / name).exists()
                assert (ctx.rules_src_dir / name).exists()

    def test_builtin_files_not_flagged_stale(self, synthetic_project: Path) -> None:
        """Synthesized ``*-system.builtin.md`` files must not be flagged STALE.

        These files are generated by :func:`~vaultspec_core.core.system.system_sync`
        and have no corresponding source file in ``.vaultspec/``.
        """
        from vaultspec_core.core.types import get_context

        ctx = get_context()
        cfg = ctx.tool_configs.get(Tool.CLAUDE)
        assert cfg is not None and cfg.rules_dir is not None

        # Place a synthesized builtin file in the dest rules dir
        builtin = cfg.rules_dir / "vaultspec-system.builtin.md"
        builtin.write_text("# Synthesized builtin\n", encoding="utf-8")

        result = collect_content_integrity("claude")
        assert "vaultspec-system.builtin.md" not in result

    def test_project_authored_rule_synced_flat_is_clean(
        self, synthetic_project: Path
    ) -> None:
        """A project-authored custom rule, synced FLAT, is CLEAN, not stale.

        Regression for issue #153: custom rules are authored one level down
        under ``.vaultspec/rules/project/`` but providers do not support
        nested folders - sync sanitizes the nesting, flattening the rule into
        the provider root by its basename. The collector must therefore match
        the recursively-discovered source basename against the flat provider
        deployment and report CLEAN, rather than flagging the source as
        STALE/MISSING because the destination has no ``project/`` subdir.
        """
        from vaultspec_core.core.rules import rules_sync
        from vaultspec_core.core.types import get_context

        ctx = get_context()
        cfg = ctx.tool_configs.get(Tool.CLAUDE)
        assert cfg is not None and cfg.rules_dir is not None

        # Source: authored under project/ (one level down).
        src_rule = ctx.rules_src_dir / "project" / "custom-rule.md"
        src_rule.parent.mkdir(parents=True, exist_ok=True)
        src_rule.write_text("# custom rule\n", encoding="utf-8")

        # Deploy through the real sync path (which flattens the nesting and
        # writes the transformed content) rather than hand-writing raw bytes:
        # content integrity now compares rendered content, so the destination
        # must hold what sync actually emits to read CLEAN.
        rules_sync()

        result = collect_content_integrity("claude")
        assert result["custom-rule.md"] == ContentSignal.CLEAN

    def test_content_drift_reports_diverged_and_agrees_with_sync(
        self, synthetic_project: Path
    ) -> None:
        """A content-drifted deployed rule reads DIVERGED, and sync would update it.

        Regression for the install/sync/doctor disagreement: the prior
        name-only check reported a content-drifted file as CLEAN while sync
        would rewrite it. The collector now routes through the same comparator
        sync uses, so the two surfaces agree.
        """
        from vaultspec_core.core.rules import rules_sync
        from vaultspec_core.core.types import get_context

        ctx = get_context()
        cfg = ctx.tool_configs.get(Tool.CLAUDE)
        assert cfg is not None and cfg.rules_dir is not None

        # A real, synced builtin rule whose deployed copy we corrupt in place.
        target = cfg.rules_dir / "vaultspec.builtin.md"
        assert target.exists()
        target.write_text("# drifted content not matching source\n", encoding="utf-8")

        # Doctor: the file is DIVERGED, not a false CLEAN.
        result = collect_content_integrity("claude")
        assert result["vaultspec.builtin.md"] == ContentSignal.DIVERGED

        # Sync: claude's copy of the same file is queued for [UPDATE]. The two
        # surfaces agree. (Other providers share the basename but were not
        # drifted, so match on the exact claude destination path.)
        sync_result = rules_sync(dry_run=True)
        target_str = str(target).replace("\\", "/")
        claude_actions = [a for p, a in sync_result.items if p == target_str]
        assert claude_actions == ["[UPDATE]"]


# ---------------------------------------------------------------------------
# diagnose() orchestrator
# ---------------------------------------------------------------------------
class TestDiagnose:
    def test_missing_framework(self, tmp_path: Path) -> None:
        """When framework is missing, only gitignore and framework are set."""
        _write_gitignore(tmp_path, "*.pyc\n")
        result = diagnose(tmp_path, scope="full")
        assert result.framework == FrameworkSignal.MISSING
        assert result.gitignore == GitignoreSignal.NO_ENTRIES
        assert result.providers == {}

    def test_framework_scope(self, tmp_path: Path) -> None:
        """Framework scope collects manifest coherence but not dir state."""
        _write_manifest(tmp_path, ["claude"])
        (tmp_path / ".claude").mkdir()
        _write_gitignore(tmp_path, "*.pyc\n")

        result = diagnose(tmp_path, scope="framework")
        assert result.framework == FrameworkSignal.PRESENT
        assert Tool.CLAUDE in result.providers
        # Framework scope sets dir_state to MISSING (not collected)
        assert result.providers[Tool.CLAUDE].dir_state == ProviderDirSignal.MISSING
        claude = result.providers[Tool.CLAUDE]
        assert claude.manifest_entry == ManifestEntrySignal.COHERENT
        assert claude.config == ConfigSignal.OK

    def test_sync_scope(self, tmp_path: Path) -> None:
        """Sync scope collects provider dir and config but not content."""
        _write_manifest(tmp_path, ["claude"])
        (tmp_path / ".claude").mkdir()
        _write_gitignore(tmp_path, "*.pyc\n")

        result = diagnose(tmp_path, scope="sync")
        assert result.framework == FrameworkSignal.PRESENT
        assert Tool.CLAUDE in result.providers
        prov = result.providers[Tool.CLAUDE]
        # Content is not collected in sync scope
        assert prov.content == {}

    def test_full_scope_with_project(self, synthetic_project: Path) -> None:
        """Full scope on a real project collects everything."""
        result = diagnose(synthetic_project, scope="full")
        assert result.framework == FrameworkSignal.PRESENT
        assert result.builtin_version in (
            BuiltinVersionSignal.CURRENT,
            BuiltinVersionSignal.NO_SNAPSHOTS,
        )
        assert Tool.CLAUDE in result.providers
        prov = result.providers[Tool.CLAUDE]
        assert prov.manifest_entry == ManifestEntrySignal.COHERENT

    def test_corrupted_framework_collects_partial_diagnosis(
        self, tmp_path: Path
    ) -> None:
        """When framework is corrupted, providers are still diagnosed for
        directory presence and manifest coherence (but not content integrity)."""
        d = tmp_path / ".vaultspec"
        d.mkdir()
        (d / "providers.json").write_text("{bad", encoding="utf-8")

        result = diagnose(tmp_path)
        assert result.framework == FrameworkSignal.CORRUPTED
        # Providers are populated with basic dir/manifest signals
        assert len(result.providers) > 0
        for prov in result.providers.values():
            # Content integrity is not collected when corrupted
            assert prov.content == {}
            assert prov.config == ConfigSignal.OK


# ---------------------------------------------------------------------------
# collect_gitignore_state with inverted markers
# ---------------------------------------------------------------------------
class TestGitignoreInvertedMarkers:
    def test_inverted_markers_returns_corrupted(self, tmp_path: Path) -> None:
        content = f"node_modules/\n{MARKER_END}\n.entry/\n{MARKER_BEGIN}\n"
        _write_gitignore(tmp_path, content)
        assert collect_gitignore_state(tmp_path) == GitignoreSignal.CORRUPTED


# ---------------------------------------------------------------------------
# diagnose() scope validation
# ---------------------------------------------------------------------------
class TestDiagnoseScopeValidation:
    def test_invalid_scope_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid scope"):
            diagnose(tmp_path, scope="nonsense")
