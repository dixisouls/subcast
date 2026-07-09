"""Tests for the permission reader: settings.json parsing, existing-agent
scanning, live MCP tool discovery, and PermissionContext assembly.

Covers the fixtures the build spec calls for explicitly: empty settings,
partial settings, and conflicting allow/deny entries.
"""

import json
import sys
from pathlib import Path

from subcast.permission_reader import (
    BUILTIN_TOOLS,
    build_permission_context,
    discover_mcp_tools,
    filter_approved_mcp_servers,
    parse_permissions,
    read_mcp_server_configs,
    read_settings,
    scan_existing_agents,
)

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_SERVER_SCRIPT = FIXTURES / "fake_mcp_server.py"


def _load_settings_fixture(tmp_path: Path, fixture_name: str) -> dict:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "settings.json").write_text((FIXTURES / fixture_name).read_text())
    return read_settings(tmp_path)


def test_read_settings_returns_empty_dict_when_file_missing(tmp_path):
    assert read_settings(tmp_path) == {}


def test_read_settings_parses_existing_file(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"permissions": {"allow": ["Read"]}}')

    assert read_settings(tmp_path) == {"permissions": {"allow": ["Read"]}}


def test_parse_permissions_empty_settings_yields_defaults(tmp_path):
    settings = _load_settings_fixture(tmp_path, "settings_empty.json")

    result = parse_permissions(settings, known_tools=BUILTIN_TOOLS)

    assert result.allowed_tools == []
    assert result.denied_tools == []
    assert set(result.unmentioned_tools) == BUILTIN_TOOLS
    assert result.permission_mode == "default"


def test_parse_permissions_partial_settings_only_deny_present(tmp_path):
    settings = _load_settings_fixture(tmp_path, "settings_partial.json")

    result = parse_permissions(settings, known_tools=BUILTIN_TOOLS)

    # A scoped deny (has a real specifier, not bare or "(*)") leaves the
    # tool itself assignable; only unscoped denies remove a tool entirely.
    assert result.denied_tools == []
    assert "Bash" in result.unmentioned_tools


def test_parse_permissions_bare_deny_removes_tool_from_unmentioned():
    settings = {"permissions": {"deny": ["Write"]}}

    result = parse_permissions(settings, known_tools=BUILTIN_TOOLS)

    assert result.denied_tools == ["Write"]
    assert "Write" not in result.unmentioned_tools


def test_parse_permissions_bare_allow_marks_tool_allowed():
    settings = {"permissions": {"allow": ["WebFetch"]}}

    result = parse_permissions(settings, known_tools=BUILTIN_TOOLS)

    assert result.allowed_tools == ["WebFetch"]
    assert "WebFetch" not in result.unmentioned_tools


def test_parse_permissions_wildcard_deny_denies_all_known_tools():
    known = {"Bash", "Read", "mcp__foo__bar"}
    settings = {"permissions": {"deny": ["*"]}}

    result = parse_permissions(settings, known_tools=known)

    assert set(result.denied_tools) == known
    assert result.unmentioned_tools == []


def test_parse_permissions_mcp_wildcard_deny_denies_only_mcp_tools():
    known = {"Bash", "Read", "mcp__foo__bar", "mcp__foo__baz"}
    settings = {"permissions": {"deny": ["mcp__*"]}}

    result = parse_permissions(settings, known_tools=known)

    assert set(result.denied_tools) == {"mcp__foo__bar", "mcp__foo__baz"}
    assert set(result.unmentioned_tools) == {"Bash", "Read"}


def test_parse_permissions_conflicting_allow_and_deny_deny_wins(tmp_path):
    settings = _load_settings_fixture(tmp_path, "settings_conflicting.json")

    result = parse_permissions(settings, known_tools=BUILTIN_TOOLS)

    assert result.denied_tools == ["Read"]
    assert "Read" not in result.allowed_tools
    assert result.permission_mode == "acceptEdits"


