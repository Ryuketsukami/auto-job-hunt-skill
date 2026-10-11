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


def playwright_args(command: str, args: argparse.Namespace) -> list[str]:
    base = ["npx.cmd", "--no-install", "@playwright/cli"]
    session = getattr(args, "session", SESSION_DEFAULT)
    if command == "doctor":
        return base + ["list", "--all"]
    if command == "attach":
        return base + ["attach", "--extension=chrome", f"--session={session}"]
    prefix = base + [f"-s={session}"]
    if command == "goto":
        return prefix + ["goto", require_linkedin_url(args.url)]
    if command == "snapshot":
        return prefix + ["snapshot"]
    if command == "screenshot":
        return prefix + ["screenshot", f"--filename={args.filename}"]
    if command == "click":
        return prefix + ["click", require_ref(args.ref)]
    if command == "fill":
        return prefix + ["fill", require_ref(args.ref), args.value]
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


def encoded_powershell(argv: list[str]) -> str:
    invocation = "& " + " ".join(_ps_literal(arg) for arg in argv)
    script = f"$ErrorActionPreference='Stop'; {invocation}; exit $LASTEXITCODE"
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return f"powershell.exe -NoProfile -EncodedCommand {encoded}"


def run_remote(runner: str, argv: list[str]) -> int:
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            require_runner(runner),
            encoded_powershell(argv),
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
    for name in ("doctor", "attach", "snapshot", "tabs", "detach"):
        commands.add_parser(name)
    goto = commands.add_parser("goto")
    goto.add_argument("url")
    screenshot = commands.add_parser("screenshot")
    screenshot.add_argument("filename")
    click = commands.add_parser("click")
    click.add_argument("ref")
    fill = commands.add_parser("fill")
    fill.add_argument("ref")
    fill.add_argument("value")
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
        remote_args = playwright_args(args.command, args)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_remote(args.runner, remote_args)


if __name__ == "__main__":
    raise SystemExit(main())
