# Architecture

SubCast is a Claude Code plugin that dynamically matches or generates
project-scoped subagents on demand. This document explains the pipeline,
why matching/designing happens where it does, and how the pieces fit
together.

## The core insight: the reasoning happens in the calling session

SubCast is invoked as `/subcast:spawn-agent "task description"` from
*inside* an active Claude Code session. That session is already an LLM
with the task in its own context — there is no need for a second,
separately-authenticated LLM call to judge reuse-vs-generate or to design a
new subagent's prompt.

This is why `matcher.py` and `designer.py` don't call the Anthropic API and
don't need `ANTHROPIC_API_KEY`. Each exposes two kinds of function:

- A **prompt-builder** (`build_match_prompt`, `build_design_prompt`) — a
  tested reference implementation of what the prompt *would* look like, if
  this pipeline ever needed to run outside a Claude Code session. These are
  not wired into the live pipeline; the calling session's own instructions
  (in `commands/spawn-agent.md`) serve the same purpose without a redundant
  round trip.
- A **parser/validator** (`parse_match_verdict`, `parse_designed_subagent`)
  — these *are* wired in. The calling session reasons inline and produces
  structured JSON; these functions parse that JSON and enforce the
  project's correctness rules (valid decision values, no denied/fabricated
  tool names) before anything gets written to disk.

The same principle applies to `approval.py` and `handoff.py`: neither can
pause for user confirmation or invoke Claude Code's own `Agent` tool —
only the calling session can do either of those. `approval.py` is a pure
decision function (`requires_approval(permission_mode) -> bool`) that the
session acts on; `handoff.py` verifies the target agent file is valid
before the session attempts to hand off to it.

## The pipeline

```
/subcast:spawn-agent "task"
        │
        ▼
1. subcast-spawn-agent context          (permission_reader.py)
   → PermissionContext as JSON: allowed/denied/unmentioned tools,
     connected MCP tools, existing agents, permission mode
        │
        ▼
2. Calling session reasons: reuse_exact / reuse_with_modification
   / generate_new                       (matcher.py validates the verdict)
        │
        ├─ reuse_exact ──────────────────────────────┐
        │                                             │
        ▼ reuse_with_modification / generate_new      │
3. Calling session designs the subagent,               │
   tools drawn only from allowed ∪ unmentioned          │
   (designer.py validates: rejects denied/              │
   unknown tool names outright)                         │
        │                                             │
        ▼                                             │
4. subcast-spawn-agent requires-approval               │
   (approval.py: pure permission_mode decision)        │
        │                                             │
        ▼                                             │
5. subcast-spawn-agent write             (writer.py)   │
   → .claude/agents/<name>.md, collision-checked        │
   by parsed `name` field, not filename                 │
        │                                             │
        ▼                                             │
6. subcast-spawn-agent resolve-handoff   (handoff.py)  │
   → verifies the file exists and parses back valid    │
        │                                             │
        └─────────────────────────┬───────────────────┘
                                   ▼
                    7. Agent(<agent-name>) — actually
                       executes the task
```

## Matcher vs. designer, and why "reuse with modification" exists

The build spec's own framing: reuse-vs-generate is a judgment call, not a
string or embedding similarity search — an existing agent's *description*
is compared against the task by the calling session's own reasoning
(`commands/spawn-agent.md` step 2 gives explicit criteria and worked
examples for this).

A strict reuse-or-generate binary undercounts a real, common case: an
existing agent covers the right domain but needs a small adjustment (one
more tool, a new case added to its process) for this specific task.
Without a third option, the pipeline would either force an exact-fit
fiction (reuse an agent that's a poor match) or duplicate work
(generate a near-clone of an agent that already exists). `reuse_with_modification`
lets the designer step revise an existing agent's `tools` or
`system_prompt_body` in place (`write --overwrite`) instead.

## The tool-naming rule, structurally enforced

See [`PERMISSION_MODEL.md`](./PERMISSION_MODEL.md) for the full permission
model. The short version: the prompt only ever shows the calling session
`allowed_tools` and `unmentioned_tools` as valid options — `denied_tools`
never appears in the prompt at all, so a denied tool is structurally
impossible to select, not just discouraged. `designer.py`'s
`parse_designed_subagent` runs a second, independent check after the fact:
every tool name in the parsed `SubagentSpec` must appear in
`allowed_tools ∪ unmentioned_tools`, or the whole generation is rejected
with the offending names listed — never silently dropped.

## Distribution: a self-contained plugin

SubCast ships as a Claude Code plugin (`.claude-plugin/plugin.json`), with
`bin/subcast-spawn-agent` — a script Claude Code adds to the Bash tool's
`PATH` automatically while the plugin is enabled. The core CLI has zero
required third-party dependencies (stdlib only); `mcp` is an optional soft
dependency that only affects live MCP tool discovery in
`permission_reader.py` (see the docstring there for the full-match-vs-scoped
distinction this module implements for both built-in and MCP tools).

`.claude-plugin/marketplace.json` self-hosts a single-plugin marketplace in
the same repository, so installation is:

```
/plugin marketplace add dixisouls/subcast
/plugin install subcast@subcast
```

No separate marketplace repo, no PyPI publish, no pip/pipx step for the end
user at all.

## A known platform limitation, and why the fallback exists

Claude Code's `Agent` tool cannot invoke a subagent written during the
*same* session it was written in — confirmed by direct, repeated testing
(including retrying minutes later, with many intervening tool calls, in a
session where `.claude/agents/` had existed the whole time). This is not a
SubCast bug; it is tracked in multiple open upstream
`anthropics/claude-code` issues, and no hot-reload mechanism currently
exists. `commands/spawn-agent.md` step 7 falls back to executing the task
directly (or via `general-purpose`) using the exact same instructions the
written subagent would have used, and tells the user the new agent becomes
usable via `Agent(<name>)` from their next session (or `claude --resume`)
onward.
