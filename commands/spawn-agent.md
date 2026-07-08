---
description: Match an existing project subagent to a task, or design and write a new one, then hand off to it
argument-hint: [task description]
disable-model-invocation: true
allowed-tools: Bash(subcast-spawn-agent:*), Agent
---

Task: $ARGUMENTS

## Why this exists

SubCast's whole point is that nothing here is pre-authored. A project that
keeps spawning the same kind of specialist ends up with a `.claude/agents/`
folder that grows organically — one real agent per recurring need, reused
whenever it fits, revised when it's close, and only ever duplicated when
nothing existing actually covers the task. Getting the reuse-vs-generate
judgment right, and making generated agents genuinely good (not generic
one-liners), is the entire value of this pipeline. Follow every step below
in order.

## Step 1: Read the permission context

Run `subcast-spawn-agent context` from the project root. This prints the
current permission context as JSON: `allowed_tools`, `denied_tools`,
`unmentioned_tools`, `connected_mcp_tools`, `existing_agents` (each with
`name`, `description`, `tools`), and `permission_mode`.

## Step 2: Decide reuse or generate

Compare the task against each existing agent's `description` yourself,
using your own judgment — no tool call needed for this step. Decide one of:

- **`reuse_exact`** — an existing agent's description already covers this
  task as-is. The task is a normal instance of what that agent already
  does; nothing about tools or approach needs to change.
- **`reuse_with_modification`** — an existing agent covers the same general
  domain, but its tool list or system prompt needs a small, specific change
  for this task (e.g. it needs one more tool, or a new case added to its
  process).
- **`generate_new`** — nothing existing fits well enough that stretching it
  would be honest. A near-miss in domain is not the same as a fit; don't
  reuse just because something already exists.

**Worked examples:**

| Task | Existing agent description | Decision |
|---|---|---|
| "Write unit tests for `parser.py`" | `python-test-writer`: "Writes and runs pytest unit tests for Python modules" | `reuse_exact` |
| "Write unit tests for `parser.py`, and also check test coverage %" | `python-test-writer`: "Writes and runs pytest unit tests for Python modules" (tools: Read, Write, Edit, Bash) | `reuse_with_modification` — same domain, just needs `pytest-cov` usage added to its process, no new tools required |
| "Research competitor pricing pages" | `python-test-writer`: "Writes and runs pytest unit tests for Python modules" | `generate_new` — different domain entirely, no honest stretch applies |

Optionally validate the verdict is well-formed before proceeding by piping
it to stdin:

```
subcast-spawn-agent validate-verdict - <<'SUBCAST_EOF'
{"decision": ..., "matched_agent_name": ..., "confidence": ...,
 "reasoning": ..., "modification_notes": ...}
SUBCAST_EOF
```

If `reuse_exact`: skip straight to Step 6 using that agent's name.

## Step 3: The tool-naming rule

If you're designing a new agent or modifying an existing one (Step 4), its
`tools` list may only contain values from `allowed_tools` or
`unmentioned_tools` in Step 1's output — **never** from `denied_tools`, and
**never** a name that doesn't appear in either list.

**The temptation:** the task clearly needs some capability, but nothing in
the valid tools list obviously covers it. The tempting shortcut is to write
a tool name that sounds right anyway, or to reach for a name from a
different project you've seen before.

**Never invent a tool name that does not exist in the valid list.** This is
the project's core safety claim: a fabricated tool name produces a subagent
file Claude Code silently fails to load correctly, or one that requests a
capability it will never actually have. There is no exception to this.

| Rationalization | Reality |
|---|---|
| "This tool name is standard, it must exist" | It must appear in Step 1's `allowed_tools`/`unmentioned_tools` right now, in this project. Standard elsewhere doesn't make it valid here. |
| "The task obviously needs this, I'll just include it" | Obviously needing a capability doesn't create the tool. Use `capability_gap` instead. |
| "I'll use a close-enough existing tool name" | A close-enough *wrong* name is still wrong — the agent will request a capability it doesn't have under a name Claude Code doesn't recognize. |
| "Denied tools are basically the same as unmentioned, just stricter" | No — a denied tool must never appear in the list at all, full stop, regardless of how central it seems to the task. |

**Red flags — stop and use `capability_gap` instead:**
- You're about to type a tool name you don't see verbatim in Step 1's
  `allowed_tools` or `unmentioned_tools` arrays.
- You're reasoning "this probably exists" instead of checking the actual
  list.
- You're tempted to substitute a similar-sounding tool for one that isn't
  available.

If the task needs a capability nothing in the valid list covers, set
`capability_gap` to a short explanation and design the rest of the agent
without that capability, rather than inventing a tool name.

## Step 4: Design the subagent

If `reuse_with_modification` or `generate_new`: design the subagent
yourself. **Read `commands/subagent-design-guide.md` and follow its recipe**
before writing `system_prompt_body` — a subagent whose prompt is just "you
do X" is a failure of this step even if everything else about it is
correct. The guide has a worked example and a fill-in template.

## Step 5: Approval and write

Before writing, run `subcast-spawn-agent requires-approval`.
- If it prints `true`, show the user the full subagent definition you
  designed (name, description, tools, and the full `system_prompt_body`)
  and get explicit confirmation before continuing.
- If it prints `false`, continue directly.

Then write the agent by piping the JSON to `subcast-spawn-agent write` on
stdin (using `-` as the argument), which avoids shell-quoting problems with
the multi-line `system_prompt_body`:

```
subcast-spawn-agent write - <<'SUBCAST_EOF'
{"name": ..., "description": ..., "tools": [...], "model": ...,
 "permission_mode": ..., "system_prompt_body": ..., "capability_gap": ...}
SUBCAST_EOF
```

Notes on the fields:
- `permission_mode` may not be more permissive than the project's own mode
  from Step 1; leave it out (null) unless you have a specific reason.
- Add `--overwrite` (before the `-`) only when `reuse_with_modification` is
  updating an existing agent of the same name.
- If the command fails (a denied/unknown tool, an invalid name, or a
  permission-mode escalation), fix the offending field and retry — do not
  continue until it succeeds.
- If the command prints a `capability gap:` line on stderr, **relay that gap
  to the user** — it means the agent was written but couldn't fully cover
  the task with the available tools.

## Step 6: Resolve handoff

Run `subcast-spawn-agent resolve-handoff <agent-name>` to confirm the agent
file is valid and ready.

## Step 7: Hand off

Invoke `Agent(<agent-name>)` with the original task description to actually
execute it. If this agent was just written during this same session
(whether or not `.claude/agents/` already existed), Claude Code will not
recognize the new agent type yet — confirmed by testing, this holds
regardless of elapsed time within the session, not just immediately after
writing. This is a known Claude Code limitation, not a failure of this
pipeline.

If `Agent(<agent-name>)` errors with "Agent type not found", fall back to
`Agent(general-purpose)`, passing it the written subagent's own
`system_prompt_body` as its instructions verbatim, plus the task. From the
user's perspective this should read as `<agent-name>` doing the work, not
as a hidden implementation detail leaking through:

- Report progress and the final result **as `<agent-name>`** — e.g. "Using
  `python-test-writer`..." — never say "general-purpose" or "fallback" in
  what you tell the user.
- If you want to mention the mechanism at all, keep it to a brief aside
  once at the end (e.g. "this ran under the hood via a generic executor
  since Claude Code doesn't recognize brand-new agents mid-session — it'll
  be available directly as `Agent(<agent-name>)` next session"), not as
  the headline of your response.