def test_scan_existing_agents_parses_valid_files_and_skips_malformed(tmp_path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for agent_file in (FIXTURES / "sample_agents").glob("*.md"):
        (agents_dir / agent_file.name).write_text(agent_file.read_text())

    agents = scan_existing_agents(tmp_path)

    names = {agent.name for agent in agents}
    assert names == {"code-reviewer", "doc-writer"}


def test_scan_existing_agents_returns_empty_list_when_dir_missing(tmp_path):
    assert scan_existing_agents(tmp_path) == []


def test_read_mcp_server_configs_parses_mcp_json(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers": {"fake": {"command": "python3", "args": ["server.py"]}}}'
    )

    configs = read_mcp_server_configs(tmp_path)

    assert configs == {"fake": {"command": "python3", "args": ["server.py"]}}


def test_read_mcp_server_configs_returns_empty_dict_when_file_missing(tmp_path):
    assert read_mcp_server_configs(tmp_path) == {}


def test_read_mcp_server_configs_normalizes_array_form(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers": [{"name": "fake", "command": "python3", "args": ["s.py"]}]}'
    )

    configs = read_mcp_server_configs(tmp_path)

    assert configs == {"fake": {"command": "python3", "args": ["s.py"]}}


def test_read_mcp_server_configs_tolerates_malformed_json(tmp_path):
    (tmp_path / ".mcp.json").write_text("{ this is not valid json ")

    assert read_mcp_server_configs(tmp_path) == {}


def test_read_settings_tolerates_malformed_json(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{ broken json ")

    assert read_settings(tmp_path) == {}


# --- MCP approval gating (SEC-3): only servers approved in the git-untracked
# .claude/settings.local.json may be discovered, so a cloned repo's committed
# config can't self-approve and trigger a spawn. ---

SERVER_CONFIGS = {"fake": {"command": "python3", "args": ["s.py"]}}


def _write_local_settings(tmp_path: Path, payload: dict):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "settings.local.json").write_text(json.dumps(payload))


def test_filter_approved_none_without_local_approval(tmp_path):
    # No settings.local.json at all -> nothing approved.
    assert filter_approved_mcp_servers(tmp_path, SERVER_CONFIGS) == {}


def test_filter_approved_by_enabled_list(tmp_path):
    _write_local_settings(tmp_path, {"enabledMcpjsonServers": ["fake"]})

    assert filter_approved_mcp_servers(tmp_path, SERVER_CONFIGS) == SERVER_CONFIGS


def test_filter_approved_by_enable_all(tmp_path):
    _write_local_settings(tmp_path, {"enableAllProjectMcpServers": True})

    assert filter_approved_mcp_servers(tmp_path, SERVER_CONFIGS) == SERVER_CONFIGS


def test_filter_approved_disabled_overrides_enable_all(tmp_path):
    _write_local_settings(
        tmp_path,
        {"enableAllProjectMcpServers": True, "disabledMcpjsonServers": ["fake"]},
    )

    assert filter_approved_mcp_servers(tmp_path, SERVER_CONFIGS) == {}


def test_filter_approved_ignores_committed_settings_json(tmp_path):
    # The security-critical case: approvals in the committed settings.json
    # (which a cloned malicious repo could ship) must NOT count.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"enableAllProjectMcpServers": True})
    )

    assert filter_approved_mcp_servers(tmp_path, SERVER_CONFIGS) == {}


def test_build_permission_context_does_not_discover_unapproved_mcp(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fake": {"command": sys.executable, "args": [str(FAKE_SERVER_SCRIPT)]}
                }
            }
        )
    )

    context = build_permission_context(tmp_path)

    # Real, reachable server, but never approved locally -> never spawned.
    assert context.connected_mcp_tools == []


def test_build_permission_context_discovers_approved_mcp(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fake": {"command": sys.executable, "args": [str(FAKE_SERVER_SCRIPT)]}
                }
            }
        )
    )
    _write_local_settings(tmp_path, {"enabledMcpjsonServers": ["fake"]})

    context = build_permission_context(tmp_path)

    assert set(context.connected_mcp_tools) == {"mcp__fake__ping", "mcp__fake__echo"}


def test_discover_mcp_tools_returns_prefixed_names_from_real_server():
    server_configs = {
        "fake": {"command": sys.executable, "args": [str(FAKE_SERVER_SCRIPT)]}
    }

    tools = discover_mcp_tools(server_configs, timeout=10.0)

    assert set(tools) == {"mcp__fake__ping", "mcp__fake__echo"}


def test_discover_mcp_tools_skips_server_that_fails_to_start():
    server_configs = {"broken": {"command": "this-command-does-not-exist", "args": []}}

    tools = discover_mcp_tools(server_configs, timeout=2.0)

    assert tools == []


def test_build_permission_context_combines_everything(tmp_path):
    _load_settings_fixture(tmp_path, "settings_full.json")
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir()
    (agents_dir / "code-reviewer.md").write_text(
        (FIXTURES / "sample_agents" / "code-reviewer.md").read_text()
    )

    context = build_permission_context(tmp_path)

    # settings_full.json: allow=[WebFetch, Bash(npm run test *) (scoped, doesn't
    # count)], deny=[Write, Bash(rm -rf *) (scoped), mcp__* (no MCP servers
    # configured here, so nothing to expand)].
    assert context.allowed_tools == ["WebFetch"]
    assert context.denied_tools == ["Write"]
    assert context.permission_mode == "acceptEdits"
    assert [a.name for a in context.existing_agents] == ["code-reviewer"]
    assert context.connected_mcp_tools == []
