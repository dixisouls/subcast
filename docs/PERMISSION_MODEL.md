# Permission model

SubCast's core safety claim is simple to state and easy to get subtly
wrong: **never assign a tool a project has denied.** This document covers
the three-way split that makes this work, the nuance that makes it correct
rather than merely conservative, and why approval inherits Claude Code's
own `permissionMode` instead of introducing a separate setting.

## The three-way split

Every tool a project could assign to a subagent falls into exactly one of
three buckets, computed by `permission_reader.parse_permissions`:

- **`allowed_tools`** — explicitly granted in `.claude/settings.json`'s
  `permissions.allow`. Freely assignable.
- **`denied_tools`** — explicitly forbidden in `permissions.deny`. Never
  assignable, structurally: the designer prompt never lists these as
  options at all.
- **`unmentioned_tools`** — every known tool (the full built-in set, plus
  any live-discovered MCP tools) minus the two lists above. Still
  assignable — Claude Code's own runtime will prompt the user the first
  time the assigned agent actually tries to use it. SubCast doesn't need to
  pre-emptively ask on its behalf.

## Full-match vs. scoped: the nuance that matters

A naive implementation might treat any deny-list mention of a tool as a
full deny. This is wrong, and would make SubCast far less useful than
intended: a project denying `Bash(rm -rf *)` clearly still wants `Bash`
available in general, just not that one dangerous pattern. Full-tool
removal only happens when a rule is:

- a **bare tool name** (`Bash`), or
- an **explicit full-match specifier** (`Bash(*)`, equivalent to bare), or
- a **tool-name-position wildcard** (`mcp__*` denies every MCP tool;
  `*` denies everything)

A **scoped** rule (`Bash(rm -rf *)`, `Bash(npm run test *)`) restricts a
specific invocation pattern but leaves the tool itself generally
assignable — Claude Code enforces the narrower restriction at the point of
actual use, regardless of which subagent is using the tool. SubCast's
permission reader doesn't need to duplicate that enforcement; it only
needs to get the *assignability* question right.

The same full-vs-scoped distinction applies to `allow` rules: a scoped
allow (`Bash(npm run build)`) doesn't establish that the *whole* tool is
safe to freely assign, so it doesn't add the tool to `allowed_tools`
either — it stays `unmentioned` instead, correctly matching Claude Code's
own note that "an allow rule for one parameter value wouldn't establish
that the call is safe overall."

Conflicting rules (the same tool named in both `allow` and `deny`) resolve
to deny — the conservative, safe default.

This distinction was verified against Claude Code's real documented
permission-rule semantics, not assumed, and is covered by
`tests/test_permission_reader.py`'s fixture set (empty settings, partial
settings, conflicting allow/deny entries, wildcard denies).

## Structural enforcement, not just instruction

The designer prompt in `commands/spawn-agent.md` is given *only*
`allowed_tools` and `unmentioned_tools` as valid options for a new or
modified subagent's `tools` list — `denied_tools` is never included in the
prompt at all. This makes a denied tool structurally impossible to select,
rather than relying on the calling session to correctly avoid a tool it can
see listed as forbidden.

After the calling session responds, `designer.parse_designed_subagent` runs
an independent second check: every tool name in the parsed result must
appear in `allowed_tools ∪ unmentioned_tools`, or the entire generation is
rejected outright, with the offending tool names named in the error. This
is a hard bar, not a nice-to-have — silently dropping an invalid tool and
proceeding would produce an agent with fewer capabilities than intended,
with no one noticing.

## A generated agent can't escalate its own permission mode

Tools aren't the only thing that decides what a subagent can do — its
`permissionMode` frontmatter does too. An agent carrying `permissionMode:
bypassPermissions` runs its tools without prompting, which would be an
escalation beyond whatever posture the project itself runs under. Because
the generated agent's fields come from the calling session's output, this
has to be guarded, not trusted.

`designer.parse_designed_subagent` rejects any generated `permission_mode`
that is unknown, or **more permissive than the project's own mode**. Modes
are ranked by permissiveness (`plan`/`dontAsk` least, then `default`, then
`acceptEdits`, `auto`, and `bypassPermissions` most); a generated value may
be at or below the project's rank, never above it. When in doubt the field
is simply omitted, so the agent inherits the session's mode rather than
declaring a stronger one. A project already running in `bypassPermissions`
can still produce a `bypassPermissions` agent — that isn't an escalation —
but a `default` project can never mint one.

## Agent names are validated before they touch the filesystem

An agent's `name` is used to build its file path
(`.claude/agents/<name>.md`), and it too originates from the calling
session. A name like `../../../etc/something` would write outside the
agents directory. Both the designer and the writer reject any name that
isn't a plain Claude Code agent name (`^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`),
and the writer additionally asserts the resolved path stays inside
`.claude/agents/` before writing. This closes an arbitrary-file-write path
that prompt injection could otherwise reach.

## MCP servers are only introspected once locally approved

`build_permission_context` discovers a project MCP server's tool names by
actually launching that server (from `.mcp.json`) and asking it. To avoid a
freshly-cloned untrusted repo silently executing its own `.mcp.json`
command the first time someone runs `/subcast:spawn-agent`, discovery is
gated: a server is spawned only if it's approved in the **git-untracked**
`.claude/settings.local.json` (via `enabledMcpjsonServers` or
`enableAllProjectMcpServers`, honoring `disabledMcpjsonServers`). Approvals
committed to `.claude/settings.json` are deliberately ignored — a malicious
repo could ship that file, so it must not be able to self-approve. This
mirrors Claude Code's own rule that committed approvals don't count in an
untrusted folder. With no local approval, `connected_mcp_tools` is simply
empty and the pipeline proceeds normally.

## Capability gaps are reported, never fabricated

If a task genuinely needs a capability nothing in `allowed_tools ∪
unmentioned_tools` covers, the designer sets `capability_gap` to a short
explanation and designs the rest of the agent without that capability. A
tool name that doesn't exist in Claude Code is never invented to paper
over the gap.

## Why approval inherits `permissionMode`, not a separate setting

Claude Code already has a permission-mode system users understand and
configure (`default`/`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk`,
`bypassPermissions`). Introducing a second, SubCast-specific approval
setting would mean two systems a user has to reason about instead of one,
and they could easily drift out of sync (e.g. a project in `bypassPermissions`
mode for everything else, but still gated for SubCast specifically, for no
reason the user configured).

`approval.requires_approval(permission_mode)` is a pure function:
`dontAsk` and `bypassPermissions` proceed immediately after the write step;
every other mode (including any future mode SubCast doesn't yet recognize —
fail-safe) requires the calling session to show the full generated
`SubagentSpec` and get explicit confirmation first. This mirrors exactly
how Claude Code's own runtime already treats those same modes for every
other tool call, so a user who understands their project's permission mode
already understands how SubCast will behave, without learning anything new.
