---
description: List the project's subagents, showing which ones SubCast created
disable-model-invocation: true
allowed-tools: Bash(subcast-spawn-agent:*)
---

Run `subcast-spawn-agent list` from the project root. It prints a JSON array
of the project's subagents (from `.claude/agents/`), each with its `name`,
`description`, `tools`, and a `created_by_subcast` flag.

Present the result to the user as a short, readable summary — group or note
which agents SubCast generated versus which were authored by hand
(`created_by_subcast: false`), since only the SubCast-created ones can be
removed with `/subcast:prune-agent` without `--force`.
