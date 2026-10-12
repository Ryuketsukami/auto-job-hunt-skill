"""Tests for preflight.py: the CV voice/fingerprint gate, v2 layout."""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
import preflight

CLEAN_CV = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Hanna Levi - CV</title></head>
<body>
<header>
  <h1 class="name">Hanna Levi</h1>
  <div class="contact">
    <a href="mailto:hanna.levi@example.com">hanna.levi@example.com</a>
    <a href="https://linkedin.com/in/hannalevi">linkedin.com/in/hannalevi</a>
  </div>
</header>
<section>
  <h2 class="sec-title">Summary</h2>
  <p>Backend engineer focused on distributed systems and reliability.</p>
</section>
<section>
  <h2 class="sec-title">Skills</h2>
  <div>Python, Go, Postgres, Kafka</div>
</section>
<section>
  <h2 class="sec-title">Experience</h2>
  <div class="entry">
    <div class="entry-title">Senior Backend Engineer, Globex</div>
    <div class="entry-meta">2021-2024</div>
    <ul class="bullets">
      <li>Built a payments reconciliation service handling 2M transactions a day.</li>
      <li>Cut p99 latency from 800ms to 120ms by redesigning the caching layer.</li>
    </ul>
  </div>
</section>
<section>
  <h2 class="sec-title">Education</h2>
  <div class="entry">
    <div class="entry-title">BSc Computer Science, Tel Aviv University</div>
    <div class="entry-meta">2017-2021</div>
  </div>
</section>
</body>
</html>
"""

BANNED_TERM = "TopSecretCorp"


class PreflightWorkspaceTests(unittest.TestCase):
    """Builds a temp people/hanna/ in the v2 layout for each test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.person = self.tmp / "people" / "hanna"
        self.role_dir = self.person / "roles" / "1-acme-ai-engineer"
        self.role_dir.mkdir(parents=True)
        (self.person / ".person").write_text("Hanna Levi\n", encoding="utf-8")
        (self.person / ".preflight").write_text(f"{BANNED_TERM}\n", encoding="utf-8")

    def write_cv(self, content: str) -> Path:
        path = self.role_dir / "cv.html"
        path.write_text(content, encoding="utf-8")
        return path

    def run_check(self, content: str) -> list[preflight.Finding]:
        path = self.write_cv(content)
        person = preflight.person_dir(self.role_dir)
        banned = preflight.read_banned(person)
        names = preflight.read_person_names(person)
        return preflight.check_file(path, banned, names, is_letter=False)

    def errors(self, content: str) -> list[preflight.Finding]:
        return [f for f in self.run_check(content) if f.level == "ERROR"]

    # -- layout plumbing --------------------------------------------------

    def test_person_dir_v2_roles_layout(self):
        self.assertEqual(preflight.person_dir(self.role_dir), self.person)

    def test_person_dir_v1_created_data_layout(self):
        legacy_role = self.person / "created_data" / "acme-ai-engineer"
        legacy_role.mkdir(parents=True)
        self.assertEqual(preflight.person_dir(legacy_role), self.person)

    def test_person_dir_unknown_parent_is_none(self):
        other = self.tmp / "people" / "hanna" / "somewhere-else"
        other.mkdir(parents=True)
        self.assertIsNone(preflight.person_dir(other))

    def test_read_person_names_uses_person_marker_only(self):
        names = preflight.read_person_names(self.person)
        self.assertIn("Hanna Levi", names)

    def test_read_person_names_ignores_profile_heading(self):
        # No profile.md fallback: a person dir with only source_data/profile.md
        # and no .person marker yields no names at all.
        other_person = self.tmp / "people" / "no-marker"
        (other_person / "source_data").mkdir(parents=True)
        (other_person / "source_data" / "profile.md").write_text(
            "# Dana Cohen, profile\n", encoding="utf-8"
        )
        self.assertEqual(preflight.read_person_names(other_person), [])

    # -- clean CV -----------------------------------------------------------

    def test_clean_cv_passes(self):
        findings = self.run_check(CLEAN_CV)
        errors = [f for f in findings if f.level == "ERROR"]
        self.assertEqual(errors, [], [str(f) for f in errors])

    def test_main_exits_zero_on_clean_cv(self):
        self.write_cv(CLEAN_CV)
        self.assertEqual(preflight.main(["preflight", str(self.role_dir)]), 0)

    # -- failing cases, each asserting the specific rule ---------------------

    def test_env_secret_in_form_answers_fails_without_printing_it(self):
        import io, contextlib
        (self.person / ".env").write_text(
            "MAIL_ADDRESS=hanna@example.com\nMAIL_APP_PASSWORD=abcd efgh ijkl mnop\nSMTP_PORT=587\n",
            encoding="utf-8")
        self.write_cv(CLEAN_CV)
        (self.role_dir / "form-answers.txt").write_text("cover: abcdefghijklmnop\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(preflight.main(["preflight", str(self.role_dir)]), 1)
        self.assertIn("credential from the person's .env", out.getvalue())
        self.assertNotIn("abcd", out.getvalue())

    def test_env_only_credential_keys_count(self):
        (self.person / ".env").write_text(
            "MAIL_ADDRESS=hanna.levi@example.com\nSMTP_PORT=587\nSITE_PIN=12\nGREENHOUSE_PASSWORD='s3cret-pw'\n",
            encoding="utf-8")
        self.assertEqual(preflight.read_secrets(self.person), ["s3cret-pw"])
        self.write_cv(CLEAN_CV)
        self.assertEqual(preflight.main(["preflight", str(self.role_dir)]), 0)


    def test_first_person_fails(self):
        bad = CLEAN_CV.replace(
            "Built a payments reconciliation service handling 2M transactions a day.",
            "I built a payments reconciliation service handling 2M transactions a day.",
        )
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("first person" in f.rule for f in errors))

    def test_em_dash_fails(self):
        em_dash = chr(0x2014)
        bad = CLEAN_CV.replace(
            "Cut p99 latency from 800ms to 120ms",
            f"Cut p99 latency{em_dash}from 800ms to 120ms",
        )
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("em dash" in f.rule for f in errors))

    def test_spaced_en_dash_fails(self):
        en_dash = chr(0x2013)
        bad = CLEAN_CV.replace(
            "Cut p99 latency from 800ms to 120ms",
            f"Cut p99 latency {en_dash} from 800ms to 120ms",
        )
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("em dash" in f.rule for f in errors))

    def test_banned_term_fails(self):
        bad = CLEAN_CV.replace("Globex", BANNED_TERM)
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("banned for this person" in f.rule for f in errors))

    def test_unlinked_email_fails(self):
        bad = CLEAN_CV.replace(
            '<a href="mailto:hanna.levi@example.com">hanna.levi@example.com</a>',
            "hanna.levi@example.com",
        )
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("mailto" in f.rule for f in errors))

    def test_name_as_bullet_subject_fails(self):
        bad = CLEAN_CV.replace(
            "Built a payments reconciliation service handling 2M transactions a day.",
            "Hanna built a payments reconciliation service handling 2M transactions a day.",
        )
        errors = self.errors(bad)
        self.assertTrue(errors)
        self.assertTrue(any("own name in the body" in f.rule for f in errors))


