"""Provenance manifest: tracks which agents SubCast itself created.

Stored at .claude/subcast/agents.json so `prune` and `list` can tell
SubCast-generated agents apart from hand-authored ones — pruning never
deletes a human's agent by accident. The manifest self-heals: every
mutation drops entries whose agent file no longer exists, so a manually
deleted agent's stale entry is cleaned on the next create/remove.

Agent files themselves stay pristine Claude Code frontmatter — provenance
lives only here, never in the agent markdown.
"""

from __future__ import annotations

import json
from pathlib import Path


def _manifest_path(project_root: str | Path) -> Path:
    return Path(project_root) / ".claude" / "subcast" / "agents.json"


def _agents_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".claude" / "agents"


def _load(project_root: str | Path) -> set[str]:
    path = _manifest_path(project_root)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    created = data.get("created", []) if isinstance(data, dict) else []
    return {name for name in created if isinstance(name, str)}


def _valid_subset(project_root: str | Path, names: set[str]) -> set[str]:
    agents_dir = _agents_dir(project_root)
    return {name for name in names if (agents_dir / f"{name}.md").exists()}


def _write(project_root: str | Path, names: set[str]) -> None:
    path = _manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"created": sorted(names)}, indent=2) + "\n")


def read_manifest(project_root: str | Path) -> set[str]:
    """Returns the raw set of names recorded in the manifest (no reconcile)."""
    return _load(project_root)


def reconcile(project_root: str | Path) -> set[str]:
    """Drops entries whose agent files no longer exist, writes back, and
    returns the current valid set."""
    valid = _valid_subset(project_root, _load(project_root))
    _write(project_root, valid)
    return valid


def record_created(project_root: str | Path, name: str) -> set[str]:
    """Records that SubCast created `name`, reconciling stale entries first.
    A name whose file doesn't exist is not recorded (record is called after a
    successful write, so the file should be present)."""
    names = _valid_subset(project_root, _load(project_root))
    if (_agents_dir(project_root) / f"{name}.md").exists():
        names.add(name)
    _write(project_root, names)
    return names


def remove_from_manifest(project_root: str | Path, name: str) -> set[str]:
    """Removes `name` from the manifest, reconciling stale entries first."""
    names = _valid_subset(project_root, _load(project_root))
    names.discard(name)
    _write(project_root, names)
    return names


def is_subcast_created(project_root: str | Path, name: str) -> bool:
    """True if `name` is recorded as SubCast-created and its file exists."""
    return name in _valid_subset(project_root, _load(project_root))
