"""Entry point wired to the /spawn-agent slash command.

Reads a task description, runs it through the permission reader, matcher,
designer, approval gate, and writer, then hands off to Claude Code's Agent
tool via subcast.handoff.
"""
