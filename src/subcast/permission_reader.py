"""Reads .claude/settings.json, existing agent tool lists, and connected MCP
servers to build a PermissionContext for the current project.

Tool naming rule: a deny entry only removes a tool from assignment when it
is a full match (bare tool name, or an explicit "(*)" specifier, or a
tool-name-position wildcard like "mcp__*"). A scoped deny like
"Bash(rm -rf *)" restricts a specific invocation but leaves the tool itself
generally assignable, matching how Claude Code itself treats these rules.
The same full-vs-scoped distinction applies to allow entries; scoped allow
rules don't establish that a whole tool is safe to freely assign.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import re
from pathlib import Path

from subcast.specs import PermissionContext, SubagentSpec

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

BUILTIN_TOOLS = frozenset(
    {
        "Agent",
        "Artifact",
        "AskUserQuestion",
        "Bash",
        "CronCreate",
        "CronDelete",
        "CronList",
        "Edit",
        "EnterPlanMode",
        "EnterWorktree",
        "ExitPlanMode",
        "ExitWorktree",
        "Glob",
        "Grep",
        "ListMcpResourcesTool",
        "LSP",
        "Monitor",
        "NotebookEdit",
        "PowerShell",
        "PushNotification",
        "Read",
        "ReadMcpResourceTool",
        "RemoteTrigger",
        "ReportFindings",
        "ScheduleWakeup",
        "SendMessage",
        "SendUserFile",
        "ShareOnboardingGuide",
        "Skill",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskOutput",
        "TaskStop",
        "TaskUpdate",
        "TodoWrite",
        "ToolSearch",
        "WaitForMcpServers",
        "WebFetch",
        "WebSearch",
        "Workflow",
        "Write",
    }
)

_MCP_SERVER_WILDCARD_ALLOW = re.compile(r"^mcp__[^*]+__\*$")


def _load_json_or_empty(path: Path) -> dict:
    """Reads and parses a JSON file, degrading to {} if it's missing or
    malformed rather than crashing the whole pipeline on a broken file."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def read_settings(project_root: str | Path) -> dict:
    return _load_json_or_empty(Path(project_root) / ".claude" / "settings.json")


def _split_rule(rule: str) -> tuple[str, str | None]:
    if "(" in rule and rule.endswith(")"):
        name, _, rest = rule.partition("(")
        return name, rest[:-1]
    return rule, None


def _is_full_match(specifier: str | None) -> bool:
    return specifier is None or specifier == "*"


def _expand_deny(rules: list[str], known_tools: set[str]) -> set[str]:
    result: set[str] = set()
    for rule in rules:
        name, specifier = _split_rule(rule)
        if not _is_full_match(specifier):
            continue
        if "*" in name:
            result.update(t for t in known_tools if fnmatch.fnmatch(t, name))
        else:
            result.add(name)
    return result


def _expand_allow(rules: list[str], known_tools: set[str]) -> set[str]:
    result: set[str] = set()
    for rule in rules:
        name, specifier = _split_rule(rule)
        if not _is_full_match(specifier):
            continue
        if "*" in name:
            if _MCP_SERVER_WILDCARD_ALLOW.match(name):
                result.update(t for t in known_tools if fnmatch.fnmatch(t, name))
            # Any other tool-name-position glob in an allow rule is invalid
            # per Claude Code's own rules and grants nothing.
        else:
            result.add(name)
    return result


def parse_permissions(settings: dict, known_tools: set[str]) -> PermissionContext:
    permissions = settings.get("permissions", {})
    deny_rules = permissions.get("deny", [])
    allow_rules = permissions.get("allow", [])

    denied = _expand_deny(deny_rules, known_tools)
    allowed = _expand_allow(allow_rules, known_tools) - denied
    unmentioned = known_tools - allowed - denied

    return PermissionContext(
        allowed_tools=sorted(allowed),
        denied_tools=sorted(denied),
        unmentioned_tools=sorted(unmentioned),
        connected_mcp_tools=[],
        existing_agents=[],
        permission_mode=permissions.get("defaultMode", "default"),
    )


def scan_existing_agents(project_root: str | Path) -> list[SubagentSpec]:
    agents_dir = Path(project_root) / ".claude" / "agents"
    if not agents_dir.exists():
        return []

    agents = []
    for agent_file in sorted(agents_dir.glob("*.md")):
        try:
            agents.append(SubagentSpec.from_markdown(agent_file.read_text()))
        except ValueError:
            continue
    return agents


def read_mcp_server_configs(project_root: str | Path) -> dict:
    data = _load_json_or_empty(Path(project_root) / ".mcp.json")
    servers = data.get("mcpServers", {})

    # Object form: {"name": {config}}. Array form: [{"name": ..., config}].
    if isinstance(servers, list):
        normalized = {}
        for entry in servers:
            if isinstance(entry, dict) and "name" in entry:
                name = entry["name"]
                normalized[name] = {k: v for k, v in entry.items() if k != "name"}
        return normalized
    if isinstance(servers, dict):
        return servers
    return {}


def filter_approved_mcp_servers(project_root: str | Path, server_configs: dict) -> dict:
    """Returns only the MCP servers the user has explicitly approved for this
    project, read from the git-untracked .claude/settings.local.json.

    This gates the auto-spawn in build_permission_context: a freshly-cloned
    untrusted repo has no local settings approving its servers, so its
    .mcp.json commands are never executed. Approvals committed to
    .claude/settings.json are deliberately ignored — a malicious repo could
    ship that file, so it must not be able to self-approve. This mirrors
    Claude Code's own rule that committed approvals don't count in an
    untrusted folder.
    """
    local_settings = _load_json_or_empty(
        Path(project_root) / ".claude" / "settings.local.json"
    )
    disabled = set(local_settings.get("disabledMcpjsonServers", []))
    enabled = set(local_settings.get("enabledMcpjsonServers", []))
    enable_all = local_settings.get("enableAllProjectMcpServers", False) is True

    approved = {}
    for name, config in server_configs.items():
        if name in disabled:
            continue
        if enable_all or name in enabled:
            approved[name] = config
    return approved


async def _list_tools_for_server(name: str, config: dict, timeout: float) -> list[str]:
    server_params = StdioServerParameters(
        command=config["command"],
        args=config.get("args", []),
        env=config.get("env"),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return [f"mcp__{name}__{tool.name}" for tool in response.tools]


def discover_mcp_tools(server_configs: dict, timeout: float = 5.0) -> list[str]:
    if not _MCP_AVAILABLE:
        return []

    async def _discover_all() -> list[str]:
        tools: list[str] = []
        for name, config in server_configs.items():
            try:
                tools.extend(
                    await asyncio.wait_for(
                        _list_tools_for_server(name, config, timeout), timeout=timeout
                    )
                )
            except Exception:
                continue
        return tools

    return asyncio.run(_discover_all())


def build_permission_context(project_root: str | Path) -> PermissionContext:
    settings = read_settings(project_root)
    existing_agents = scan_existing_agents(project_root)
    server_configs = read_mcp_server_configs(project_root)
    approved_servers = filter_approved_mcp_servers(project_root, server_configs)
    connected_mcp_tools = discover_mcp_tools(approved_servers) if approved_servers else []

    known_tools = set(BUILTIN_TOOLS) | set(connected_mcp_tools)
    context = parse_permissions(settings, known_tools)
    context.existing_agents = existing_agents
    context.connected_mcp_tools = connected_mcp_tools
    return context
