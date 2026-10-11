"""Repository hygiene for the v2 skill: dash-free text, a complete SKILL.md, no stale script names.

Scope: every file git tracks (falls back to a directory walk outside a git checkout).
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "job-hunt"
SKILL_MD = SKILL_DIR / "SKILL.md"
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"

# Built from code points so this file never contains the characters it forbids.
DASHES = {chr(0x2014): "U+2014", chr(0x2013): "U+2013", chr(0x2015): "U+2015"}



def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts)


BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".pyc", ".ico", ".woff", ".woff2"}

STATUSES = [
    "✅ sent",
    "\U0001f4ac interview",
    "\U0001f3c6 offer",
    "❌ rejected",
    "⏳ no-response",
    "⛔ dropped",
    "⚠️ deferred",
]


def text_files():
    for path in tracked_files():
        if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


class RepoHygiene(unittest.TestCase):
    def test_no_dash_characters(self):
        hits = []
        for path, text in text_files():
            for lineno, line in enumerate(text.splitlines(), start=1):
                for char, name in DASHES.items():
                    if char in line:
                        hits.append(f"{path.relative_to(ROOT)}:{lineno}: {name}")
        self.assertEqual(hits, [])

    def test_skill_md_is_short_and_lists_every_status(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 200)
        for status in STATUSES:
            self.assertIn(status, text)

    def test_skill_md_frontmatter_names_job_hunt(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        match = re.match(r"---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(match, "SKILL.md has no frontmatter")
        self.assertRegex(match.group(1), r"(?m)^name: job-hunt$")

    def test_every_reference_named_in_skill_md_exists(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        named = set(re.findall(r"reference/[\w./-]+?\.md", text))
        self.assertTrue(named, "SKILL.md names no reference files")
        missing = sorted(n for n in named if not (SKILL_DIR / n).is_file())
        self.assertEqual(missing, [])

    def test_no_v1_script_names_under_skills(self):
        stale = ("new_person.py", "render_cv.sh")
        hits = [
            f"{path.relative_to(ROOT)}: {name}"
            for path, text in text_files()
            if ROOT / "skills" in path.parents
            for name in stale
            if name in text
        ]
        self.assertEqual(hits, [])

    def test_plugin_manifest_is_valid_json_named_job_hunt(self):
        data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "job-hunt")

    def test_marketplace_manifest_is_valid_json_named_job_hunt(self):
        data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(data["plugins"][0]["name"], "job-hunt")


if __name__ == "__main__":
    unittest.main()
