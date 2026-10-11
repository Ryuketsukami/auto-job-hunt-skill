#!/usr/bin/env python3
"""Drive one consented LinkedIn Easy Apply session through Playwright CLI over SSH."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import PureWindowsPath
import re
import subprocess
import sys
from urllib.parse import urlparse


SESSION_DEFAULT = "linkedin-easy-apply"
REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
UPLOAD_SUFFIXES = {".pdf", ".doc", ".docx", ".rtf"}
RUNNER_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$")
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TEXT_LIMIT = 9000

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
    )
    return completed.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Bounded controller for a consented LinkedIn Easy Apply browser session."
    )
    result.add_argument("--runner", default=os.environ.get("LINKEDIN_RUNNER"))
    result.add_argument("--session", default=SESSION_DEFAULT)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("doctor", "attach", "snapshot", "text", "tabs", "detach"):
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
    args = parser().parse_args(argv)
    if not args.runner:
        print("set LINKEDIN_RUNNER or pass --runner user@host", file=sys.stderr)
        return 2
    try:
        require_runner(args.runner)
        if args.command == "attach":
            script = attach_script(args.session)
        else:
            script = cli_script(playwright_args(args.command, args), inline_snapshot=args.command != "doctor")
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_remote(args.runner, script)


if __name__ == "__main__":
    raise SystemExit(main())
