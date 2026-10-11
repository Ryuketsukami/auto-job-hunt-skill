"""Shared test helper: snapshot the REAL job-hunt config file around a module's tests.

Several job-hunt scripts (workspace.py's save_workspace, and anything that calls it)
write to a per-machine config file outside the repo:
Path.home()/.config/job-hunt/config.json on POSIX (or $XDG_CONFIG_HOME if set),
%APPDATA%/job-hunt/config.json on Windows. A test that forgets to patch
XDG_CONFIG_HOME/APPDATA before calling save_workspace() silently overwrites that
real file. This module gives test modules a cheap way to catch that: snapshot the
real file before the module's tests run, and assert it is unchanged after.

The path is computed from the environment as it stood at interpreter start
(_ORIGINAL_ENV), not from whatever a test has patched os.environ to afterwards, so
the check targets the genuine file even while a test is mid-patch.
"""
from __future__ import annotations

import os
from pathlib import Path

_ORIGINAL_ENV = dict(os.environ)


def real_config_path() -> Path:
    if os.name == "nt":
        base = Path(_ORIGINAL_ENV.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(_ORIGINAL_ENV.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return (base / "job-hunt" / "config.json").resolve()


def snapshot() -> tuple[bool, float | None, bytes | None]:
    path = real_config_path()
    if not path.exists():
        return False, None, None
    stat = path.stat()
    return True, stat.st_mtime, path.read_bytes()


def assert_unchanged(before: tuple[bool, float | None, bytes | None]) -> None:
    after = snapshot()
    if before != after:
        raise AssertionError(
            f"real config file changed during this test module: {real_config_path()} "
            f"(before={before!r}, after={after!r})"
        )
