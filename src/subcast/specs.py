"""TaskSpec, SubagentSpec, and MatchVerdict dataclasses.

These are the core data contracts shared across the pipeline. SubagentSpec
in particular must round-trip cleanly to Claude Code's own agent frontmatter
schema: name and description are required, tools/model/permissionMode are
optional and omitted from the markdown when absent, and tools is written as
a comma-separated string rather than a YAML list to match how Claude Code
itself writes subagent files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

_VALID_DECISIONS = {"reuse_exact", "reuse_with_modification", "generate_new"}


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
        if not markdown.startswith("---\n"):
            raise ValueError("subagent markdown must start with a '---' frontmatter block")

        _, frontmatter_block, body = markdown.split("---", 2)
        parsed = yaml.safe_load(frontmatter_block) or {}

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
