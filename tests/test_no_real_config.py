"""Standalone guard: the real, per-machine job-hunt config file must never move.

Independent of every other test module: it snapshots the real config path (see
_config_guard.real_config_path - computed from the environment as it stood at
interpreter start, ignoring any XDG_CONFIG_HOME/APPDATA a test has patched)
at import time, and asserts nothing has touched it by the time its one test
runs. Catches any test module that calls workspace.save_workspace() (directly,
or indirectly through onboard.create_person/migrate.migrate_person) without
first isolating XDG_CONFIG_HOME/APPDATA to a temp dir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _config_guard

import unittest

_IMPORT_TIME_SNAPSHOT = _config_guard.snapshot()


class NoRealConfigTouchedTests(unittest.TestCase):
    def test_real_config_file_unchanged(self):
        _config_guard.assert_unchanged(_IMPORT_TIME_SNAPSHOT)


if __name__ == "__main__":
    unittest.main()
