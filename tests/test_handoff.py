"""Tests for handoff resolution: verifying a written agent actually exists
and is valid before the calling Claude Code session hands off to it via
its own Agent tool.
"""

import pytest

from subcast.handoff import resolve_handoff
from subcast.specs import SubagentSpec
from subcast.writer import write_subagent

SPEC = SubagentSpec(
    name="test-writer",
    description="Writes unit tests for Python modules",
    tools=["Read", "Write"],
    system_prompt_body="You write tests.",
)


def test_resolve_handoff_returns_name_for_valid_written_agent(tmp_path):
    write_subagent(SPEC, tmp_path)

    assert resolve_handoff("test-writer", tmp_path) == "test-writer"


def test_resolve_handoff_raises_when_agent_file_missing(tmp_path):
    with pytest.raises(ValueError):
        resolve_handoff("does-not-exist", tmp_path)


def test_resolve_handoff_raises_when_agent_file_is_malformed(tmp_path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "broken.md").write_text("---\ndescription: missing a name\n---\n\nBody.\n")

    with pytest.raises(ValueError):
        resolve_handoff("broken", tmp_path)
