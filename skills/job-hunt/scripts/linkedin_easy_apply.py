#!/usr/bin/env python3
"""Drive one consented LinkedIn Easy Apply session through Playwright CLI.

`session` reports whether the attached Chrome is signed in to LinkedIn: it prints
LINKEDIN_SESSION signed-in (exit 0), signed-out (exit 3), challenge (exit 4), or
unreachable (exit 5, no browser to drive). Run it before any Easy Apply work.

With no --runner (and no LINKEDIN_RUNNER in the environment) the CLI runs locally,
against the desktop session this process is already in. Pass --runner user@host, or
set LINKEDIN_RUNNER, to drive a remote machine over SSH instead.
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

import workspace


SESSION_DEFAULT = "linkedin-easy-apply"
REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
UPLOAD_SUFFIXES = {".pdf", ".doc", ".docx", ".rtf"}
RUNNER_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$")
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SNAPSHOT_FILE_RE = re.compile(r"\(([^)]*\.yml)\)")
TEXT_LIMIT = 9000
CREATE_NO_WINDOW = 0x08000000

# npx.cmd is a batch file: cmd.exe re-parses its arguments, so an & inside a URL splits the
# command. Calling node on the CLI entry point passes every argument through untouched.
CLI_PREAMBLE = (
    "$ProgressPreference='SilentlyContinue'; "
    "$cli = Join-Path $env:APPDATA 'npm\\node_modules\\@playwright\\cli\\playwright-cli.js'"
)

# The bridge opens its connect page by launching chrome.exe. Over SSH that launch lands in
# session 0, where it can never reach the person's Chrome in their desktop session, so attach
# hangs. Attach therefore runs as a one-shot interactive task in the desktop session, hidden
# behind a WScript launcher so no console window appears.
ATTACH_TEMPLATE = """
$ErrorActionPreference = 'Stop'
{preamble}
$work = Join-Path $env:LOCALAPPDATA 'linkedin-easy-apply'
New-Item -ItemType Directory -Force $work | Out-Null
$log = Join-Path $work 'attach.log'
$cmd = Join-Path $work 'attach.cmd'
$vbs = Join-Path $work 'hidden.vbs'
Remove-Item $log -ErrorAction SilentlyContinue
Set-Content $cmd -Encoding ascii ('@echo off' + "`r`n" + 'node "' + $cli + '" attach --extension=chrome --session={session} > "' + $log + '" 2>&1')
Set-Content $vbs -Encoding ascii 'CreateObject("WScript.Shell").Run Chr(34) & WScript.Arguments(0) & Chr(34), 0, True'
$task = 'LinkedInEasyApplyAttach'
$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('//B //Nologo "' + $vbs + '" "' + $cmd + '"')
$principal = New-ScheduledTaskPrincipal -UserId ((whoami).Trim()) -LogonType Interactive
Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $task
for ($i = 0; $i -lt 45; $i++) {{
  Start-Sleep 2
  if ((Get-ScheduledTask $task).State -ne 'Running') {{ break }}
}}
Unregister-ScheduledTask -TaskName $task -Confirm:$false
if (Test-Path $log) {{ Get-Content $log }}
& node $cli '-s={session}' tab-list
exit $LASTEXITCODE
"""

SNAPSHOT_INLINE = (
    "$m = [regex]::Match($out, '\\(([^)]*\\.yml)\\)'); "
    "if ($m.Success) { $p = $m.Groups[1].Value; "
    "if (-not [IO.Path]::IsPathRooted($p)) { $p = Join-Path $env:USERPROFILE $p }; "
    "'--- snapshot ---'; Get-Content -Raw -Encoding UTF8 $p }"
)


class UsageError(ValueError):
    """Raised when an action would leave the bounded Easy Apply workflow."""


def require_linkedin_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        raise UsageError("goto accepts only an https://linkedin.com URL")
    return value


def require_ref(value: str) -> str:
    if not REF_RE.fullmatch(value):
        raise UsageError("element references must come from the latest Playwright snapshot")
    return value


def require_upload(value: str) -> str:
    if PureWindowsPath(value).suffix.lower() not in UPLOAD_SUFFIXES:
        raise UsageError("upload accepts only a CV document: pdf, doc, docx, or rtf")
    return value


def require_runner(value: str) -> str:
    if not RUNNER_RE.fullmatch(value):
        raise UsageError("runner must have the form user@host")
    return value


def require_session(value: str) -> str:
    if not SESSION_RE.fullmatch(value):
        raise UsageError("session names use letters, digits, hyphen, and underscore only")
    return value


def playwright_args(command: str, args: argparse.Namespace) -> list[str]:
    """CLI arguments after the playwright-cli entry point; attach is handled separately."""
    session = require_session(getattr(args, "session", SESSION_DEFAULT))
    if command == "doctor":
        return ["list", "--all"]
    prefix = [f"-s={session}"]
    if command == "goto":
        return prefix + ["goto", require_linkedin_url(args.url)]
    if command == "snapshot":
        return prefix + ["snapshot"]
    if command == "text":
        script = f"() => (document.querySelector('main') || document.body).innerText.slice(0, {TEXT_LIMIT})"
        return prefix + ["eval", script]
    if command == "screenshot":
        return prefix + ["screenshot", f"--filename={args.filename}"]
    if command == "click":
        return prefix + ["click", require_ref(args.ref)]
    if command == "fill":
        return prefix + ["fill", require_ref(args.ref), args.value]
    if command == "select":
        return prefix + ["select", require_ref(args.ref), args.value]
    if command in ("check", "uncheck"):
        return prefix + [command, require_ref(args.ref)]
    if command == "upload":
        return prefix + ["upload", require_upload(args.path)]
    if command == "press":
        return prefix + ["press", args.key]
    if command == "tabs":
        return prefix + ["tab-list"]
    if command == "detach":
        return prefix + ["detach"]
    raise UsageError(f"unsupported command: {command}")


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def cli_script(cli_args: list[str], inline_snapshot: bool) -> str:
    invocation = "& node $cli " + " ".join(_ps_literal(arg) for arg in cli_args)
    script = f"{CLI_PREAMBLE}; $out = {invocation} 2>&1 | Out-String; $code = $LASTEXITCODE; $out"
    if inline_snapshot:
        script += "; " + SNAPSHOT_INLINE
    return script + "; exit $code"


def attach_script(session: str) -> str:
    return ATTACH_TEMPLATE.format(preamble=CLI_PREAMBLE, session=require_session(session))


def encoded_powershell(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return f"powershell.exe -NoProfile -EncodedCommand {encoded}"


def run_remote(runner: str, script: str) -> int:
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            require_runner(runner),
            encoded_powershell(script),
        ],
        check=False,
        **local_subprocess_kwargs(),
    )
    return completed.returncode


_cli_path_cache: Path | None = None


def local_subprocess_kwargs() -> dict:
    """Extra subprocess.run kwargs so a local child never pops a console on Windows."""
    if os.name == "nt":
        return {"creationflags": CREATE_NO_WINDOW}
    return {}


def cli_path() -> Path:
    """Locate the globally installed Playwright CLI entry point. Cached per process."""
    global _cli_path_cache
    if _cli_path_cache is None:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if npm is None:
            raise UsageError("npm not found on PATH; install Node.js, or pass --runner user@host")
        try:
            completed = subprocess.run(
                [npm, "root", "-g"], capture_output=True, text=True, check=True, **local_subprocess_kwargs()
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise UsageError(f"npm root -g failed: {exc}") from exc
        _cli_path_cache = Path(completed.stdout.strip()) / "@playwright/cli/playwright-cli.js"
    return _cli_path_cache


def local_command(cli_args: list[str]) -> list[str]:
    return ["node", str(cli_path()), *cli_args]


def inline_snapshot_text(output: str) -> str | None:
    """Mirrors SNAPSHOT_INLINE for the local path: find and read the named .yml file."""
    match = SNAPSHOT_FILE_RE.search(output)
    if not match:
        return None
    path = Path(match.group(1))
    if not path.is_absolute():
        path = Path.home() / path
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


SESSION_PROBE_URL = "https://www.linkedin.com/feed/"
SESSION_PROBE = (
    "() => JSON.stringify({url: location.href, title: document.title, "
    "nav: !!document.querySelector('#global-nav, nav.global-nav, [data-test-global-nav]'), "
    "pw: !!document.querySelector('input[type=password]')})"
)
SESSION_EXIT = {"signed-in": 0, "signed-out": 3, "challenge": 4, "unreachable": 5}


def classify_session(output: str) -> str:
    """Read the probe's JSON out of the CLI output. Only a signed-in visitor stays on /feed/:
    logged-out ones land on /login, /uas/login, /authwall, /signup or the guest home page
    ("Log In or Sign Up"); a security check lands on /checkpoint/."""
    match = re.search(r'\{\\?"url\\?".*?\}', output, re.S)
    if not match:
        return "unreachable"
    blob = match.group(0).replace('\\"', '"')
    url = (re.search(r'"url":\s*"([^"]*)"', blob) or [None, ""])[1].lower()
    title = (re.search(r'"title":\s*"([^"]*)"', blob) or [None, ""])[1].lower()
    nav = '"nav":true' in blob.replace(" ", "")
    if "/checkpoint/" in url:
        return "challenge"
    if '"pw":true' in blob.replace(" ", ""):
        # A password box on the page outranks the URL: a sign-in form can render under /feed/.
        return "signed-out"
    if any(k in url for k in ("/login", "/uas/", "/authwall", "/signup")) or "sign in" in title or "log in" in title:
        return "signed-out"
    if "linkedin.com" in url and (nav or "/feed" in url):
        return "signed-in"
    return "signed-out" if "linkedin.com" in url else "unreachable"


def run_capture(runner: str | None, cli_args: list[str]) -> tuple[int, str]:
    if runner:
        script = f"{CLI_PREAMBLE}; $out = & node $cli " + " ".join(_ps_literal(a) for a in cli_args)
        script += " 2>&1 | Out-String; $code = $LASTEXITCODE; $out; exit $code"
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", require_runner(runner),
               encoded_powershell(script)]
    else:
        cmd = local_command(cli_args)
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              check=False, **local_subprocess_kwargs())
    except OSError as exc:
        return 127, str(exc)
    return done.returncode, done.stdout + done.stderr


def session_check(runner: str | None, session: str) -> str:
    prefix = [f"-s={require_session(session)}"]
    code, out = run_capture(runner, prefix + ["goto", SESSION_PROBE_URL])
    if code != 0 or "is not open" in out:
        return "unreachable"
    _, out = run_capture(runner, prefix + ["eval", SESSION_PROBE])
    return classify_session(out)


def run_local(cli_args: list[str], inline_snapshot: bool) -> int:
    completed = subprocess.run(
        local_command(cli_args), capture_output=True, text=True, check=False, **local_subprocess_kwargs()
    )
    output = completed.stdout + completed.stderr
    print(output)
    if inline_snapshot:
        snapshot = inline_snapshot_text(output)
        if snapshot is not None:
            print("--- snapshot ---")
            print(snapshot)
    return completed.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Bounded controller for a consented LinkedIn Easy Apply browser session."
    )
    result.add_argument("--runner", default=os.environ.get("LINKEDIN_RUNNER"))
    result.add_argument("--session", default=SESSION_DEFAULT)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("doctor", "attach", "session", "snapshot", "text", "tabs", "detach"):
        commands.add_parser(name)
    goto = commands.add_parser("goto")
    goto.add_argument("url")
    screenshot = commands.add_parser("screenshot")
    screenshot.add_argument("filename")
    for name in ("click", "check", "uncheck"):
        commands.add_parser(name).add_argument("ref")
    for name in ("fill", "select"):
        sub = commands.add_parser(name)
        sub.add_argument("ref")
        sub.add_argument("value")
    upload = commands.add_parser("upload")
    upload.add_argument("path")
    press = commands.add_parser("press")
    press.add_argument("key")
    return result


def main(argv: list[str] | None = None) -> int:
    workspace.utf8_stdio()
    args = parser().parse_args(argv)
    try:
        if args.command == "session":
            state = session_check(args.runner, args.session)
            print(f"LINKEDIN_SESSION {state}")
            return SESSION_EXIT[state]
        if args.runner:
            require_runner(args.runner)
            if args.command == "attach":
                script = attach_script(args.session)
            else:
                script = cli_script(playwright_args(args.command, args), inline_snapshot=args.command != "doctor")
            return run_remote(args.runner, script)

        # No runner: this process is already in the desktop session, so attach runs
        # the CLI directly instead of the remote scheduled-task dance.
        if args.command == "attach":
            cli_args = ["attach", "--extension=chrome", f"--session={require_session(args.session)}"]
        else:
            cli_args = playwright_args(args.command, args)
        return run_local(cli_args, inline_snapshot=args.command not in ("doctor", "attach"))
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
