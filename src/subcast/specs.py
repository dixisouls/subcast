"""TaskSpec, SubagentSpec, MatchVerdict, and PermissionContext dataclasses.

These are the core data contracts shared across the pipeline. SubagentSpec
in particular must round-trip cleanly to Claude Code's own agent frontmatter
schema.
"""
