"""Schema validation tests for TaskSpec, SubagentSpec, and MatchVerdict.

SubagentSpec's markdown round-trip is the highest-risk contract in the
project: a malformed SubagentSpec produces a subagent file Claude Code
silently fails to load correctly.
"""

import pytest

from subcast.specs import MatchVerdict, SubagentSpec, TaskSpec


def test_task_spec_holds_raw_task_and_inferred_fields():
    spec = TaskSpec(
        raw_task="write unit tests for the parser",
        inferred_domain="testing",
        inferred_capabilities_needed=["read files", "run test suite"],
    )

    assert spec.raw_task == "write unit tests for the parser"
    assert spec.inferred_domain == "testing"
    assert spec.inferred_capabilities_needed == ["read files", "run test suite"]


def test_subagent_spec_round_trip_preserves_all_fields():
    original = SubagentSpec(
        name="code-reviewer",
        description="Reviews code for quality and best practices",
        tools=["Read", "Glob", "Grep"],
        model="sonnet",
        permission_mode="acceptEdits",
        system_prompt_body=(
            "You are a code reviewer. When invoked, analyze the code and "
            "provide specific, actionable feedback."
        ),
    )

    markdown = original.to_markdown()
    parsed = SubagentSpec.from_markdown(markdown)

    assert parsed == original


def test_subagent_spec_to_markdown_uses_comma_separated_tools_field():
    spec = SubagentSpec(
        name="code-reviewer",
        description="Reviews code for quality and best practices",
        tools=["Read", "Glob", "Grep"],
        model="sonnet",
        system_prompt_body="You are a code reviewer.",
    )

    markdown = spec.to_markdown()

    assert markdown == (
        "---\n"
        "name: code-reviewer\n"
        "description: Reviews code for quality and best practices\n"
        "tools: Read, Glob, Grep\n"
        "model: sonnet\n"
        "---\n"
        "\n"
        "You are a code reviewer.\n"
    )


def test_subagent_spec_to_markdown_omits_absent_optional_fields():
    spec = SubagentSpec(
        name="minimal-agent",
        description="Does the bare minimum",
        system_prompt_body="You do the bare minimum.",
    )

    markdown = spec.to_markdown()

    assert "tools:" not in markdown
    assert "model:" not in markdown
    assert "permissionMode:" not in markdown
    assert markdown == (
        "---\n"
        "name: minimal-agent\n"
        "description: Does the bare minimum\n"
        "---\n"
        "\n"
        "You do the bare minimum.\n"
    )


def test_subagent_spec_from_markdown_parses_real_claude_code_agent_file():
    real_agent_markdown = (
        "---\n"
        "name: vscode-test-writer\n"
        "description: Use this agent when the user needs to write tests.\n"
        "tools: Bash, Glob, Grep, Read, Edit, Write\n"
        "model: opus\n"
        "color: blue\n"
        "---\n"
        "\n"
        "You are an elite VS Code extension test engineer.\n"
    )

    parsed = SubagentSpec.from_markdown(real_agent_markdown)

    assert parsed.name == "vscode-test-writer"
    assert parsed.description == "Use this agent when the user needs to write tests."
    assert parsed.tools == ["Bash", "Glob", "Grep", "Read", "Edit", "Write"]
    assert parsed.model == "opus"
    assert parsed.system_prompt_body == "You are an elite VS Code extension test engineer."


def test_subagent_spec_from_markdown_requires_name_and_description():
    missing_name = "---\ndescription: no name here\n---\n\nBody.\n"

    with pytest.raises(ValueError):
        SubagentSpec.from_markdown(missing_name)


def test_match_verdict_holds_decision_and_reasoning():
    verdict = MatchVerdict(
        decision="reuse_with_modification",
        matched_agent_name="code-reviewer",
        confidence=0.82,
        reasoning="Existing agent covers this domain with a tweak to tools.",
        modification_notes="Add Bash to the tool list.",
    )

    assert verdict.decision == "reuse_with_modification"
    assert verdict.matched_agent_name == "code-reviewer"
    assert verdict.confidence == 0.82
    assert verdict.modification_notes == "Add Bash to the tool list."


def test_match_verdict_rejects_unknown_decision_value():
    with pytest.raises(ValueError):
        MatchVerdict(
            decision="not_a_real_decision",
            matched_agent_name=None,
            confidence=0.5,
            reasoning="bogus",
        )
