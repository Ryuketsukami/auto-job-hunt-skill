import argparse
import base64
import unittest

from scripts.linkedin_easy_apply import (
    UsageError,
    encoded_powershell,
    playwright_args,
    require_linkedin_url,
    require_runner,
    require_upload,
)


class ValidationTests(unittest.TestCase):
    def test_accepts_linkedin_https_url(self):
        url = "https://www.linkedin.com/jobs/view/123"
        self.assertEqual(require_linkedin_url(url), url)

    def test_rejects_non_linkedin_url(self):
        with self.assertRaises(UsageError):
            require_linkedin_url("https://example.com/jobs/123")

    def test_accepts_cv_formats_only(self):
        self.assertEqual(require_upload(r"C:\CVs\Person_CV.pdf"), r"C:\CVs\Person_CV.pdf")
        with self.assertRaises(UsageError):
            require_upload(r"C:\CVs\notes.txt")

    def test_rejects_runner_that_can_be_parsed_as_an_ssh_option(self):
        self.assertEqual(require_runner("person@runner.example"), "person@runner.example")
        with self.assertRaises(UsageError):
            require_runner("-oProxyCommand=bad")


class CommandTests(unittest.TestCase):
    def test_attach_uses_official_bridge(self):
        args = argparse.Namespace(session="linkedin-test")
        self.assertEqual(
            playwright_args("attach", args),
            [
                "npx.cmd",
                "--no-install",
                "@playwright/cli",
                "attach",
                "--extension=chrome",
                "--session=linkedin-test",
            ],
        )

    def test_powershell_encoding_hides_fill_value_from_process_list(self):
        value = "text with & and % characters"
        command = encoded_powershell(["tool.cmd", "fill", value])
        self.assertNotIn(value, command)
        encoded = command.rsplit(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-16le")
        self.assertIn("'text with & and % characters'", decoded)


if __name__ == "__main__":
    unittest.main()
