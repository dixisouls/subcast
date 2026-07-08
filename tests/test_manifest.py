"""Tests for the provenance manifest: which agents SubCast created.

The manifest lets `prune` and `list` distinguish SubCast-generated agents
from hand-authored ones, so pruning never deletes a human's agent by
accident. It self-heals via reconcile on every mutation.
"""

from subcast.manifest import (
    is_subcast_created,
    read_manifest,
    reconcile,
    record_created,
    remove_from_manifest,
)
from subcast.specs import SubagentSpec
from subcast.writer import write_subagent


def _make_agent(tmp_path, name):
    write_subagent(
        SubagentSpec(name=name, description="d", system_prompt_body="b"),
        tmp_path,
        overwrite=True,
    )


def test_read_manifest_empty_when_missing(tmp_path):
    assert read_manifest(tmp_path) == set()


def test_record_created_adds_name(tmp_path):
    _make_agent(tmp_path, "alpha")
    record_created(tmp_path, "alpha")

    assert read_manifest(tmp_path) == {"alpha"}
    assert is_subcast_created(tmp_path, "alpha") is True


def test_record_created_is_idempotent(tmp_path):
    _make_agent(tmp_path, "alpha")
    record_created(tmp_path, "alpha")
    record_created(tmp_path, "alpha")

    assert read_manifest(tmp_path) == {"alpha"}


def test_remove_from_manifest_drops_name(tmp_path):
    _make_agent(tmp_path, "alpha")
    record_created(tmp_path, "alpha")

    remove_from_manifest(tmp_path, "alpha")

    assert read_manifest(tmp_path) == set()


def test_reconcile_drops_entries_whose_files_are_gone(tmp_path):
    _make_agent(tmp_path, "present")
    record_created(tmp_path, "present")
    # "ghost" is in the manifest but never had a file written.
    record_created(tmp_path, "ghost")  # will reconcile away "ghost"? no file
    # record_created for a name with no file: after reconcile, ghost is dropped
    # because its file doesn't exist.
    assert "ghost" not in read_manifest(tmp_path)
    assert "present" in read_manifest(tmp_path)


def test_reconcile_runs_on_mutation_cleaning_manually_deleted_agent(tmp_path):
    _make_agent(tmp_path, "alpha")
    _make_agent(tmp_path, "beta")
    record_created(tmp_path, "alpha")
    record_created(tmp_path, "beta")

    # Simulate the user manually deleting beta's file.
    (tmp_path / ".claude" / "agents" / "beta.md").unlink()

    # Any subsequent mutation reconciles, cleaning the stale entry.
    remove_from_manifest(tmp_path, "alpha")

    assert read_manifest(tmp_path) == set()


def test_is_subcast_created_false_for_unknown(tmp_path):
    assert is_subcast_created(tmp_path, "never-made") is False


def test_read_manifest_tolerates_malformed_file(tmp_path):
    manifest_dir = tmp_path / ".claude" / "subcast"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "agents.json").write_text("{ not valid json")

    assert read_manifest(tmp_path) == set()


def test_reconcile_returns_current_valid_set(tmp_path):
    _make_agent(tmp_path, "alpha")
    record_created(tmp_path, "alpha")

    assert reconcile(tmp_path) == {"alpha"}
