"""LLM call that designs a new SubagentSpec from a TaskSpec and
PermissionContext when no existing agent is a good enough match.

Enforces the tool naming rule: only allowed and unmentioned tools are ever
shown to the LLM as options, denied tools are structurally excluded.
"""
