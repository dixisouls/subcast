"""Tests for the matcher: prompt building and MatchVerdict parsing.

The reuse/generate judgment itself is made by the Claude Code session
that invokes /spawn-agent, not by a Python-side API call. matcher.py's
job is to build that prompt and to parse and validate whatever
structured JSON response comes back.
"""

import pytest

from subcast.matcher import build_match_prompt, parse_match_verdict
from subcast.specs import SubagentSpec, TaskSpec

TASK = TaskSpec(
    raw_task="write unit tests for the parser module",
    inferred_domain="testing",
    inferred_capabilities_needed=["read files", "run test suite"],
)

EXISTING_AGENTS = [
    SubagentSpec(
        name="test-writer",
        description="Writes unit and integration tests for Python modules",
        tools=["Read", "Write", "Bash"],
        system_prompt_body="You write tests.",
    ),
    SubagentSpec(
        name="doc-writer",
        description="Writes and updates project documentation",
        system_prompt_body="You write docs.",
    ),
]


def test_build_match_prompt_includes_task_details():
    prompt = build_match_prompt(TASK, EXISTING_AGENTS)

    assert TASK.raw_task in prompt
    assert TASK.inferred_domain in prompt


def test_build_match_prompt_includes_each_existing_agent_name_and_description():
    prompt = build_match_prompt(TASK, EXISTING_AGENTS)

    for agent in EXISTING_AGENTS:
        assert agent.name in prompt
        assert agent.description in prompt


def test_build_match_prompt_notes_when_no_existing_agents():
    prompt = build_match_prompt(TASK, [])

    assert "no existing" in prompt.lower()


def test_parse_match_verdict_parses_well_formed_json():
    response = """{
        "decision": "reuse_with_modification",
        "matched_agent_name": "test-writer",
        "confidence": 0.85,
        "reasoning": "Existing agent covers testing, just needs Grep added.",
        "modification_notes": "Add Grep to the tool list."
    }"""

    verdict = parse_match_verdict(response)

    assert verdict.decision == "reuse_with_modification"
    assert verdict.matched_agent_name == "test-writer"
    assert verdict.confidence == 0.85
    assert verdict.modification_notes == "Add Grep to the tool list."


def test_parse_match_verdict_handles_json_wrapped_in_markdown_fence():
    response = """Here is my judgment:
```json
{
    "decision": "generate_new",
    "matched_agent_name": null,
    "confidence": 0.9,
    "reasoning": "No existing agent covers this domain."
}
```
"""

    verdict = parse_match_verdict(response)

    assert verdict.decision == "generate_new"
    assert verdict.matched_agent_name is None


def test_parse_match_verdict_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_match_verdict("this is not json at all")


def test_parse_match_verdict_raises_on_missing_required_field():
    response = '{"decision": "generate_new", "confidence": 0.9}'

    with pytest.raises(ValueError):
        parse_match_verdict(response)


def test_parse_match_verdict_raises_on_invalid_decision_value():
    response = (
        '{"decision": "maybe_reuse", "confidence": 0.5, "reasoning": "unsure"}'
    )

    with pytest.raises(ValueError):
        parse_match_verdict(response)


def test_parse_match_verdict_raises_when_reuse_decision_missing_matched_agent_name():
    response = (
        '{"decision": "reuse_exact", "confidence": 0.9, '
        '"reasoning": "Good match.", "matched_agent_name": null}'
    )

    with pytest.raises(ValueError):
        parse_match_verdict(response)


def test_parse_match_verdict_raises_when_generate_new_has_modification_notes():
    response = (
        '{"decision": "generate_new", "confidence": 0.9, "reasoning": "No match.", '
        '"matched_agent_name": null, "modification_notes": "should not be here"}'
    )

    with pytest.raises(ValueError):
        parse_match_verdict(response)
