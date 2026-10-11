import os, json, tempfile, unittest
from pathlib import Path
from unittest import mock
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace
import _config_guard

_CONFIG_SNAPSHOT = None


def setUpModule():
    global _CONFIG_SNAPSHOT
    _CONFIG_SNAPSHOT = _config_guard.snapshot()


def tearDownModule():
    _config_guard.assert_unchanged(_CONFIG_SNAPSHOT)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.tmp / "cfg"), "APPDATA": str(self.tmp / "cfg")}, clear=False)
        self.env.start(); os.environ.pop("JOB_HUNT_WORKSPACE", None)
    def tearDown(self): self.env.stop()

    def test_none_when_unconfigured(self):
        self.assertIsNone(workspace.load_workspace())

    def test_save_then_load(self):
        workspace.save_workspace(self.tmp / "ws")
        self.assertEqual(workspace.load_workspace(), (self.tmp / "ws").resolve())
        self.assertEqual(json.loads(workspace.config_path().read_text())["workspace"], str((self.tmp / "ws").resolve()))

    def test_env_overrides_config(self):
        workspace.save_workspace(self.tmp / "a")
        with mock.patch.dict(os.environ, {"JOB_HUNT_WORKSPACE": str(self.tmp / "b")}):
            self.assertEqual(workspace.load_workspace(), (self.tmp / "b").resolve())

    def test_person_dir(self):
        self.assertEqual(workspace.person_dir(self.tmp, "hanna"), self.tmp / "people" / "hanna")

    def _home(self):
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        return mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}), home

    def test_tilde_expanded_on_save_and_load(self):
        patch, home = self._home()
        with patch:
            workspace.save_workspace("~/x")
            saved = json.loads(workspace.config_path().read_text())["workspace"]
            self.assertEqual(saved, str((home / "x").resolve()))
            self.assertEqual(workspace.load_workspace(), (home / "x").resolve())

    def test_tilde_in_config_value_expanded(self):
        patch, home = self._home()
        with patch:
            workspace.config_path().parent.mkdir(parents=True, exist_ok=True)
            workspace.config_path().write_text(json.dumps({"workspace": "~/y"}))
            self.assertEqual(workspace.load_workspace(), (home / "y").resolve())

    def test_tilde_in_env_var_expanded(self):
        patch, home = self._home()
        with patch, mock.patch.dict(os.environ, {"JOB_HUNT_WORKSPACE": "~/z"}):
            self.assertEqual(workspace.load_workspace(), (home / "z").resolve())
