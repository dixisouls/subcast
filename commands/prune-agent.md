---
description: Delete a project subagent that SubCast created
argument-hint: [agent-name]
disable-model-invocation: true
allowed-tools: Bash(subcast-spawn-agent:*)
---

Agent to remove: $ARGUMENTS

Run `subcast-spawn-agent remove $ARGUMENTS` from the project root. This
deletes `.claude/agents/<name>.md` and cleans the agent out of SubCast's
provenance manifest.

By default the command **refuses** to delete an agent that SubCast did not
create (to protect hand-authored agents). If it exits with that message and
the user genuinely wants it gone anyway, confirm with them first, then rerun
as `subcast-spawn-agent remove $ARGUMENTS --force`.

If the command reports the agent doesn't exist or the name is invalid,
relay that to the user rather than retrying blindly. You can run
`/subcast:list-agents` first to see what's available and which agents are
SubCast-created.
