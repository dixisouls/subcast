"""Builds the reuse-vs-generate match prompt and parses the resulting
MatchVerdict.

The judgment itself is made by the Claude Code session that invokes
/spawn-agent, since that session is already an LLM with the task in its own
context. This module only builds the prompt (task description plus every
existing project-scoped subagent's description field) and parses/validates
the structured JSON response into a MatchVerdict; it never calls an LLM API
directly.
"""

from __future__ import annotations

import json
import re

from subcast.specs import MatchVerdict, SubagentSpec, TaskSpec

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def build_match_prompt(task: TaskSpec, existing_agents: list[SubagentSpec]) -> str:
    if existing_agents:
        agents_section = "\n".join(
            f"- {agent.name}: {agent.description}" for agent in existing_agents
        )
    else:
        agents_section = "There are no existing project-scoped subagents."

    return (
        "Decide whether an existing subagent is a good enough match for this "
        "task, or whether a new one should be generated.\n\n"
        f"Task: {task.raw_task}\n"
        f"Inferred domain: {task.inferred_domain}\n"
        f"Inferred capabilities needed: {', '.join(task.inferred_capabilities_needed)}\n\n"
        "Existing project-scoped subagents:\n"
        f"{agents_section}\n\n"
        "Respond with JSON only, matching this shape:\n"
        "{\n"
        '  "decision": "reuse_exact" | "reuse_with_modification" | "generate_new",\n'
        '  "matched_agent_name": string or null, required unless decision is generate_new,\n'
        '  "confidence": number between 0 and 1,\n'
        '  "reasoning": string,\n'
        '  "modification_notes": string or null, only set when decision is '
        "reuse_with_modification\n"
        "}"
    )


def parse_match_verdict(response_text: str) -> MatchVerdict:
    fence_match = _JSON_FENCE_RE.search(response_text)
    json_text = fence_match.group(1) if fence_match else response_text

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"matcher response was not valid JSON: {exc}") from exc

    required_fields = {"decision", "confidence", "reasoning"}
    missing = required_fields - payload.keys()
    if missing:
        raise ValueError(f"matcher response missing required fields: {sorted(missing)}")

    decision = payload["decision"]
    matched_agent_name = payload.get("matched_agent_name")
    modification_notes = payload.get("modification_notes")

    if decision != "generate_new" and not matched_agent_name:
        raise ValueError(f"decision {decision!r} requires a matched_agent_name")

    if decision != "reuse_with_modification" and modification_notes:
        raise ValueError(
            "modification_notes may only be set when decision is "
            "reuse_with_modification"
        )

    return MatchVerdict(
        decision=decision,
        confidence=payload["confidence"],
        reasoning=payload["reasoning"],
        matched_agent_name=matched_agent_name,
        modification_notes=modification_notes,
    )
