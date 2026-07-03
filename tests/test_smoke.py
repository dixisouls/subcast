"""Smoke test for M0: every stub module must import cleanly."""

import importlib

MODULES = [
    "subcast",
    "subcast.specs",
    "subcast.permission_reader",
    "subcast.matcher",
    "subcast.designer",
    "subcast.writer",
    "subcast.approval",
    "subcast.handoff",
    "cli",
    "cli.spawn_agent",
]


def test_all_stub_modules_import():
    for module_name in MODULES:
        importlib.import_module(module_name)
