# Demo: before and after

This walks through the same scenario the project's differentiator claims:
run SubCast on two similar tasks in the same fresh project, and watch
`.claude/agents/` grow by exactly one agent, reused (not duplicated) on the
second run. Every command and output below is real, run against a clean
scratch project with the plugin installed via `--plugin-dir` — nothing here
is fabricated or edited for effect.

## Setup

```bash
mkdir demo-project && cd demo-project
git init
mkdir -p .claude
echo '{"permissions": {"defaultMode": "dontAsk"}}' > .claude/settings.json
```

(`dontAsk` skips the approval prompt for this scripted walkthrough. The
default mode would instead pause and show you the full agent definition
before writing it — see [`PERMISSION_MODEL.md`](./PERMISSION_MODEL.md).)

Drop in a small module to act on:

```python
# temperature.py
def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32


def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9
```

Confirm there are no agents yet:

```
$ ls .claude/agents
ls: .claude/agents: No such file or directory
```

## Run 1: nothing to reuse, generate a new agent

```
/subcast:spawn-agent write unit tests for temperature.py
```

Output:

> All 21 tests pass. `test_temperature.py` was created covering both
> conversion functions with known values, round-trip conversion, and error
> handling for non-numeric input — no changes to `temperature.py` itself.
>
> A new `python-test-writer` agent was also written to `.claude/agents/`
> for reuse; it wasn't recognized this session (a known Claude Code
> limitation), so I ran the task directly with the same brief. It'll be
> available via `Agent(python-test-writer)` starting next session.

`.claude/agents/` now has exactly one file:

```
$ ls .claude/agents
python-test-writer.md
```

Its contents follow the structured recipe from
[`subagent-design-guide.md`](../commands/subagent-design-guide.md) — role
line, bulleted expertise, a numbered process, output expectations, quality
standards, and a checkable self-verification list, not a generic
one-liner:

```markdown
---
name: python-test-writer
description: Writes and runs pytest unit tests for Python modules, covering normal cases, boundary conditions, and error handling.
tools: Read, Write, Edit, Bash
model: sonnet
permissionMode: default
---

You are an elite test engineer with deep expertise in testing Python modules, mocking external dependencies, and property-based testing.

## Core Expertise

- Writing comprehensive tests using pytest, including fixtures and parametrization
- Mocking external services and I/O so tests run fast and deterministically
- Identifying edge cases the developer may not have considered (invalid types, boundary values, exceptions)

## Process

When given a target module, you will:

1. **Read the target file fully** to understand its public functions, inputs, outputs, and dependencies before writing anything.
2. **Check for an existing test convention** ... and follow it if one exists.
3. **Design test cases covering normal cases, boundary conditions, and error handling** ...
4. **Write the tests**, using `pytest.mark.parametrize` where multiple similar cases share structure ...
5. **Run the test suite** (`pytest`) to confirm every test passes before reporting completion. ...

[Output Expectations / Quality Standards / Self-Verification sections follow the same recipe]
```

Note the fallback: this same session can't invoke the agent it just wrote
(a real, currently-open upstream Claude Code limitation, not a SubCast
bug — see [`ARCHITECTURE.md`](./ARCHITECTURE.md)), so it executed the task
directly using the identical brief instead. The task still completes
correctly either way.

## Run 2: reuse, not duplication

A second, similar module:

```python
# distance.py
def miles_to_km(miles):
    return miles * 1.60934


def km_to_miles(km):
    return km / 1.60934
```

```
/subcast:spawn-agent write unit tests for distance.py
```

Output:

> The `python-test-writer` agent finished: it created `test_distance.py`
> with 27 tests covering `miles_to_km` and `km_to_miles` (known values,
> round-trips, zero/negative/large inputs, and `TypeError` handling for
> bad input types). All 27 tests pass, and no source files were modified.

`.claude/agents/` is still exactly one file — the same agent, reused, not
a second `python-test-writer-2` or similar:

```
$ ls .claude/agents
python-test-writer.md
```

This time the agent *was* invoked directly via `Agent(python-test-writer)`
— by the second session, `.claude/agents/` already existed for the whole
session, so the earlier limitation doesn't apply. This is the realistic
common case: the one-time fallback only ever affects the very first agent
a project generates.

## What actually ran

Both test files are real and pass:

```
$ python3 -m pytest test_temperature.py -q
.....................                                                    [100%]
21 passed

$ python3 -m pytest test_distance.py -q
...........................                                              [100%]
27 passed
```

## Running this yourself

```bash
claude --plugin-dir /path/to/subcast
```

from inside any project, or install it permanently with no `--plugin-dir`
needed at all:

```
/plugin marketplace add dixisouls/subcast
/plugin install subcast@subcast
```
