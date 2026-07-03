# SubCast

**Subagent casting** — dynamic, on-demand subagent generation for Claude Code.

## What it is

SubCast is a slash command backed by a standalone Claude Agent SDK program. Given a task, it:

1. Checks the current project's existing Claude Code subagents (`.claude/agents/`) for a good enough match.
2. If none exists, designs a new subagent scoped strictly within the project's existing permission boundaries.
3. Shows the generated agent for approval if the project's `permissionMode` calls for that.
4. Writes the approved agent to `.claude/agents/`.
5. Hands off execution to Claude Code's native Agent tool.

The differentiator from the many existing "prewritten agent library" projects: nothing here is pre-authored. SubCast decides what specialist is needed at the moment of need, and reuses or extends what already exists in the project rather than duplicating it.

## Core behavior

- Invocation is explicit: `/spawn-agent "task description"`. Not a hook, not an MCP server — the user triggers the meta-agent reasoning on purpose.
- **Tool naming rule:** SubCast never assigns a tool that appears in the project's `permissions.deny` list. Tools in `permissions.allow` are freely assignable. Unmentioned tools can still be assigned — Claude Code's own runtime will prompt on first use.
- If a task needs a capability with no matching built-in or MCP tool, SubCast reports a capability gap rather than inventing a tool name that doesn't exist.
- Reuse vs. generate is decided by an LLM call that reads the task plus every existing project-scoped subagent's description, not string or embedding similarity.
- A third option, reuse-with-modification, lets SubCast lightly adjust an existing agent's tools or prompt for the task at hand, instead of a strict reuse-or-generate binary.
- Reuse candidates are scoped to the current project's `.claude/agents/` only; user-scope `~/.claude/agents/` is out of scope.
- Approval before a newly generated agent's first run inherits Claude Code's own `permissionMode` directly rather than introducing a separate setting.

## Status

Early scaffolding. See [`build-spec.md`](./build-spec.md) for the full build specification, milestone plan (M0–M9), and core data contracts (`TaskSpec`, `SubagentSpec`, `MatchVerdict`, `PermissionContext`).

## Repository structure

```
subcast/
├── src/
│   ├── subcast/          # specs, permission reader, matcher, designer, writer, approval, handoff
│   └── cli/              # entry point wired to the /spawn-agent slash command
├── .claude/
│   └── commands/         # spawn-agent.md slash command definition
├── tests/
└── docs/                 # ARCHITECTURE.md, PERMISSION_MODEL.md, DEMO.md
```

## Requirements

SubCast is designed to run inside a project already using [Claude Code](https://claude.com/product/claude-code) as its CLI agent, and reads that project's `.claude/settings.json` and `.claude/agents/` conventions directly. It is an independent, unaffiliated project built to work with Claude Code's existing extension points — it is not endorsed by or affiliated with Anthropic.

## License

MIT — see [LICENSE](./LICENSE).
