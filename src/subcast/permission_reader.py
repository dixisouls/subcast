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

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from subcast.specs import PermissionContext, SubagentSpec

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


def read_settings(project_root: str | Path) -> dict:
    settings_path = Path(project_root) / ".claude" / "settings.json"
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text())


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
    mcp_json_path = Path(project_root) / ".mcp.json"
    if not mcp_json_path.exists():
        return {}
    return json.loads(mcp_json_path.read_text()).get("mcpServers", {})


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
    connected_mcp_tools = discover_mcp_tools(server_configs) if server_configs else []

    known_tools = set(BUILTIN_TOOLS) | set(connected_mcp_tools)
    context = parse_permissions(settings, known_tools)
    context.existing_agents = existing_agents
    context.connected_mcp_tools = connected_mcp_tools
    return context
