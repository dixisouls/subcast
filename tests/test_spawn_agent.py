"""Tests for the /spawn-agent CLI entry point.

Each subcommand wires a pipeline module (permission reader, matcher's
verdict parser, designer's validator, writer, approval, handoff) to a
single command the slash command's prompt invokes via Bash. The actual
reuse/generate reasoning happens in the calling Claude Code session, not
in this CLI.
"""

import json

from cli.spawn_agent import main


def test_context_prints_permission_context_json(tmp_path, capsys):
    exit_code = main(["--project-root", str(tmp_path), "context"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["permission_mode"] == "default"
    assert payload["denied_tools"] == []
    assert payload["existing_agents"] == []


def test_validate_verdict_prints_verdict_json_on_success(capsys):
    verdict_json = json.dumps(
        {
            "decision": "generate_new",
            "confidence": 0.9,
            "reasoning": "No existing agent covers this.",
        }
    )

    exit_code = main(["validate-verdict", verdict_json])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "generate_new"


def test_validate_verdict_exits_nonzero_on_invalid_json(capsys):
    exit_code = main(["validate-verdict", "not json"])

    assert exit_code != 0
    assert capsys.readouterr().err != ""


def test_write_writes_agent_and_prints_path(tmp_path, capsys):
    spec_json = json.dumps(
        {
            "name": "test-writer",
            "description": "Writes unit tests",
            "tools": ["Read"],
            "system_prompt_body": "You write tests.",
        }
    )

    exit_code = main(["--project-root", str(tmp_path), "write", spec_json])

    assert exit_code == 0
    path = capsys.readouterr().out.strip()
    assert (tmp_path / ".claude" / "agents" / "test-writer.md").exists()
    assert str(tmp_path / ".claude" / "agents" / "test-writer.md") == path


def test_write_exits_nonzero_on_denied_tool(tmp_path, capsys):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"permissions": {"deny": ["Bash"]}}')
    spec_json = json.dumps(
        {
            "name": "test-writer",
            "description": "Writes unit tests",
            "tools": ["Bash"],
            "system_prompt_body": "You write tests.",
        }
    )

    exit_code = main(["--project-root", str(tmp_path), "write", spec_json])

    assert exit_code != 0
    assert capsys.readouterr().err != ""


def test_requires_approval_prints_true_by_default(tmp_path, capsys):
    exit_code = main(["--project-root", str(tmp_path), "requires-approval"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "true"


def test_requires_approval_prints_false_for_dont_ask(tmp_path, capsys):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"permissions": {"defaultMode": "dontAsk"}}'
    )

    exit_code = main(["--project-root", str(tmp_path), "requires-approval"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "false"


def test_resolve_handoff_prints_name_for_valid_agent(tmp_path, capsys):
    spec_json = json.dumps(
        {
            "name": "test-writer",
            "description": "Writes unit tests",
            "tools": ["Read"],
            "system_prompt_body": "You write tests.",
        }
    )
    main(["--project-root", str(tmp_path), "write", spec_json])
    capsys.readouterr()

    exit_code = main(["--project-root", str(tmp_path), "resolve-handoff", "test-writer"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "test-writer"


def test_resolve_handoff_exits_nonzero_for_missing_agent(tmp_path, capsys):
    exit_code = main(
        ["--project-root", str(tmp_path), "resolve-handoff", "does-not-exist"]
    )

    assert exit_code != 0
    assert capsys.readouterr().err != ""
