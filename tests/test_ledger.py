import csv, json, tempfile, unittest
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger
import _config_guard

_CONFIG_SNAPSHOT = None


def setUpModule():
    global _CONFIG_SNAPSHOT
    _CONFIG_SNAPSHOT = _config_guard.snapshot()


def tearDownModule():
    _config_guard.assert_unchanged(_CONFIG_SNAPSHOT)


def make_person(tmp):
    p = tmp / "people" / "hanna"; p.mkdir(parents=True); ledger.init_files(p); return p


class LedgerTests(unittest.TestCase):
    def setUp(self): self.p = make_person(Path(tempfile.mkdtemp()))
    def rows(self, name):
        import csv; return list(csv.DictReader(open(self.p / name, encoding="utf-8-sig")))

    def test_headers_and_bom(self):
        raw = (self.p / "applications.csv").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(self.rows("applications.csv"), [])
        import csv; hdr = next(csv.reader(open(self.p / "deferred.csv", encoding="utf-8-sig")))
        self.assertEqual(hdr, ledger.DEFERRED_COLUMNS)

    def test_add_uses_icon_status_and_current_batch(self):
        ledger.add(self.p, company="Acme", role="AI Engineer", url="https://x/1", status="sent")
        r = self.rows("applications.csv")[0]
        self.assertEqual((r["status"], r["batch"]), ("✅ sent", "1"))

    def test_batches_append_oldest_first(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent")
        self.assertEqual(ledger.new_batch(self.p), 2)
        ledger.add(self.p, company="B", role="r", url="u2", status="dropped", notes="degree required")
        self.assertEqual([r["batch"] for r in self.rows("applications.csv")], ["1", "2"])

    def test_duplicate_url_rejected(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent")
        with self.assertRaises(ledger.DuplicateRole):
            ledger.add(self.p, company="A", role="r", url="u1", status="sent")

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            ledger.add(self.p, company="A", role="r", url="u1", status="maybe")

    def test_defer_then_promote_moves_row(self):
        ledger.defer(self.p, company="A", role="r", url="u1", needs="salary figure")
        self.assertEqual(self.rows("deferred.csv")[0]["status"], "⚠️ deferred")
        ledger.new_batch(self.p)
        ledger.promote(self.p, "u1", status="sent", proof="confirmation shot")
        self.assertEqual(self.rows("deferred.csv"), [])
        r = self.rows("applications.csv")[0]
        self.assertEqual((r["batch"], r["status"]), ("2", "✅ sent"))
        self.assertIn("deferred from batch 1", r["reason_or_notes"])

    def test_set_status_and_age(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent", date="2026-01-01")
        ledger.add(self.p, company="B", role="r", url="u2", status="sent", date="2026-01-01")
        ledger.set_status(self.p, "u2", "interview")
        self.assertEqual(ledger.age(self.p, days=30, today="2026-03-01"), 1)
        st = [r["status"] for r in self.rows("applications.csv")]
        self.assertEqual(st, ["⏳ no-response", "💬 interview"])

    def test_find_matches_company_role_case_insensitive(self):
        ledger.add(self.p, company="Acme", role="AI Engineer", url="u1", status="sent")
        self.assertEqual(len(ledger.find(self.p, company="acme", role="ai engineer")), 1)

    def test_validate_clean(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent")
        self.assertEqual(ledger.validate(self.p), [])

    def test_validate_catches_unknown_status(self):
        with open(self.p / "applications.csv", "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(["1", "2026-01-01", "A", "r", "", "", "u9", "", "", "bogus-status", "2026-01-01", "", "", ""])
        problems = ledger.validate(self.p)
        self.assertTrue(any("status" in p for p in problems))

    def test_validate_catches_bad_column_count(self):
        with open(self.p / "applications.csv", "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(["1", "2026-01-01", "A"])
        problems = ledger.validate(self.p)
        self.assertTrue(any("column" in p for p in problems))

    def test_validate_catches_batch_not_ascending(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent")
        ledger.new_batch(self.p)
        ledger.add(self.p, company="B", role="r", url="u2", status="sent")
        with open(self.p / "applications.csv", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        rows[1], rows[2] = rows[2], rows[1]
        with open(self.p / "applications.csv", "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
        problems = ledger.validate(self.p)
        self.assertTrue(any("batch" in p for p in problems))

    def test_validate_catches_wrong_header(self):
        with open(self.p / "applications.csv", "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerow(["wrong", "header"])
        problems = ledger.validate(self.p)
        self.assertTrue(any("header" in p for p in problems))

    def test_cli_duplicate_add_exits_1(self):
        import subprocess, os
        env = dict(os.environ)
        env["JOB_HUNT_WORKSPACE"] = str(self.p.parent.parent)
        script = str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts/ledger.py")
        args = [sys.executable, script, "add", "--person", "hanna", "--company", "A", "--role", "r", "--url", "u1", "--status", "sent"]
        r1 = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertEqual(r2.returncode, 1)

    def test_add_rejects_deferred(self):
        with self.assertRaises(ValueError):
            ledger.add(self.p, company="A", role="r", url="u1", status="deferred")
        self.assertEqual(self.rows("applications.csv"), [])

    def test_promote_rejects_deferred(self):
        ledger.defer(self.p, company="A", role="r", url="u1", needs="x")
        with self.assertRaises(ValueError):
            ledger.promote(self.p, "u1", status="deferred")
        self.assertEqual(self.rows("applications.csv"), [])
        self.assertEqual(len(self.rows("deferred.csv")), 1)

    def test_set_status_rejects_deferred(self):
        ledger.add(self.p, company="A", role="r", url="u1", status="sent")
        with self.assertRaises(ValueError):
            ledger.set_status(self.p, "u1", "deferred")
        self.assertEqual(self.rows("applications.csv")[0]["status"], "\u2705 sent")

    def test_validate_flags_deferred_in_applications(self):
        with open(self.p / "applications.csv", "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerow(
                ["1", "2026-01-01", "A", "r", "", "", "u9", "", "", ledger.STATUS["deferred"], "2026-01-01", "", "", ""])
        self.assertTrue(any("deferred" in p and "applications.csv" in p for p in ledger.validate(self.p)))

    def test_validate_flags_non_deferred_in_deferred_csv(self):
        with open(self.p / "deferred.csv", "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerow(
                ["1", "2026-01-01", "A", "r", "", "", "u9", "", "", ledger.STATUS["sent"], "2026-01-01", "", "", "", "x"])
        self.assertTrue(any("deferred.csv" in p for p in ledger.validate(self.p)))

    def _cli(self, *args, **env_extra):
        import subprocess, os
        env = dict(os.environ, JOB_HUNT_WORKSPACE=str(self.p.parent.parent), **env_extra)
        script = str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts/ledger.py")
        return subprocess.run([sys.executable, script, *args], env=env, capture_output=True)

    def test_cli_find_with_cp1252_stdout(self):
        ledger.add(self.p, company="Acme", role="r", url="u1", status="interview")
        r = self._cli("find", "--person", "hanna", "--company", "Acme", PYTHONIOENCODING="cp1252")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(ledger.STATUS["interview"], r.stdout.decode("utf-8"))

    def test_cli_unknown_person_exits_2_on_stderr(self):
        r = self._cli("find", "--person", "nobody")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"nobody", r.stderr)
        self.assertNotIn(b"Traceback", r.stderr)
        self.assertEqual(r.stdout, b"")

    def test_cli_errors_go_to_stderr(self):
        r = self._cli("add", "--person", "hanna", "--url", "u1", "--status", "maybe")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b"")
        self.assertIn(b"maybe", r.stderr)


if __name__ == "__main__":
    unittest.main()