CV_TEMPLATE = Path(__file__).resolve().parent.parent / "skills/job-hunt/templates/cv-template.html"

# Invented values for every real placeholder in the shipped template. The template's
# instructional comments mention a literal {{MARKER}}; that one is left as is.
TEMPLATE_VALUES = {
    "FULL_NAME": "Hanna Levi", "HEADLINE": "Backend Engineer",
    "EMAIL": "hanna.levi@example.com", "PHONE": "+1 555 0100",
    "PROFILE_URL": "linkedin.com/in/hanna-levi-example", "LOCATION": "Springfield",
    "SUMMARY": "Ships backend services that stay up, and documents them so others can run them.",
    "SKILL_CATEGORY": "Languages", "SKILL_VALUES": "Python, Go, SQL",
    "JOB_TITLE": "Backend Engineer", "EMPLOYER": "Acme", "DATES": "2021-2024",
    "BULLET": "Built a billing service that processes 1.2M events a day.",
    "PROJECT_NAME": "Ledgerline", "TECH": "Python, Postgres",
    "DESCRIPTION": "Reconciles bank exports against an internal ledger.",
    "URL": "github.com/example/ledgerline",
    "QUALIFICATION": "BSc Computer Science", "INSTITUTION": "State University",
    "CERTIFICATION": "Cloud Practitioner", "ISSUER": "Acme Institute", "YEAR": "2023",
    "LANGUAGE": "English", "LEVEL": "Native",
}


class ShippedTemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.person = self.tmp / "people" / "hanna"
        self.role_dir = self.person / "roles" / "1-acme-backend-engineer"
        self.role_dir.mkdir(parents=True)
        (self.person / ".person").write_text("Hanna Levi\n", encoding="utf-8")

    def filled(self) -> str:
        text = CV_TEMPLATE.read_text(encoding="utf-8")
        return re.sub(r"\{\{(\w+)\}\}", lambda m: TEMPLATE_VALUES.get(m.group(1), m.group(0)), text)

    def test_filled_template_passes(self):
        (self.role_dir / "cv.html").write_text(self.filled(), encoding="utf-8")
        self.assertEqual(preflight.main(["preflight.py", str(self.role_dir)]), 0)

    def test_table_outside_comments_still_fails(self):
        markup = self.filled().replace("</body>", "<table><tr><td>x</td></tr></table>\n</body>")
        (self.role_dir / "cv.html").write_text(markup, encoding="utf-8")
        self.assertEqual(preflight.main(["preflight.py", str(self.role_dir)]), 1)

    def test_marker_outside_comments_still_fails(self):
        markup = self.filled().replace("</body>", "<p>{{SUMMARY}}</p>\n</body>")
        (self.role_dir / "cv.html").write_text(markup, encoding="utf-8")
        self.assertEqual(preflight.main(["preflight.py", str(self.role_dir)]), 1)


if __name__ == "__main__":
    unittest.main()
