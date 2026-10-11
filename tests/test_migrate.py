import csv
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger
import migrate
import workspace
import _config_guard

_CONFIG_SNAPSHOT = None


def setUpModule():
    global _CONFIG_SNAPSHOT
    _CONFIG_SNAPSHOT = _config_guard.snapshot()


def tearDownModule():
    _config_guard.assert_unchanged(_CONFIG_SNAPSHOT)


HANNA_HEADER = [
    "presented", "batch", "company", "role", "location", "arrangement", "url",
    "source", "years_asked", "stretch", "decision", "cv_status", "ats_score",
    "added_technologies", "channel", "date_sent", "proof", "response",
    "response_date", "notes",
]

HANNA_ROWS = [
    # 1: sent, no response -> sent
    ["2026-01-05", "1", "Acme", "AI Engineer", "Berlin", "remote", "https://acme/1",
     "job board", "3", "none", "yes", "sent", "80", "", "email", "2026-01-10", "", "", "", ""],
    # 2: sent, rejected
    ["2026-01-06", "1", "Globex", "Backend Engineer", "Berlin", "hybrid", "https://globex/2",
     "job board", "4", "stretch", "yes", "sent", "75", "", "email", "2026-01-12", "", "Rejected after interview", "2026-02-01", ""],
    # 3: sent, interview
    ["2026-01-07", "1", "Initech", "Data Scientist", "Remote", "remote", "https://initech/3",
     "job board", "5", "none", "yes", "sent", "90", "", "email", "2026-01-15", "", "Interview scheduled", "2026-02-05", ""],
    # 4: dropped by decision no
    ["2026-01-20", "2", "Umbrella", "QA Engineer", "Berlin", "onsite", "https://umbrella/4",
     "job board", "2", "none", "no", "not sent", "", "", "", "", "", "", "", "degree requirement"],
    # 5: dropped by cv_status not sent (decision says yes)
    ["2026-01-21", "2", "Stark", "DevOps", "Berlin", "remote", "https://stark/5",
     "job board", "3", "none", "yes", "not sent", "", "", "", "", "", "", "", "role closed"],
    # 6: dropped by cv_status skipped
    ["2026-01-22", "2", "Wayne", "SRE", "Berlin", "remote", "https://wayne/6",
     "job board", "3", "none", "yes", "skipped", "", "", "", "", "", "", "", ""],
    # 7: deferred, cv_status deferred text
    ["2026-02-01", "3", "Oscorp", "ML Engineer", "Berlin", "remote", "https://oscorp/7",
     "job board", "4", "none", "yes", "deferred (manual send required)", "", "", "", "", "", "", "", ""],
    # 8: deferred, cv_status blocked
    ["2026-02-02", "3", "LexCorp", "Platform Engineer", "Berlin", "remote", "https://lexcorp/8",
     "job board", "4", "none", "yes", "blocked", "", "", "", "", "", "", "", ""],
    # 9: deferred, decision pending
    ["2026-02-03", "3", "Pied Piper", "Infra Engineer", "Berlin", "remote", "https://pp/9",
     "job board", "4", "none", "pending", "", "", "", "", "", "", "", "", ""],
    # 10: other not sent, batch pre-pipeline -> 0
    ["2026-02-04", "pre-pipeline", "Hooli", "Intern", "Berlin", "remote", "https://hooli/10",
     "job board", "1", "none", "auto-yes (scored 8/10)", "tailored 2026-09-10", "", "", "", "", "", "", "", ""],
    # 11: duplicate url of row 1, also sent
    ["2026-01-05", "1", "Acme", "AI Engineer (reposted)", "Berlin", "remote", "https://acme/1",
     "job board", "3", "none", "yes", "sent", "80", "", "email", "2026-01-11", "", "", "", ""],
]

DANIEL_HEADER = ["id"] + HANNA_HEADER
DANIEL_ROWS = [
    ["1", "2026-03-01", "1", "Acme", "Support Engineer", "Berlin", "remote", "https://acme/d1",
     "job board", "2", "none", "yes", "sent", "60", "", "email", "2026-03-01", "", "", "", ""],
    ["2", "2026-03-02", "1", "Globex", "SRE", "Berlin", "remote", "https://globex/d2",
     "job board", "3", "none", "dropped", "none", "", "", "", "", "", "", "", "not a fit"],
]


