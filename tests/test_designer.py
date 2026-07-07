"""Tests for the designer: prompt building and SubagentSpec validation.

Like the matcher, the design judgment itself is made by the Claude Code
session that invokes /spawn-agent. designer.py builds the prompt (task plus
only the allowed and unmentioned tools, denied tools are structurally
excluded) and runs the hard validation pass on the parsed response: every
tool name must appear in allowed_tools or unmentioned_tools, or the
generation is rejected outright rather than silently trimmed.
"""

import pytest

from subcast.designer import build_design_prompt, parse_designed_subagent
from subcast.specs import PermissionContext, TaskSpec

TASK = TaskSpec(
    raw_task="write unit tests for the parser module",
    inferred_domain="testing",
    inferred_capabilities_needed=["read files", "run test suite"],
)

CONTEXT = PermissionContext(
    allowed_tools=["Read"],
    denied_tools=["Bash"],
    unmentioned_tools=["Write", "Glob"],
    connected_mcp_tools=[],
    existing_agents=[],
    permission_mode="default",
)


def test_build_design_prompt_includes_task_details():
    prompt = build_design_prompt(TASK, CONTEXT)

    assert TASK.raw_task in prompt
    assert TASK.inferred_domain in prompt


def test_build_design_prompt_lists_only_allowed_and_unmentioned_tools():
    prompt = build_design_prompt(TASK, CONTEXT)

    assert "Read" in prompt
    assert "Write" in prompt
    assert "Glob" in prompt
    assert "Bash" not in prompt


def test_build_design_prompt_instructs_against_fabricating_tools():
    prompt = build_design_prompt(TASK, CONTEXT)

    assert "capability_gap" in prompt


def test_parse_designed_subagent_parses_well_formed_json():
    response = """{
        "name": "test-writer",
        "description": "Writes unit tests for Python modules",
        "tools": ["Read", "Write"],
        "model": "sonnet",
        "system_prompt_body": "You write tests."
    }"""

    spec = parse_designed_subagent(response, CONTEXT)

    assert spec.name == "test-writer"
    assert spec.tools == ["Read", "Write"]
    assert spec.model == "sonnet"


def test_parse_designed_subagent_handles_markdown_fence():
    response = """```json
{
    "name": "test-writer",
    "description": "Writes unit tests for Python modules",
    "tools": ["Read"],
    "system_prompt_body": "You write tests."
}
```"""

    spec = parse_designed_subagent(response, CONTEXT)

    assert spec.name == "test-writer"


def test_parse_designed_subagent_raises_on_denied_tool():
    response = """{
        "name": "test-writer",
        "description": "Writes unit tests for Python modules",
        "tools": ["Read", "Bash"],
        "system_prompt_body": "You write tests."
    }"""

    with pytest.raises(ValueError):
        parse_designed_subagent(response, CONTEXT)


def test_parse_designed_subagent_raises_on_fabricated_unknown_tool():
    response = """{
        "name": "test-writer",
        "description": "Writes unit tests for Python modules",
        "tools": ["Read", "NotARealTool"],
        "system_prompt_body": "You write tests."
    }"""

    with pytest.raises(ValueError):
        parse_designed_subagent(response, CONTEXT)


def test_parse_designed_subagent_accepts_tools_from_allowed_and_unmentioned():
    response = """{
        "name": "test-writer",
        "description": "Writes unit tests for Python modules",
        "tools": ["Read", "Write", "Glob"],
        "system_prompt_body": "You write tests."
    }"""

    spec = parse_designed_subagent(response, CONTEXT)

    assert spec.tools == ["Read", "Write", "Glob"]


def test_parse_designed_subagent_passes_through_capability_gap():
    response = """{
        "name": "test-writer",
        "description": "Writes unit tests for Python modules",
        "tools": ["Read"],
        "system_prompt_body": "You write tests.",
        "capability_gap": "Needs a coverage-reporting tool that doesn't exist."
    }"""

    spec = parse_designed_subagent(response, CONTEXT)

    assert spec.capability_gap == "Needs a coverage-reporting tool that doesn't exist."


def test_parse_designed_subagent_raises_on_missing_required_fields():
    response = '{"tools": ["Read"]}'

    with pytest.raises(ValueError):
        parse_designed_subagent(response, CONTEXT)


def test_parse_designed_subagent_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_designed_subagent("not json", CONTEXT)
