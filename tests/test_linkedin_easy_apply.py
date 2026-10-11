import argparse
import base64
import unittest

from scripts.linkedin_easy_apply import (
    UsageError,
    attach_script,
    cli_script,
    encoded_powershell,
    playwright_args,
    require_linkedin_url,
    require_runner,
    require_session,
    require_upload,
)


def decode(command: str) -> str:
    return base64.b64decode(command.rsplit(" ", 1)[1]).decode("utf-16le")


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

    def test_rejects_session_that_could_break_out_of_the_script(self):
        self.assertEqual(require_session("role-123"), "role-123")
        for bad in ("a b", "x'; calc", "x&y", ""):
            with self.assertRaises(UsageError):
                require_session(bad)


class CommandTests(unittest.TestCase):
    def test_goto_passes_query_string_untouched(self):
        url = "https://www.linkedin.com/jobs/search/?keywords=AI&location=Israel&f_AL=true"
        args = argparse.Namespace(session="s1", url=url)
        self.assertEqual(playwright_args("goto", args), ["-s=s1", "goto", url])

    def test_cli_runs_node_directly_not_the_npx_batch_shim(self):
        script = cli_script(["-s=s1", "snapshot"], inline_snapshot=True)
        self.assertIn("& node $cli '-s=s1' 'snapshot'", script)
        self.assertNotIn("npx", script)
        self.assertIn("--- snapshot ---", script)

    def test_select_and_check_require_snapshot_refs(self):
        args = argparse.Namespace(session="s1", ref="e12", value="Israel (+972)")
        self.assertEqual(playwright_args("select", args), ["-s=s1", "select", "e12", "Israel (+972)"])
        self.assertEqual(playwright_args("uncheck", args), ["-s=s1", "uncheck", "e12"])
        with self.assertRaises(UsageError):
            playwright_args("check", argparse.Namespace(session="s1", ref="#follow"))

    def test_attach_runs_in_the_desktop_session_without_a_window(self):
        script = attach_script("linkedin-test")
        self.assertIn("-LogonType Interactive", script)
        self.assertIn("wscript.exe", script)
        self.assertIn("Run Chr(34) & WScript.Arguments(0) & Chr(34), 0, True", script)
        self.assertIn("attach --extension=chrome --session=linkedin-test", script)

    def test_powershell_encoding_hides_fill_value_from_process_list(self):
        value = "text with & and % characters"
        command = encoded_powershell(cli_script(["-s=s1", "fill", "e1", value], inline_snapshot=True))
        self.assertNotIn(value, command)
        self.assertIn("'text with & and % characters'", decode(command))


if __name__ == "__main__":
    unittest.main()