def _write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def build_v1(root: Path) -> Path:
    people = root / "people"

    hanna = people / "hanna_levi"
    _write_csv(hanna / "applications.csv", HANNA_HEADER, HANNA_ROWS)
    (hanna / "source_data").mkdir(parents=True)
    (hanna / "source_data" / "profile.md").write_text("# Hanna Levi - profile\n\nSome testimony.\n", encoding="utf-8")
    (hanna / "source_data" / "raw").mkdir()
    (hanna / "source_data" / "raw" / "cv.pdf").write_bytes(b"%PDF-1.4 fake")
    (hanna / "source_data" / "raw" / "notes.txt").write_text("raw notes\n", encoding="utf-8")
    (hanna / ".person").write_text("Hanna Levi\n", encoding="utf-8")
    (hanna / ".env").write_text("MAIL_ADDRESS=hanna@example.invalid\n", encoding="utf-8")
    (hanna / ".preflight").write_text("acme internal\n", encoding="utf-8")

    created1 = hanna / "created_data" / "1-acme-ai-engineer"
    created1.mkdir(parents=True)
    (created1 / "cv.html").write_text("<html>acme cv</html>", encoding="utf-8")

    created2 = hanna / "created_data" / "2-globex-backend"
    created2.mkdir(parents=True)
    (created2 / "cv.html").write_text("<html>globex cv</html>", encoding="utf-8")

    sent1 = hanna / "sent_archive" / "1-acme-ai-engineer"
    sent1.mkdir(parents=True)
    (sent1 / "cv.pdf").write_bytes(b"%PDF-1.4 acme-sent")
    (sent1 / "sent.md").write_text("sent to acme\n", encoding="utf-8")
    (sent1 / "cv.html").write_text("<html>acme cv sent-archive copy, should be kept alongside</html>", encoding="utf-8")

    sent2 = hanna / "sent_archive" / "2-globex-backend"
    sent2.mkdir(parents=True)
    (sent2 / "cv.pdf").write_bytes(b"%PDF-1.4 globex-sent")
    (sent2 / "screenshot.png").write_bytes(b"fake-png-bytes")

    daniel = people / "daniel_cruz"
    _write_csv(daniel / "applications.csv", DANIEL_HEADER, DANIEL_ROWS)
    (daniel / "source_data").mkdir(parents=True)
    (daniel / "source_data" / "profile.md").write_text("# Daniel Cruz\n\nSome testimony.\n", encoding="utf-8")
    (daniel / "source_data" / "raw").mkdir()
    (daniel / "source_data" / "raw" / "notes.txt").write_text("daniel raw\n", encoding="utf-8")
    created_d = daniel / "created_data" / "1-acme-support-eng"
    created_d.mkdir(parents=True)
    (created_d / "cv.html").write_text("<html>daniel cv</html>", encoding="utf-8")

    return root


