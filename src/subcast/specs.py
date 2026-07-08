"""TaskSpec, SubagentSpec, and MatchVerdict dataclasses.

These are the core data contracts shared across the pipeline. SubagentSpec
in particular must round-trip cleanly to Claude Code's own agent frontmatter
schema: name and description are required, tools/model/permissionMode are
optional and omitted from the markdown when absent, and tools is written as
a comma-separated string rather than a YAML list to match how Claude Code
itself writes subagent files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_VALID_DECISIONS = {"reuse_exact", "reuse_with_modification", "generate_new"}

# Claude Code's own rule: agent names are lowercase letters, digits, and
# hyphens (no leading/trailing hyphen). Enforcing this also closes a path
# traversal hole, since `name` is used to build the output file path.
_AGENT_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# Permission modes ranked by how permissive they are. A generated agent must
# never set a mode more permissive than the project's own — otherwise a
# subagent could run with fewer prompts than the project ever authorized.
# dontAsk auto-denies unless pre-approved, so it is treated as restrictive
# (rank 0) rather than an escalation.
_PERMISSION_MODE_RANK = {
    "plan": 0,
    "dontAsk": 0,
    "default": 1,
    "manual": 1,  # alias for default
    "acceptEdits": 2,
    "auto": 3,
    "bypassPermissions": 4,
}


def is_valid_agent_name(name: str) -> bool:
    """True if `name` is a safe Claude Code agent name (lowercase, digits,
    hyphens, no path separators or traversal sequences)."""
    return bool(_AGENT_NAME_RE.match(name))


def is_permission_mode_allowed(candidate: str | None, project_mode: str) -> bool:
    """True if a generated agent may carry permission mode `candidate` in a
    project whose own mode is `project_mode`.

    None (inherit / unset) is always allowed. A known mode is allowed only if
    it is no more permissive than the project's mode. Unknown modes are
    rejected outright.
    """
    if candidate is None:
        return True
    if candidate not in _PERMISSION_MODE_RANK:
        return False
    project_rank = _PERMISSION_MODE_RANK.get(project_mode, 1)
    return _PERMISSION_MODE_RANK[candidate] <= project_rank


def _parse_flat_frontmatter(frontmatter_block: str) -> dict[str, str]:
    """Parses simple `key: value` frontmatter lines.

    Claude Code's own subagent frontmatter is always flat scalars, no
    nesting or lists, so a real YAML parser is unnecessary; this keeps the
    module stdlib-only so it can ship as a self-contained script with no
    installs required. str.partition splits on the first colon only, so a
    colon inside a value (e.g. a description containing "note: like this")
    is preserved correctly.
    """
    result: dict[str, str] = {}
    for line in frontmatter_block.strip().splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


@dataclass
class TaskSpec:
    raw_task: str
    inferred_domain: str
    inferred_capabilities_needed: list[str] = field(default_factory=list)


@dataclass
class SubagentSpec:
    name: str
    description: str
    system_prompt_body: str
    tools: list[str] | None = None
    model: str | None = None
    permission_mode: str | None = None
    capability_gap: str | None = None

    def to_markdown(self) -> str:
        frontmatter_lines = [f"name: {self.name}", f"description: {self.description}"]
        if self.tools:
            frontmatter_lines.append(f"tools: {', '.join(self.tools)}")
        if self.model:
            frontmatter_lines.append(f"model: {self.model}")
        if self.permission_mode:
            frontmatter_lines.append(f"permissionMode: {self.permission_mode}")

        frontmatter = "\n".join(frontmatter_lines)
        return f"---\n{frontmatter}\n---\n\n{self.system_prompt_body}\n"

    @classmethod
    def from_markdown(cls, markdown: str) -> "SubagentSpec":
        # Normalize CRLF so files saved with Windows line endings parse the
        # same as Unix ones.
        markdown = markdown.replace("\r\n", "\n")
        if not markdown.startswith("---\n"):
            raise ValueError("subagent markdown must start with a '---' frontmatter block")

        _, frontmatter_block, body = markdown.split("---", 2)
        parsed = _parse_flat_frontmatter(frontmatter_block)

        if "name" not in parsed or "description" not in parsed:
            raise ValueError("subagent frontmatter requires both 'name' and 'description'")

        tools_raw = parsed.get("tools")
        tools = [t.strip() for t in tools_raw.split(",")] if tools_raw else None

        return cls(
            name=parsed["name"],
            description=parsed["description"],
            system_prompt_body=body.strip(),
            tools=tools,
            model=parsed.get("model"),
            permission_mode=parsed.get("permissionMode"),
        )


@dataclass
class PermissionContext:
    allowed_tools: list[str]
    denied_tools: list[str]
    unmentioned_tools: list[str]
    connected_mcp_tools: list[str]
    existing_agents: list["SubagentSpec"]
    permission_mode: str


@dataclass
class MatchVerdict:
    decision: str
    confidence: float
    reasoning: str
    matched_agent_name: str | None = None
    modification_notes: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in _VALID_DECISIONS:
            raise ValueError(
                f"decision must be one of {sorted(_VALID_DECISIONS)}, got {self.decision!r}"
            )
