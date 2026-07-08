"""Serializes a SubagentSpec to valid Claude Code frontmatter markdown and
writes it to .claude/agents/, checking for name collisions first.

Identity comes only from the `name` frontmatter field, not the filename
(Claude Code itself allows the filename to differ from `name`), so the
collision check scans every existing agent's parsed name rather than just
checking whether `<name>.md` already exists.
"""

from __future__ import annotations

from pathlib import Path

from subcast.permission_reader import scan_existing_agents
from subcast.specs import SubagentSpec, is_valid_agent_name


def write_subagent(
    spec: SubagentSpec, project_root: str | Path, overwrite: bool = False
) -> Path:
    project_root = Path(project_root)
    agents_dir = project_root / ".claude" / "agents"

    # Security boundary: `spec.name` may originate from LLM output. Reject any
    # name that isn't a plain Claude Code agent name before it can be used to
    # build a file path (path traversal), and assert containment as defense in
    # depth.
    if not is_valid_agent_name(spec.name):
        raise ValueError(
            f"refusing to write agent with invalid name {spec.name!r}: must be "
            "lowercase letters, digits, and hyphens only"
        )

    if not overwrite:
        existing_names = {agent.name for agent in scan_existing_agents(project_root)}
        if spec.name in existing_names:
            raise ValueError(
                f"a subagent named {spec.name!r} already exists in .claude/agents/"
            )

    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{spec.name}.md"

    # Defense in depth: even though the name is validated above, confirm the
    # resolved path stays inside the agents directory before writing.
    resolved_dir = agents_dir.resolve()
    if not path.resolve().parent == resolved_dir:
        raise ValueError(
            f"refusing to write outside {resolved_dir} (resolved to {path.resolve()})"
        )

    path.write_text(spec.to_markdown())
    return path
