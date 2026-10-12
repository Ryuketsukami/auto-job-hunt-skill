"""Tests for mailbox.py: the outgoing-credential guard (no network)."""
from __future__ import annotations

import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
import mailbox

CFG = {"MAIL_ADDRESS": "hanna@example.com", "MAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
       "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465"}


def send_args(body: str) -> argparse.Namespace:
    return argparse.Namespace(to="jobs@acme.example", subject="Backend Engineer", body=body,
                              body_file=None, attach=None, dry_run=True)


class SendGuardTests(unittest.TestCase):
    def test_body_with_app_password_is_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            mailbox.cmd_send(CFG, send_args("Hello, abcdefghijklmnop"))
        self.assertIn("credential", str(ctx.exception))
        self.assertNotIn("abcd", str(ctx.exception))

    def test_clean_body_passes_dry_run(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mailbox.cmd_send(CFG, send_args("Hello, CV attached.")), 0)


if __name__ == "__main__":
    unittest.main()
