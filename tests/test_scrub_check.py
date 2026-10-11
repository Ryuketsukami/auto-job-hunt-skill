"""Tests for tools/scrub_check.py: the maintainer pre-commit personal-data scrub."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / "tools" / "scrub_check.py")
TERM = "Zorblatt Quennings"  # invented; stands in for a real name


def git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                          capture_output=True, text=True).stdout


class ScrubCheckTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        git(self.repo, "init", "-q")
        (self.repo / ".gitignore").write_text(".scrub-names\n", encoding="utf-8")
        (self.repo / ".scrub-names").write_text(f"# names\n{TERM.lower()}\n\n", encoding="utf-8")
        (self.repo / "a.txt").write_text("clean line\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD").strip()

    def run_check(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.repo,
                              capture_output=True, text=True)

    def test_clean_stage_passes(self):
        (self.repo / "a.txt").write_text("clean line\nanother clean line\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_staged_hit_fails_with_file_and_line(self):
        (self.repo / "a.txt").write_text(f"clean line\nCV for {TERM.upper()}\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("a.txt:2", r.stdout)

    def test_unstaged_hit_is_ignored(self):
        (self.repo / "a.txt").write_text(f"{TERM}\n", encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 0)

    def test_history_hit_fails(self):
        (self.repo / "b.txt").write_text(f"one\ntwo {TERM}\n", encoding="utf-8")
        git(self.repo, "add", "b.txt")
        git(self.repo, "commit", "-q", "-m", "leak")
        (self.repo / "b.txt").write_text("one\ntwo\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "scrubbed")
        self.assertEqual(self.run_check().returncode, 0)
        r = self.run_check("--history", self.base)
        self.assertEqual(r.returncode, 1)
        self.assertIn("b.txt:2", r.stdout)

    def test_missing_names_file_passes_with_note(self):
        (self.repo / ".scrub-names").unlink()
        r = self.run_check()
        self.assertEqual(r.returncode, 0)
        self.assertIn(".scrub-names", r.stderr)


if __name__ == "__main__":
    unittest.main()
