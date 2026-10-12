from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/job-hunt/scripts"))
import linkedin_easy_apply
import linkedin_easy_apply as lea
from linkedin_easy_apply import (
    UsageError,
    attach_script,
    cli_script,
    encoded_powershell,
    local_command,
    main,
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


class LocalModeTests(unittest.TestCase):
    def setUp(self):
        self.fake_cli = Path("/fake/playwright-cli.js")
        patcher = mock.patch("linkedin_easy_apply.cli_path", return_value=self.fake_cli)
        self.cli_path_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_local_command_runs_node_on_the_cached_cli_path(self):
        self.assertEqual(
            local_command(["-s=s1", "snapshot"]),
            ["node", str(self.fake_cli), "-s=s1", "snapshot"],
        )

    def test_main_with_no_runner_runs_the_local_command(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            linkedin_easy_apply.os.environ.pop("LINKEDIN_RUNNER", None)
            with mock.patch("subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                code = main(["snapshot"])
        self.assertEqual(code, 0)
        run.assert_called_once()
        command = run.call_args[0][0]
        self.assertEqual(command, ["node", str(self.fake_cli), "-s=linkedin-easy-apply", "snapshot"])

    def test_main_with_runner_still_builds_the_ssh_command(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            code = main(["--runner", "person@runner.example", "snapshot"])
        self.assertEqual(code, 0)
        run.assert_called_once()
        command = run.call_args[0][0]
        self.assertEqual(command[0], "ssh")
        self.assertIn("person@runner.example", command)
        self.cli_path_mock.assert_not_called()

    def test_run_remote_passes_no_window_kwargs(self):
        with mock.patch.object(linkedin_easy_apply, "local_subprocess_kwargs", return_value={"creationflags": 0x08000000}), \
                mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            main(["--runner", "person@runner.example", "snapshot"])
        self.assertEqual(run.call_args.kwargs.get("creationflags"), 0x08000000)

    def test_main_prints_inline_snapshot_for_local_snapshot_command(self):
        tmp = Path(tempfile.mkdtemp())
        snapshot_path = tmp / "snap1.yml"
        snapshot_path.write_text("- role: button\n  name: Submit\n", encoding="utf-8")
        with mock.patch.dict("os.environ", {}, clear=False):
            linkedin_easy_apply.os.environ.pop("LINKEDIN_RUNNER", None)
            with mock.patch("subprocess.run") as run:
                run.return_value = mock.Mock(
                    returncode=0, stdout=f"saved snapshot ({snapshot_path})\n", stderr=""
                )
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["snapshot"])
        self.assertEqual(code, 0)
        printed = buf.getvalue()
        self.assertIn("--- snapshot ---", printed)
        self.assertIn("role: button", printed)
        self.assertIn("name: Submit", printed)



class SessionCheckTests(unittest.TestCase):
    def probe(self, url, title="", nav=False):
        blob = json.dumps(json.dumps({"url": url, "title": title, "nav": nav}))
        return f"### Result\n{blob}\n### Ran Playwright code"

    def test_feed_is_signed_in(self):
        self.assertEqual(lea.classify_session(self.probe("https://www.linkedin.com/feed/", "(2) Feed | LinkedIn")), "signed-in")

    def test_login_redirect_is_signed_out(self):
        for url in ("https://www.linkedin.com/login?session_redirect=x", "https://www.linkedin.com/authwall?x",
                    "https://www.linkedin.com/uas/login"):
            self.assertEqual(lea.classify_session(self.probe(url)), "signed-out", url)

    def test_guest_home_page_is_signed_out(self):
        self.assertEqual(lea.classify_session(self.probe("https://www.linkedin.com/", "LinkedIn: Log In or Sign Up")), "signed-out")

    def test_password_box_under_feed_url_is_signed_out(self):
        blob = json.dumps(json.dumps({"url": "https://www.linkedin.com/feed/", "title": "LinkedIn", "nav": False, "pw": True}))
        self.assertEqual(lea.classify_session(f"### Result\n{blob}"), "signed-out")

    def test_checkpoint_is_challenge(self):
        self.assertEqual(lea.classify_session(self.probe("https://www.linkedin.com/checkpoint/challenge/x")), "challenge")

    def test_no_probe_output_is_unreachable(self):
        self.assertEqual(lea.classify_session("The browser 'x' is not open, please run open first"), "unreachable")

    def test_main_session_exit_codes(self):
        for state, code in lea.SESSION_EXIT.items():
            with mock.patch.object(lea, "session_check", return_value=state), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(lea.main(["session"]), code)
            self.assertIn(f"LINKEDIN_SESSION {state}", out.getvalue())

    def test_session_check_short_circuits_when_browser_is_not_open(self):
        with mock.patch.object(lea, "run_capture", return_value=(1, "The browser is not open")) as rc:
            self.assertEqual(lea.session_check(None, "s1"), "unreachable")
        self.assertEqual(rc.call_count, 1)

if __name__ == "__main__":
    unittest.main()
