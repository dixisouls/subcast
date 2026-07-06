---
description: Match an existing project subagent to a task, or design and write a new one, then hand off to it
argument-hint: [task description]
disable-model-invocation: true
allowed-tools: Bash(subcast-spawn-agent:*), Agent
---

Task: $ARGUMENTS

You are running the SubCast pipeline for this task. Follow every step below
in order. Never invent a tool name that isn't explicitly listed as valid in
step 1's output — if the task needs a capability nothing there covers,
document it in `capability_gap` instead.

1. Run `subcast-spawn-agent context` from the project root. This prints
   the current permission context as JSON: `allowed_tools`,
   `denied_tools`, `unmentioned_tools`, `connected_mcp_tools`,
   `existing_agents` (each with `name`, `description`, `tools`), and
   `permission_mode`.

2. Compare the task against each existing agent's `description` yourself,
   using your own judgment (no tool call needed for this step). Decide one
   of:
   - `reuse_exact`: an existing agent already covers this task as-is.
   - `reuse_with_modification`: an existing agent is close, but its tools
     or system prompt need a small change for this task.
   - `generate_new`: nothing existing fits well enough.

   Optionally run `subcast-spawn-agent validate-verdict '<json>'` with
   your decision as `{"decision", "matched_agent_name", "confidence",
   "reasoning", "modification_notes"}` to double-check it's well-formed
   before proceeding.

3. If `reuse_exact`: skip straight to step 6 using that agent's name.

4. If `reuse_with_modification` or `generate_new`: design the subagent
   yourself. Its `tools` list may only contain values from `allowed_tools`
   or `unmentioned_tools` from step 1 — never from `denied_tools`, and
   never a name that doesn't appear in either list.

5. Before writing, run `subcast-spawn-agent requires-approval`.
   - If it prints `true`, show the user the full subagent definition you
     designed and get explicit confirmation before continuing.
   - If it prints `false`, continue directly.

   Then run `subcast-spawn-agent write '<json>'` with your designed
   subagent as `{"name", "description", "tools", "model",
   "permission_mode", "system_prompt_body", "capability_gap"}`. Add
   `--overwrite` only when `reuse_with_modification` is updating an
   existing agent of the same name. If this command fails (for example, a
   denied or unknown tool), fix the `tools` list and retry — do not
   continue until it succeeds.

6. Run `subcast-spawn-agent resolve-handoff <agent-name>` to confirm the
   agent file is valid and ready.

7. Invoke `Agent(<agent-name>)` with the original task description to
   actually execute it. If this is the very first agent ever written to
   this project's `.claude/agents/` (the directory didn't exist yet when
   this session started), the agent type may not be recognized yet — this
   is a known Claude Code limitation, not a failure of this pipeline: the
   directory watcher only picks up a directory that already existed at
   session start. If `Agent(<agent-name>)` isn't available, fall back to
   executing the task yourself directly (or via the `general-purpose`
   agent) using the same instructions as the written subagent, and tell
   the user the new agent will be usable via `Agent(<agent-name>)` from
   their next session onward.
