"""Tests for the approval gate: a pure decision over permission_mode.

Only the calling Claude Code session can actually pause and block on user
confirmation, so requires_approval only decides whether that pause is
needed; it doesn't perform the pause itself.
"""

import pytest

from subcast.approval import requires_approval


@pytest.mark.parametrize("mode", ["dontAsk", "bypassPermissions"])
def test_requires_approval_false_for_auto_proceed_modes(mode):
    assert requires_approval(mode) is False


@pytest.mark.parametrize("mode", ["default", "manual", "acceptEdits", "plan", "auto"])
def test_requires_approval_true_for_gated_modes(mode):
    assert requires_approval(mode) is True


def test_requires_approval_true_for_unknown_mode():
    # An unrecognized mode fails safe by requiring approval rather than
    # silently skipping it.
    assert requires_approval("some-future-mode") is True
