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


def test_write_surfaces_capability_gap_on_stderr(tmp_path, capsys):
    spec_json = json.dumps(
        {
            "name": "gap-agent",
            "description": "Has a capability gap",
            "tools": ["Read"],
            "system_prompt_body": "You do your best.",
            "capability_gap": "Needs a screenshot tool that isn't available.",
        }
    )

    exit_code = main(["--project-root", str(tmp_path), "write", spec_json])
    captured = capsys.readouterr()

    assert exit_code == 0
    # stdout stays the clean path; the gap is surfaced on stderr so the
    # calling session can relay it to the user.
    assert captured.out.strip().endswith("gap-agent.md")
    assert "screenshot tool" in captured.err


def test_write_reads_spec_from_stdin_when_dash(tmp_path, capsys, monkeypatch):
    import io

    spec_json = json.dumps(
        {
            "name": "stdin-agent",
            "description": "Written via stdin",
            "tools": ["Read"],
            "system_prompt_body": "You were piped in.",
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(spec_json))

    exit_code = main(["--project-root", str(tmp_path), "write", "-"])

    assert exit_code == 0
    assert (tmp_path / ".claude" / "agents" / "stdin-agent.md").exists()


def _write_spec(tmp_path, name="feat-agent", extra=""):
    return json.dumps(
        {
            "name": name,
            "description": "Feature test agent",
            "tools": ["Read"],
            "system_prompt_body": "You do the thing." + extra,
        }
    )


def test_write_records_created_agent_in_manifest(tmp_path):
    from subcast.manifest import is_subcast_created

    main(["--project-root", str(tmp_path), "write", _write_spec(tmp_path, "made-by-subcast")])

    assert is_subcast_created(tmp_path, "made-by-subcast") is True


def test_write_dry_run_prints_markdown_without_writing(tmp_path, capsys):
    exit_code = main(
        ["--project-root", str(tmp_path), "write", "--dry-run", _write_spec(tmp_path, "preview")]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "name: preview" in out
    assert not (tmp_path / ".claude" / "agents" / "preview.md").exists()


def test_list_reports_agents_with_subcast_provenance(tmp_path, capsys):
    # One agent created via SubCast, one dropped in by hand.
    main(["--project-root", str(tmp_path), "write", _write_spec(tmp_path, "auto")])
    capsys.readouterr()  # flush the write command's output
    agents_dir = tmp_path / ".claude" / "agents"
    (agents_dir / "handmade.md").write_text(
        "---\nname: handmade\ndescription: by a human\n---\n\nBody.\n"
    )

    exit_code = main(["--project-root", str(tmp_path), "list"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    by_name = {a["name"]: a for a in payload}
    assert by_name["auto"]["created_by_subcast"] is True
    assert by_name["handmade"]["created_by_subcast"] is False


def test_remove_deletes_subcast_agent_and_cleans_manifest(tmp_path, capsys):
    from subcast.manifest import read_manifest

    main(["--project-root", str(tmp_path), "write", _write_spec(tmp_path, "removable")])

    exit_code = main(["--project-root", str(tmp_path), "remove", "removable"])

    assert exit_code == 0
    assert not (tmp_path / ".claude" / "agents" / "removable.md").exists()
    assert "removable" not in read_manifest(tmp_path)


def test_remove_refuses_non_subcast_agent_without_force(tmp_path, capsys):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "handmade.md").write_text(
        "---\nname: handmade\ndescription: by a human\n---\n\nBody.\n"
    )

    exit_code = main(["--project-root", str(tmp_path), "remove", "handmade"])

    assert exit_code != 0
    assert capsys.readouterr().err != ""
    assert (agents_dir / "handmade.md").exists()  # not deleted


def test_remove_force_deletes_non_subcast_agent(tmp_path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "handmade.md").write_text(
        "---\nname: handmade\ndescription: by a human\n---\n\nBody.\n"
    )

    exit_code = main(["--project-root", str(tmp_path), "remove", "handmade", "--force"])

    assert exit_code == 0
    assert not (agents_dir / "handmade.md").exists()


def test_remove_rejects_invalid_name(tmp_path):
    exit_code = main(["--project-root", str(tmp_path), "remove", "../../etc/passwd"])

    assert exit_code != 0


def test_context_pretty_prints_human_readable(tmp_path, capsys):
    exit_code = main(["--project-root", str(tmp_path), "context", "--pretty"])
    out = capsys.readouterr().out

    assert exit_code == 0
    # Pretty output is not raw single-line JSON; it labels the sections.
    assert "permission mode" in out.lower()