class MigrateMappingTests(unittest.TestCase):
    def setUp(self):
        self.v1 = build_v1(Path(tempfile.mkdtemp()) / "v1")
        self.ws = Path(tempfile.mkdtemp()) / "ws"
        (self.ws / "people").mkdir(parents=True)

    def _rows(self, person_dir, name):
        with open(person_dir / name, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def test_hanna_row_counts_and_statuses(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        summary = migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)

        apps = self._rows(target, "applications.csv")
        deferred = self._rows(target, "deferred.csv")

        self.assertEqual(len(apps), 7)
        self.assertEqual(len(deferred), 4)

        statuses = [r["status"] for r in apps]
        self.assertEqual(statuses.count(ledger.STATUS["sent"]), 2)
        self.assertEqual(statuses.count(ledger.STATUS["rejected"]), 1)
        self.assertEqual(statuses.count(ledger.STATUS["interview"]), 1)
        self.assertEqual(statuses.count(ledger.STATUS["dropped"]), 3)
        self.assertTrue(all(r["status"] == ledger.STATUS["deferred"] for r in deferred))

        self.assertEqual(summary["applications"][ledger.STATUS["sent"]], 2)
        self.assertEqual(summary["applications"][ledger.STATUS["rejected"]], 1)
        self.assertEqual(summary["applications"][ledger.STATUS["interview"]], 1)
        self.assertEqual(summary["applications"][ledger.STATUS["dropped"]], 3)
        self.assertEqual(summary["deferred"], 4)

    def test_status_date_prefers_response_date(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        apps = self._rows(target, "applications.csv")
        rejected = next(r for r in apps if r["status"] == ledger.STATUS["rejected"])
        self.assertEqual(rejected["status_date"], "2026-02-01")
        self.assertEqual(rejected["date"], "2026-01-12")

    def test_needs_text_for_each_deferred_branch(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        deferred = {r["company"]: r for r in self._rows(target, "deferred.csv")}
        self.assertIn("deferred (manual send required)", deferred["Oscorp"]["needs"])
        self.assertIn("blocked", deferred["LexCorp"]["needs"])
        self.assertEqual(deferred["Pied Piper"]["needs"], "your decision: apply or skip")
        self.assertIn("tailored 2026-09-10", deferred["Hooli"]["needs"])
        self.assertIn("auto-yes", deferred["Hooli"]["needs"])

    def test_pre_pipeline_batch_becomes_zero(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        deferred = {r["company"]: r for r in self._rows(target, "deferred.csv")}
        self.assertEqual(deferred["Hooli"]["batch"], "0")

    def test_duplicate_url_kept_in_both_rows(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        apps = self._rows(target, "applications.csv")
        acme_rows = [r for r in apps if r["url"] == "https://acme/1"]
        self.assertEqual(len(acme_rows), 2)

    def test_batch_order_non_decreasing_and_validate_clean(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        self.assertEqual(ledger.validate(target), [])

    def test_state_batch_is_max_migrated(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        self.assertEqual(ledger.current_batch(target), 3)
        self.assertEqual(ledger.new_batch(target), 4)

    def test_leading_id_column_variant(self):
        target = workspace.person_dir(self.ws, "daniel_cruz")
        summary = migrate.migrate_person(self.v1 / "people" / "daniel_cruz", target)
        apps = self._rows(target, "applications.csv")
        self.assertEqual(len(apps), 2)
        self.assertEqual(summary["applications"][ledger.STATUS["sent"]], 1)
        self.assertEqual(summary["applications"][ledger.STATUS["dropped"]], 1)


class MigrateFileCopyTests(unittest.TestCase):
    def setUp(self):
        self.v1 = build_v1(Path(tempfile.mkdtemp()) / "v1")
        self.ws = Path(tempfile.mkdtemp()) / "ws"
        (self.ws / "people").mkdir(parents=True)

    def test_profile_raw_and_markers_copied(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        profile = (target / "profile.md").read_text(encoding="utf-8")
        self.assertTrue(profile.startswith("# Hanna Levi - profile\n"))
        self.assertIn("Some testimony.", profile)
        self.assertTrue((target / "raw" / "cv.pdf").exists())
        self.assertTrue((target / "raw" / "notes.txt").exists())
        self.assertEqual((target / ".person").read_text(encoding="utf-8").strip(), "Hanna Levi")
        self.assertTrue((target / ".env").exists())
        self.assertTrue((target / ".preflight").exists())

    def test_settings_block_inserted_after_title_when_missing(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        lines = (target / "profile.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# Hanna Levi - profile")
        self.assertIn("## Settings", lines)
        self.assertIn("- Send authority:", lines)
        self.assertLess(lines.index("## Settings"), lines.index("Some testimony."))
        self.assertEqual(lines.count("## Settings"), 1)

    def test_existing_settings_block_left_alone(self):
        src = self.v1 / "people/hanna_levi/source_data/profile.md"
        original = "# Hanna Levi - profile\n\n## Settings\n\n- Send authority: ask\n"
        src.write_text(original, encoding="utf-8")
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        self.assertEqual((target / "profile.md").read_text(encoding="utf-8"), original)

    def test_roles_merge_created_and_sent_archive(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        role1 = target / "roles" / "1-acme-ai-engineer"
        self.assertTrue((role1 / "cv.html").exists())
        self.assertTrue((role1 / "cv.pdf").exists())
        self.assertTrue((role1 / "sent.md").exists())
        # name clash: created_data had cv.html, sent_archive also had cv.html -> both kept
        clashed = list(role1.glob("cv*.html"))
        self.assertGreaterEqual(len(clashed), 2)

        role2 = target / "roles" / "2-globex-backend"
        self.assertTrue((role2 / "cv.html").exists())
        self.assertTrue((role2 / "cv.pdf").exists())
        self.assertTrue((role2 / "screenshot.png").exists())

    def test_pdfs_extracted_to_cvs(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        self.assertTrue((target / "cvs" / "1-acme-ai-engineer.pdf").exists())
        self.assertTrue((target / "cvs" / "2-globex-backend.pdf").exists())

    def test_name_derived_from_profile_heading_when_no_person_marker(self):
        target = workspace.person_dir(self.ws, "daniel_cruz")
        migrate.migrate_person(self.v1 / "people" / "daniel_cruz", target)
        self.assertEqual((target / ".person").read_text(encoding="utf-8").strip(), "Daniel Cruz")

    def test_v1_tree_unchanged(self):
        before = (self.v1 / "people/hanna_levi/applications.csv").read_bytes()
        target = workspace.person_dir(self.ws, "hanna_levi")
        migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        after = (self.v1 / "people/hanna_levi/applications.csv").read_bytes()
        self.assertEqual(before, after)
        self.assertTrue((self.v1 / "people/hanna_levi/sent_archive/1-acme-ai-engineer/cv.pdf").exists())

    def test_refuses_when_target_exists(self):
        target = workspace.person_dir(self.ws, "hanna_levi")
        target.mkdir(parents=True)
        (target / "marker.txt").write_text("already here\n", encoding="utf-8")
        with self.assertRaises(migrate.TargetExists):
            migrate.migrate_person(self.v1 / "people" / "hanna_levi", target)
        # untouched
        self.assertEqual(list(target.iterdir()), [target / "marker.txt"])


class MigrateCliTests(unittest.TestCase):
    def setUp(self):
        self.v1 = build_v1(Path(tempfile.mkdtemp()) / "v1")
        self.ws_root = Path(tempfile.mkdtemp()) / "ws"
        # JOB_HUNT_WORKSPACE overrides config-file lookup entirely (see
        # workspace.load_workspace), so the workspace never needs to be
        # persisted via save_workspace() here - which would otherwise write to
        # the real, unpatched ~/.config/job-hunt/config.json on this machine.
        self.env = unittest.mock.patch.dict(os.environ, {"JOB_HUNT_WORKSPACE": str(self.ws_root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_exits_2_without_workspace(self):
        empty_cfg = Path(tempfile.mkdtemp()) / "cfg"
        env = {"XDG_CONFIG_HOME": str(empty_cfg), "APPDATA": str(empty_cfg)}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            rc = migrate.main(["--from", str(self.v1)])
        self.assertEqual(rc, 2)

    def test_migrates_all_people(self):
        rc = migrate.main(["--from", str(self.v1)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.ws_root / "people" / "hanna_levi" / "applications.csv").exists())
        self.assertTrue((self.ws_root / "people" / "daniel_cruz" / "applications.csv").exists())

    def test_migrates_single_person(self):
        rc = migrate.main(["--from", str(self.v1), "--person", "daniel_cruz"])
        self.assertEqual(rc, 0)
        self.assertTrue((self.ws_root / "people" / "daniel_cruz" / "applications.csv").exists())
        self.assertFalse((self.ws_root / "people" / "hanna_levi").exists())

    def test_cli_refuses_existing_target(self):
        (self.ws_root / "people" / "hanna_levi").mkdir(parents=True)
        rc = migrate.main(["--from", str(self.v1), "--person", "hanna_levi"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    import unittest.mock
    unittest.main()
