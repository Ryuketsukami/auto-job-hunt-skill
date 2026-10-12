"""Tests for onboard.py: first-run detection and per-person scaffold."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboard
import _config_guard

ONBOARD_SCRIPT = str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts/onboard.py")

_CONFIG_SNAPSHOT = None


def setUpModule():
    global _CONFIG_SNAPSHOT
    _CONFIG_SNAPSHOT = _config_guard.snapshot()


def tearDownModule():
    _config_guard.assert_unchanged(_CONFIG_SNAPSHOT)


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": str(self.tmp / "cfg"), "APPDATA": str(self.tmp / "cfg")},
            clear=False,
        )
        self.env.start()
        os.environ.pop("JOB_HUNT_WORKSPACE", None)

    def tearDown(self):
        self.env.stop()

    def test_first_run_without_config(self):
        self.assertTrue(onboard.status()["first_run"])

    def test_first_run_with_empty_workspace(self):
        onboard.init(self.tmp / "ws")
        s = onboard.status()
        self.assertTrue(s["first_run"])
        self.assertEqual(s["people"], [])

    def test_person_created_layout(self):
        ws = onboard.init(self.tmp / "ws")
        state, d = onboard.create_person(ws, "Hanna Levi")
        self.assertEqual((state, d.name), ("created", "hanna"))
        for rel in [
            "profile.md", ".person", ".preflight", ".env", "raw", "cvs", "roles",
            "applications.csv", "deferred.csv",
        ]:
            self.assertTrue((d / rel).exists(), rel)
        self.assertFalse(onboard.status()["first_run"])

    def test_first_name_collision_moves_both(self):
        ws = onboard.init(self.tmp / "ws")
        onboard.create_person(ws, "Hanna Levi")
        state, d = onboard.create_person(ws, "Hanna Cohen")
        self.assertEqual(d.name, "hanna_cohen")
        self.assertTrue((ws / "people" / "hanna_levi").is_dir())
        self.assertFalse((ws / "people" / "hanna").exists())

    def test_same_person_is_idempotent(self):
        ws = onboard.init(self.tmp / "ws")
        onboard.create_person(ws, "Hanna Levi")
        self.assertEqual(onboard.create_person(ws, "Hanna Levi")[0], "exists")

    def test_single_word_name_collision_raises(self):
        ws = onboard.init(self.tmp / "ws")
        onboard.create_person(ws, "Hanna")
        with self.assertRaises(ValueError):
            onboard.create_person(ws, "Hanna Levi")
        self.assertTrue((ws / "people" / "hanna").is_dir())

    def test_cli_prints_migration_line_before_created_line(self):
        ws = self.tmp / "ws"
        env = dict(os.environ, JOB_HUNT_WORKSPACE=str(ws))
        subprocess.run(
            [sys.executable, ONBOARD_SCRIPT, "person", "Hanna Levi"],
            env=env, check=True, capture_output=True, text=True,
        )
        result = subprocess.run(
            [sys.executable, ONBOARD_SCRIPT, "person", "Hanna Cohen"],
            env=env, check=True, capture_output=True, text=True,
        )
        lines = result.stdout.splitlines()
        self.assertIn("migrated   people/hanna -> people/hanna_levi   (Hanna Levi)", lines)
        self.assertIn("created   people/hanna_cohen", lines)
        self.assertLess(
            lines.index("migrated   people/hanna -> people/hanna_levi   (Hanna Levi)"),
            lines.index("created   people/hanna_cohen"),
        )

    def test_full_name_rescan_after_first_name_clash(self):
        ws = onboard.init(self.tmp / "ws")
        onboard.create_person(ws, "Hanna Levi")
        onboard.create_person(ws, "Hanna Cohen")
        state, d = onboard.create_person(ws, "hanna levi")
        self.assertEqual((state, d.name), ("exists", "hanna_levi"))
        self.assertFalse((ws / "people" / "hanna").exists())

    def test_third_same_first_name_gets_first_last(self):
        ws = onboard.init(self.tmp / "ws")
        onboard.create_person(ws, "Hanna Levi")
        onboard.create_person(ws, "Hanna Cohen")
        state, d = onboard.create_person(ws, "Hanna Mor")
        self.assertEqual((state, d.name), ("created", "hanna_mor"))
        self.assertFalse((ws / "people" / "hanna").exists())

    def test_no_env_example_left_in_person_dir(self):
        ws = onboard.init(self.tmp / "ws")
        _, d = onboard.create_person(ws, "Hanna Levi")
        self.assertFalse((d / ".env.example").exists())
        self.assertEqual(
            (d / ".env").read_text(encoding="utf-8"),
            (onboard.TEMPLATE / ".env.example").read_text(encoding="utf-8"),
        )

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_env_is_owner_only(self):
        ws = onboard.init(self.tmp / "ws")
        _, d = onboard.create_person(ws, "Hanna Levi")
        self.assertEqual((d / ".env").stat().st_mode & 0o777, 0o600)

    def test_init_expands_tilde(self):
        home = self.tmp / "home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            ws = onboard.init(Path("~/ws"))
        self.assertEqual(ws, (home / "ws").resolve())
        self.assertTrue((home / "ws" / "people").is_dir())


class PermissionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp)}, clear=False)
        self.env.start()
        self.settings = self.tmp / "settings.json"

    def tearDown(self):
        self.env.stop()

    def test_bypass_keeps_other_keys_and_backs_up(self):
        self.settings.write_text('{"model": "opus", "permissions": {"allow": ["Bash(ls)"]}}')
        self.assertEqual(onboard.set_bypass(True), "bypassPermissions")
        data = json.loads(self.settings.read_text())
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"], "defaultMode": "bypassPermissions"})
        self.assertNotIn("skipDangerousModePermissionPrompt", data)
        backup = json.loads((self.tmp / "settings.json.job-hunt.bak").read_text())
        self.assertNotIn("defaultMode", backup["permissions"])

    def test_restore_removes_only_bypass(self):
        self.settings.write_text('{"permissions": {"defaultMode": "bypassPermissions"}}')
        self.assertEqual(onboard.set_bypass(False), "default")
        self.assertEqual(json.loads(self.settings.read_text()), {})
        self.settings.write_text('{"permissions": {"defaultMode": "acceptEdits"}}')
        self.assertEqual(onboard.set_bypass(False), "acceptEdits")

    def test_bypass_creates_missing_file(self):
        onboard.set_bypass(True)
        self.assertEqual(onboard.permission_mode(), "bypassPermissions")

    def test_cli_rejects_non_object_settings(self):
        self.settings.write_text("[]")
        r = subprocess.run([sys.executable, ONBOARD_SCRIPT, "permissions", "bypass"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.settings.read_text(), "[]")


if __name__ == "__main__":
    unittest.main()
