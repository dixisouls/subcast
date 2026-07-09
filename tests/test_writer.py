"""Tests for the writer: serializing SubagentSpec to .claude/agents/*.md,
checking for name collisions before writing.
"""

import pytest

from subcast.specs import SubagentSpec
from subcast.writer import write_subagent

SPEC = SubagentSpec(
    name="test-writer",
    description="Writes unit tests for Python modules",
    tools=["Read", "Write"],
    model="sonnet",
    system_prompt_body="You write tests.",
)


def test_write_subagent_creates_agents_directory_if_missing(tmp_path):
    path = write_subagent(SPEC, tmp_path)

    assert (tmp_path / ".claude" / "agents").is_dir()
    assert path.exists()


def test_write_subagent_writes_path_based_on_name(tmp_path):
    path = write_subagent(SPEC, tmp_path)

    assert path == tmp_path / ".claude" / "agents" / "test-writer.md"


def test_write_subagent_writes_content_matching_to_markdown(tmp_path):
    path = write_subagent(SPEC, tmp_path)

    assert path.read_text() == SPEC.to_markdown()


def test_write_subagent_raises_on_name_collision_without_overwrite(tmp_path):
    write_subagent(SPEC, tmp_path)

    with pytest.raises(ValueError):
        write_subagent(SPEC, tmp_path)


def test_write_subagent_overwrites_when_overwrite_true(tmp_path):
    write_subagent(SPEC, tmp_path)

    updated = SubagentSpec(
        name="test-writer",
        description="Writes unit tests for Python modules, now with Bash",
        tools=["Read", "Write", "Bash"],
        model="sonnet",
        system_prompt_body="You write tests, including integration tests.",
    )

    path = write_subagent(updated, tmp_path, overwrite=True)

    assert path.read_text() == updated.to_markdown()


def test_write_subagent_collision_check_uses_name_field_not_filename(tmp_path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    # File name differs from the agent's own `name:` field, matching Claude
    # Code's own rule that identity comes only from that field.
    (agents_dir / "differently-named-file.md").write_text(SPEC.to_markdown())

    with pytest.raises(ValueError):
        write_subagent(SPEC, tmp_path)


def test_write_subagent_no_collision_for_different_name(tmp_path):
    write_subagent(SPEC, tmp_path)

    other = SubagentSpec(
        name="doc-writer",
        description="Writes docs",
        system_prompt_body="You write docs.",
    )

    path = write_subagent(other, tmp_path)

    assert path == tmp_path / ".claude" / "agents" / "doc-writer.md"


@pytest.mark.parametrize(
    "bad_name",
    ["../../../../tmp/evil", "../outside", "has space", "UpperCase", "slash/name", ""],
)
def test_write_subagent_rejects_invalid_name(tmp_path, bad_name):
    bad = SubagentSpec(
        name=bad_name,
        description="Attempts a bad path",
        system_prompt_body="body",
    )

    with pytest.raises(ValueError):
        write_subagent(bad, tmp_path)


def test_write_subagent_never_writes_outside_agents_dir(tmp_path):
    bad = SubagentSpec(
        name="../../../../tmp/subcast-should-not-exist",
        description="path traversal attempt",
        system_prompt_body="body",
    )

    with pytest.raises(ValueError):
        write_subagent(bad, tmp_path)

    # Nothing should have been written outside the project's agents dir.
    from pathlib import Path

    assert not Path("/tmp/subcast-should-not-exist.md").exists()
