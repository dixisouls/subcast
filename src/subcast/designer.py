"""Builds the subagent design prompt and validates the resulting
SubagentSpec.

Like the matcher, the design judgment is made by the Claude Code session
that invokes /spawn-agent, not by a Python-side API call. This module builds
the prompt, given only the allowed and unmentioned tools as valid options
(denied tools are structurally excluded, never shown at all), and runs the
hard validation pass on the parsed response: every tool name must appear in
allowed_tools or unmentioned_tools, or the generation is rejected outright.
Never silently drop an invalid tool and proceed, since that could produce an
agent with fewer capabilities than intended without anyone noticing.
"""

from __future__ import annotations

import json
import re

from subcast.specs import (
    PermissionContext,
    SubagentSpec,
    TaskSpec,
    is_permission_mode_allowed,
    is_valid_agent_name,
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def build_design_prompt(task: TaskSpec, context: PermissionContext) -> str:
    valid_tools = sorted(set(context.allowed_tools) | set(context.unmentioned_tools))

    return (
        "Design a new subagent for this task. Only use tools from the valid "
        "tools list below; if the task needs a capability no listed tool "
        "covers, document it in capability_gap instead of inventing a tool "
        "name that doesn't exist.\n\n"
        f"Task: {task.raw_task}\n"
        f"Inferred domain: {task.inferred_domain}\n"
        f"Inferred capabilities needed: {', '.join(task.inferred_capabilities_needed)}\n\n"
        f"Valid tools: {', '.join(valid_tools)}\n\n"
        "Respond with JSON only, matching this shape:\n"
        "{\n"
        '  "name": string, lowercase letters and hyphens only,\n'
        '  "description": string, when Claude should delegate to this agent,\n'
        '  "tools": list of strings, drawn only from the valid tools list,\n'
        '  "model": "sonnet" | "opus" | "haiku" | "fable" | "inherit" | null,\n'
        '  "permission_mode": string or null,\n'
        '  "system_prompt_body": string, the agent\'s system prompt,\n'
        '  "capability_gap": string or null, populated only if a needed '
        "capability has no matching tool\n"
        "}"
    )


def parse_designed_subagent(response_text: str, context: PermissionContext) -> SubagentSpec:
    fence_match = _JSON_FENCE_RE.search(response_text)
    json_text = fence_match.group(1) if fence_match else response_text

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"designer response was not valid JSON: {exc}") from exc

    required_fields = {"name", "description", "system_prompt_body"}
    missing = required_fields - payload.keys()
    if missing:
        raise ValueError(f"designer response missing required fields: {sorted(missing)}")

    name = payload["name"]
    if not is_valid_agent_name(name):
        raise ValueError(
            f"invalid agent name {name!r}: must be lowercase letters, digits, and "
            "hyphens only (no path separators or traversal sequences)"
        )

    permission_mode = payload.get("permission_mode")
    if not is_permission_mode_allowed(permission_mode, context.permission_mode):
        raise ValueError(
            f"permission_mode {permission_mode!r} is not allowed: it is either "
            f"unknown or more permissive than the project's own mode "
            f"({context.permission_mode!r}). A generated agent may not escalate "
            "beyond the project's permission posture."
        )

    tools = payload.get("tools") or []
    valid_tools = set(context.allowed_tools) | set(context.unmentioned_tools)
    invalid_tools = [t for t in tools if t not in valid_tools]
    if invalid_tools:
        raise ValueError(
            f"designer response used denied or unknown tools: {invalid_tools}"
        )

    return SubagentSpec(
        name=name,
        description=payload["description"],
        system_prompt_body=payload["system_prompt_body"],
        tools=tools or None,
        model=payload.get("model"),
        permission_mode=permission_mode,
        capability_gap=payload.get("capability_gap"),
    )
