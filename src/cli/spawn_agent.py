"""Entry point wired to the /spawn-agent slash command.

Each subcommand exposes one deterministic pipeline step. The reuse-vs-
generate judgment and the subagent design itself are made by the calling
Claude Code session (see subcast.matcher / subcast.designer docstrings);
this CLI only supplies PermissionContext, validates the session's
structured JSON output, writes the result, and resolves the handoff
target. It never calls an LLM API itself.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from subcast.approval import requires_approval
from subcast.designer import parse_designed_subagent
from subcast.handoff import resolve_handoff
from subcast.matcher import parse_match_verdict
from subcast.permission_reader import build_permission_context
from subcast.writer import write_subagent


def _cmd_context(args: argparse.Namespace) -> int:
    context = build_permission_context(args.project_root)
    print(json.dumps(dataclasses.asdict(context)))
    return 0


def _read_json_arg(value: str) -> str:
    """Returns the JSON payload for a subcommand. A value of "-" (or empty)
    means read it from stdin instead of the command line, which avoids
    exposing the payload in the process list and sidesteps shell quoting."""
    if value in ("", "-"):
        return sys.stdin.read()
    return value


def _cmd_validate_verdict(args: argparse.Namespace) -> int:
    try:
        verdict = parse_match_verdict(_read_json_arg(args.verdict_json))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(dataclasses.asdict(verdict)))
    return 0


def _cmd_write(args: argparse.Namespace) -> int:
    context = build_permission_context(args.project_root)
    try:
        spec = parse_designed_subagent(_read_json_arg(args.spec_json), context)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        path = write_subagent(spec, args.project_root, overwrite=args.overwrite)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Surface a documented capability gap so the calling session can relay it
    # to the user. stdout stays the clean path (scripts read it); the gap goes
    # to stderr.
    if spec.capability_gap:
        print(f"capability gap: {spec.capability_gap}", file=sys.stderr)

    print(str(path))
    return 0


def _cmd_requires_approval(args: argparse.Namespace) -> int:
    context = build_permission_context(args.project_root)
    print("true" if requires_approval(context.permission_mode) else "false")
    return 0


def _cmd_resolve_handoff(args: argparse.Namespace) -> int:
    try:
        name = resolve_handoff(args.agent_name, args.project_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(name)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spawn_agent")
    parser.add_argument("--project-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("context").set_defaults(func=_cmd_context)

    validate_verdict = subparsers.add_parser("validate-verdict")
    validate_verdict.add_argument("verdict_json", nargs="?", default="-")
    validate_verdict.set_defaults(func=_cmd_validate_verdict)

    write = subparsers.add_parser("write")
    write.add_argument("spec_json", nargs="?", default="-")
    write.add_argument("--overwrite", action="store_true")
    write.set_defaults(func=_cmd_write)

    subparsers.add_parser("requires-approval").set_defaults(func=_cmd_requires_approval)

    resolve = subparsers.add_parser("resolve-handoff")
    resolve.add_argument("agent_name")
    resolve.set_defaults(func=_cmd_resolve_handoff)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
