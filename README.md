# SubCast

**Subagent casting** — dynamic, on-demand subagent generation for Claude Code.

## What it is

SubCast is a Claude Code plugin. Given a task via `/subcast:spawn-agent
"task description"`, it:

1. Checks the current project's existing subagents (`.claude/agents/`) for
   a good enough match.
2. If none exists, designs a new subagent scoped strictly within the
   project's existing permission boundaries.
3. Shows the generated agent for approval if the project's permission mode
   calls for that.
4. Writes the approved agent to `.claude/agents/`.
5. Hands off execution to Claude Code's native `Agent` tool.

The differentiator from the many existing "prewritten agent library"
projects: nothing here is pre-authored. SubCast decides what specialist is
needed at the moment of need, and reuses or extends what already exists in
the project rather than duplicating it. See
[`docs/DEMO.md`](./docs/DEMO.md) for a real, unedited before-and-after run.

## Install

```
/plugin marketplace add dixisouls/subcast
/plugin install subcast@subcast
```

No pip, no pipx, no separate CLI install — the plugin's `bin/` script is
added to the Bash tool's `PATH` automatically while it's enabled. To try it
without installing, point Claude Code at a local checkout instead:

```
claude --plugin-dir /path/to/subcast
```

## Core behavior

- Invocation is explicit and user-triggered (`disable-model-invocation:
  true`) — Claude never runs this on its own judgment.
- The reuse-vs-generate judgment and the subagent design itself are made by
  the *calling* Claude Code session's own reasoning, not a separate,
  separately-authenticated LLM call. No `ANTHROPIC_API_KEY` is needed for
  any of this — see [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
- **Tool-naming rule:** a denied tool is never even shown as an option to
  the calling session, and a second, independent validation pass rejects
  any generated agent that uses a denied or unknown tool name outright. See
  [`docs/PERMISSION_MODEL.md`](./docs/PERMISSION_MODEL.md) for the full
  allowed/denied/unmentioned model, including the full-match-vs-scoped
  distinction that keeps this from being overly conservative.
- If a task needs a capability with no matching tool, SubCast reports a
  capability gap rather than inventing a tool name that doesn't exist.
- A third option, `reuse_with_modification`, lets SubCast lightly adjust an
  existing agent's tools or prompt for the task at hand, instead of a
  strict reuse-or-generate binary.
- Reuse candidates are scoped to the current project's `.claude/agents/`
  only; user-scope `~/.claude/agents/` is out of scope.
- Approval before a newly generated agent's first run inherits Claude
  Code's own permission mode directly rather than introducing a separate
  setting.
- Generated agents follow a structured recipe (role, responsibilities,
  numbered process, output expectations, quality standards,
  self-verification), not generic one-liners — see
  [`commands/subagent-design-guide.md`](./commands/subagent-design-guide.md).

## Status

Feature-complete through the full pipeline, packaged and installable as a
real Claude Code plugin, verified end to end against real scratch projects.
See [`build-spec.md`](./build-spec.md) (local, not committed to this repo)
for the full build history if you have it, or the git log for the actual
history.

## Repository structure

```
subcast/
├── .claude-plugin/
│   ├── plugin.json        # plugin manifest
│   └── marketplace.json   # self-hosted single-plugin marketplace
├── bin/
│   └── subcast-spawn-agent  # self-contained entry point, added to PATH while the plugin is enabled
├── commands/
│   ├── spawn-agent.md              # the /subcast:spawn-agent command
│   └── subagent-design-guide.md    # recipe for generated agents' system prompts
├── src/
│   ├── subcast/            # specs, permission reader, matcher, designer, writer, approval, handoff
│   └── cli/                # CLI entry point bin/ delegates to
├── tests/
└── docs/                   # ARCHITECTURE.md, PERMISSION_MODEL.md, DEMO.md
```

## Requirements

SubCast runs inside a project already using [Claude
Code](https://claude.com/product/claude-code), and reads that project's
`.claude/settings.json` and `.claude/agents/` conventions directly. It is
an independent, unaffiliated project built to work with Claude Code's
existing extension points — it is not endorsed by or affiliated with
Anthropic.

## License

MIT — see [LICENSE](./LICENSE).
