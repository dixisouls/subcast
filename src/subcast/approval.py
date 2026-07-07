"""Decides whether a newly generated subagent needs explicit user approval
before its first run, based on the project's permission mode.

Only the calling Claude Code session can actually pause and block on user
confirmation, so this module makes the decision, it doesn't perform the
pause itself. The slash command's prompt is responsible for showing the
full generated SubagentSpec and blocking when requires_approval returns
True, and for proceeding straight to the writer step when it returns False.
"""

from __future__ import annotations

_AUTO_PROCEED_MODES = frozenset({"dontAsk", "bypassPermissions"})


def requires_approval(permission_mode: str) -> bool:
    return permission_mode not in _AUTO_PROCEED_MODES
