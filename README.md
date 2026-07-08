# SubCast

**Subagent casting.** SubCast is a Claude Code plugin that spawns the right
subagent for the task in front of you — matching one that already exists in
your project, adapting it, or designing a brand new one on the spot. Nothing
is pre-authored. Your `.claude/agents/` folder grows exactly as your project
needs it to, instead of shipping with sixty agents you'll never use.

## Install

```
/plugin marketplace add dixisouls/subcast
/plugin install subcast@subcast
```

That's it — no pip, no pipx, nothing else to set up. Want to try it first
without installing?

```
claude --plugin-dir /path/to/subcast
```

## Quickstart

```
/subcast:spawn-agent write unit tests for calculator.py
```

First time, SubCast finds nothing to reuse, so it designs a focused
`python-test-writer` agent — scoped to only the tools your project
actually allows — and gets the tests written.

Ask for something similar later:

```
/subcast:spawn-agent write unit tests for stringutils.py
```

Same agent, reused automatically. No duplicate, no new file — SubCast
recognized the fit and handed the task straight to what already exists.

See [`docs/DEMO.md`](./docs/DEMO.md) for the real, unedited transcript of
exactly this.

## How it works

You describe a task with `/subcast:spawn-agent`. SubCast reads your
project's existing subagents and checks whether one already fits — not by
keyword matching, but by actually judging whether the task belongs to what
that agent already does.

If something's close but not quite right, SubCast adjusts it — a tool
added, a case folded into its process — instead of leaving you to hand-edit
it or spawning a near-duplicate. If nothing fits at all, it designs a new
subagent from scratch: a real, detailed system prompt (role, process,
quality bar, self-checks — not a generic one-liner), using only tools your
project has actually allowed. If your project's permission settings call
for it, you'll see the full definition and confirm before anything gets
written. Either way, the task runs immediately, and the agent is there
waiting the next time you need something like it.

Curious how the pieces fit together? [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
walks through the pipeline, and [`docs/PERMISSION_MODEL.md`](./docs/PERMISSION_MODEL.md)
covers exactly how SubCast decides what a generated agent is and isn't
allowed to touch.

## Status

`v1.0` — full pipeline shipped, packaged as a real plugin, verified end to
end against real projects.

## Requirements

A project already using [Claude Code](https://claude.com/product/claude-code).
SubCast reads that project's `.claude/settings.json` and `.claude/agents/`
directly and is an independent project, not affiliated with or endorsed by
Anthropic.

## License

MIT — see [LICENSE](./LICENSE).
