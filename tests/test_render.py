"""Tests for render.py: cross-platform HTML-to-one-page-PDF rendering."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
import render

MINIMAL_PDF_TWO_PAGES = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Pages /Kids [2 0 R 3 0 R] /Count 2 >> endobj\n"
    b"%%EOF"
)


class PageCountTests(unittest.TestCase):
    def test_reads_count_from_pdf_bytes(self):
        self.tmp = Path(tempfile.mkdtemp())
        pdf = self.tmp / "doc.pdf"
        pdf.write_bytes(MINIMAL_PDF_TWO_PAGES)
        self.assertEqual(render.page_count(pdf), 2)


class FindBrowserTests(unittest.TestCase):
    def test_none_when_path_empty_and_no_fixed_paths(self):
        with mock.patch.dict(os.environ, {"PATH": "", "JOB_HUNT_BROWSER": ""}, clear=False):
            os.environ.pop("JOB_HUNT_BROWSER", None)
            with mock.patch.object(render, "_fixed_browser_paths", return_value=["/nonexistent/chrome"]):
                self.assertIsNone(render.find_browser())

    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"JOB_HUNT_BROWSER": "/custom/chrome"}):
            self.assertEqual(render.find_browser(), "/custom/chrome")

    def test_path_hit(self):
        os.environ.pop("JOB_HUNT_BROWSER", None)
        with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/chromium" if name == "chromium" else None):
            self.assertEqual(render.find_browser(), "/usr/bin/chromium")


class SafeNameTests(unittest.TestCase):
    def test_transliterates_and_strips(self):
        self.assertEqual(render.safe_name("Jürgen Müller"), "Juergen_Mueller")

    def test_strips_punctuation(self):
        self.assertEqual(render.safe_name("O'Brien, Jr."), "OBrien_Jr")


class RenderErrorNoBrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.person = self.tmp / "people" / "hanna"
        (self.person / "roles" / "1-acme").mkdir(parents=True)
        (self.person / ".person").write_text("Hanna Levi", encoding="utf-8")
        (self.person / "roles" / "1-acme" / "cv.html").write_text("<html><body>hi</body></html>", encoding="utf-8")

    def test_raises_with_install_guidance_when_no_browser(self):
        os.environ.pop("JOB_HUNT_BROWSER", None)
        with mock.patch.object(render, "find_browser", return_value=None):
            with self.assertRaises(render.RenderError) as ctx:
                render.render(self.person / "roles" / "1-acme")
        self.assertIn("Install Google Chrome or Microsoft Edge", str(ctx.exception))
        self.assertIn("JOB_HUNT_BROWSER", str(ctx.exception))

    def test_stale_pdf_removed_before_render(self):
        role = self.person / "roles" / "1-acme"
        stale = role / "Hanna_Levi_CV.pdf"
        stale.write_bytes(MINIMAL_PDF_TWO_PAGES.replace(b"/Count 2", b"/Count 1"))
        with mock.patch.object(render, "find_browser", return_value="/fake/chrome"), \
                mock.patch.object(render, "_run_browser", return_value=None):
            with self.assertRaises(render.RenderError) as ctx:
                render.render(role)
        self.assertIn("produced no output", str(ctx.exception))
        self.assertFalse(stale.exists())

    def test_missing_source_html_raises(self):
        empty_role = self.person / "roles" / "2-empty"
        empty_role.mkdir(parents=True)
        with self.assertRaises(render.RenderError):
            render.render(empty_role)


class MainCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_missing_role_dir_exits_2(self):
        rc = render.main([str(self.tmp / "nope")])
        self.assertEqual(rc, 2)

    def test_missing_html_exits_2(self):
        role_dir = self.tmp / "roles" / "r1"
        role_dir.mkdir(parents=True)
        rc = render.main([str(role_dir)])
        self.assertEqual(rc, 2)


CV_TEMPLATE = Path(__file__).resolve().parent.parent / "skills/job-hunt/templates/cv-template.html"

# Short throwaway values for every {{MARKER}} in the shipped template, so the
# integration test renders the real artifact a person's CV is built from, not a
# synthetic stand-in.
_TEMPLATE_FILLERS = {
    "FULL_NAME": "Hanna Levi",
    "HEADLINE": "Backend Engineer",
    "EMAIL": "hanna@example.com",
    "PHONE": "+1 555 0100",
    "PROFILE_URL": "linkedin.com/in/hannalevi",
    "LOCATION": "Remote",
    "SUMMARY": "Ships backend systems end to end.",
    "SKILL_CATEGORY": "Languages",
    "SKILL_VALUES": "Python, Go",
    "JOB_TITLE": "Engineer",
    "EMPLOYER": "Acme",
    "DATES": "2022 to present",
    "BULLET": "Built the deployment pipeline.",
    "PROJECT_NAME": "Acme CLI",
    "TECH": "Python",
    "DESCRIPTION": "A small internal tool.",
    "URL": "acme.example.com",
    "QUALIFICATION": "BSc Computer Science",
    "INSTITUTION": "Acme University",
    "CERTIFICATION": "Acme Certified Engineer",
    "ISSUER": "Acme Institute",
    "YEAR": "2021",
    "LANGUAGE": "English",
    "LEVEL": "Native",
}


def _filled_template() -> str:
    # The template's own leading comment mentions a literal "{{MARKER}}" as an example,
    # not a real placeholder to fill, so fall back to the token itself for anything
    # not in the filler map rather than failing on it.
    text = CV_TEMPLATE.read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: _TEMPLATE_FILLERS.get(m.group(1), m.group(1)), text)


@unittest.skipUnless(render.find_browser(), "no Chromium-based browser found on this machine")
class RenderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.person_dir = self.tmp / "people" / "hanna"
        self.role_dir = self.person_dir / "roles" / "1-acme-ai-engineer"
        self.role_dir.mkdir(parents=True)
        (self.person_dir / ".person").write_text("Hanna Levi", encoding="utf-8")
        (self.role_dir / "cv.html").write_text(_filled_template(), encoding="utf-8")

    def test_renders_one_page_and_copies_to_cvs(self):
        out = render.render(self.role_dir)
        self.assertTrue(out.is_file())
        self.assertEqual(render.page_count(out), 1)
        self.assertEqual(out.name, "Hanna_Levi_CV.pdf")
        copy = self.person_dir / "cvs" / "1-acme-ai-engineer.pdf"
        self.assertTrue(copy.is_file())


if __name__ == "__main__":
    unittest.main()
