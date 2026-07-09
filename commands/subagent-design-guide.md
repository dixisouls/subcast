# Subagent design guide

Read this before writing `system_prompt_body` for a new or modified
subagent. It exists because "design the subagent yourself" alone tends to
produce a generic one-liner — this is a recipe for the alternative: a
prompt with the same depth as a real specialist agent.

## What separates a good subagent prompt from a shallow one

A shallow prompt names the job and stops:

> You write tests for Python code.

A good prompt reads like a specialist was actually briefed for the role: it
states what the agent knows, how it works through a task step by step, what
"done" looks like, and how it checks its own output before reporting. The
difference isn't length for its own sake — it's that every required part
below is actually present, in order.

## The recipe: required parts, in order

1. **Role/persona opening line.** One sentence naming the specific
   expertise, not a generic label. "You are an elite Python test engineer
   with deep expertise in pytest fixtures and property-based testing" beats
   "You write tests."

2. **Core responsibilities/expertise** (bulleted). The specific things this
   agent knows or does, not a restatement of the task. If the task
   description already covers this well, keep this section short rather
   than padding it.

3. **Process** (numbered steps). How the agent should work through a
   typical task from start to finish — read/investigate first, then act,
   then verify. This is the part most shallow prompts skip entirely, and
   it's the part that most changes real behavior: an agent told to "read
   the target file fully before writing anything" behaves differently than
   one just told to "write tests."

4. **Output expectations.** What form the result should take — file
   naming/location conventions, what to report back, what NOT to change
   (e.g. don't silently modify the source file being tested unless asked).

5. **Quality standards.** What "good" looks like for this specific domain —
   concrete, not "be thorough." E.g. "cover the normal case, at least one
   boundary condition, and error handling" rather than "write good tests."

6. **Self-verification checklist.** What the agent should confirm before
   reporting the task done. This is what turns "I think this works" into
   "I checked this works."

Every part must be present. A prompt missing the process or
self-verification section is still a shallow prompt, even if the role line
is elaborate.

## Worked example

**Shallow (avoid):**

```markdown
You write unit tests for Python code. Use pytest. Make sure the tests pass.
```

**Following the recipe (real example, from a production Claude Code agent —
adapt the domain specifics, keep the structure):**

```markdown
You are an elite test engineer with deep expertise in testing Python
modules, mocking external dependencies, and property-based testing.

## Core Expertise

- Writing comprehensive tests using pytest, including fixtures and
  parametrization
- Mocking external services and I/O so tests run fast and deterministically
- Identifying edge cases the developer may not have considered

## Process

When given a target module, you will:

1. **Read the target file fully** to understand its public functions,
   inputs, outputs, and dependencies before writing anything.
2. **Check for an existing test convention** (pytest vs unittest, existing
   test file naming, existing fixtures) and follow it if one exists.
3. **Cover normal cases, boundary conditions, and error handling** —
   invalid input types, empty/zero/negative values, and any exceptions the
   function can raise.
4. **Run the test suite** to confirm every test passes before reporting
   completion. Fix failures you introduced; if a test fails because of an
   actual bug in the source file, report it instead of silently patching it.

## Quality Standards

- Tests must be deterministic — no reliance on real time, real network
  calls, or test execution order
- Test names describe the behavior under test, not the input values
- No redundant assertions covering the same behavior twice

## Self-Verification

Before reporting done, confirm:
- [ ] Every public function/method in the target file has at least one test
- [ ] The full test suite was actually run, not just written
- [ ] No source file was modified except where an actual bug justified it
```

Notice what makes this work: the process section describes an actual
sequence of investigation-then-action-then-verification, not just a
restatement of "write tests." The quality standards are concrete enough to
check against. The self-verification list is literally checkable.

## Choosing the model

Set the `model` field to match the task's actual weight:

- **`haiku`** — mechanical, well-specified, low-judgment work: renaming,
  formatting, simple boilerplate generation, straightforward lookups.
- **`sonnet`** — standard substantive work: writing tests, typical feature
  code, focused refactors, documentation. This is the right pick for most
  agents.
- **`opus`** — genuinely hard reasoning: architecture and design decisions,
  subtle debugging across many files, security analysis, anything where a
  wrong call is expensive.

Pick the level that fits; **omit `model` (leave it null) only when you
genuinely can't gauge the task's weight**, in which case the agent inherits
the session's model. Don't reach for a bigger model "to be safe" — an
oversized model for trivial work just burns cost, and an undersized one for
hard work produces bad results.

## Fill-in template

Use this shape as your starting structure, adapting section names to the
domain:

```markdown
You are a [specific role], with expertise in [concrete areas, not generic
buzzwords].

## Core Expertise / Responsibilities

- [specific thing this agent knows or does]
- [specific thing this agent knows or does]

## Process

1. [investigate/understand step]
2. [main action step(s)]
3. [verification step]

## Output Expectations

- [where/how results should be reported or saved]
- [what NOT to touch or change]

## Quality Standards

- [concrete, checkable standard for this domain]

## Self-Verification

Before reporting done, confirm:
- [ ] [checkable condition]
- [ ] [checkable condition]
```
