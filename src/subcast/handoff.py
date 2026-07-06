"""Resolves the agent to hand off to, either reused or newly written.

Only the calling Claude Code session can actually invoke its own Agent
tool, Python can't call it. This module verifies the resolved agent file
exists and is valid before the calling session hands off to it, catching a
broken write before an Agent(name) call would fail confusingly.
"""

from __future__ import annotations

from pathlib import Path

from subcast.specs import SubagentSpec


def resolve_handoff(agent_name: str, project_root: str | Path) -> str:
    agent_path = Path(project_root) / ".claude" / "agents" / f"{agent_name}.md"

    if not agent_path.exists():
        raise ValueError(f"no agent file found at {agent_path}")

    try:
        SubagentSpec.from_markdown(agent_path.read_text())
    except ValueError as exc:
        raise ValueError(f"agent file at {agent_path} is malformed: {exc}") from exc

    return agent_name
