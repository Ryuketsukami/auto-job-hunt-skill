"""First-run detection and per-person scaffold for job-hunt.

    python3 scripts/onboard.py status
    python3 scripts/onboard.py init <path>
    python3 scripts/onboard.py person "<Full Name>"
    python3 scripts/onboard.py list
    python3 scripts/onboard.py permissions status|bypass|restore

Naming: first name, lowercased -> people/hanna. If that directory is already
taken by a DIFFERENT person, the new person becomes first_last AND the
existing one is migrated to first_last too, so a bare first name never stays
ambiguous. Once any first_* directory exists, every later person with that
first name goes straight to first_last. A full name already tracked anywhere
under people/ resolves to its existing directory.

Creates .env (owner-only on POSIX) from the template if absent, and never
touches an existing one.

permissions: Claude Code accepts bypassPermissions as a default mode only from
its user settings file (project and local settings are ignored for it), so
"bypass" writes permissions.defaultMode there, keeping every other key and a
one-time backup. It never sets skipDangerousModePermissionPrompt: Claude Code's
own confirmation stays the person's to accept.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

import ledger
import workspace

TEMPLATE = workspace.SKILL_DIR / "templates" / "person"


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")


def name_of(person: Path) -> str:
    marker = person / ".person"
    return marker.read_text(encoding="utf-8").strip() if marker.exists() else ""


def candidates(full: str) -> tuple[str, str]:
    parts = [p for p in full.split() if p]
    first = slug(parts[0])
    last = slug(parts[-1]) if len(parts) > 1 else ""
    return first, f"{first}_{last}" if last else first


def status() -> dict:
    ws = workspace.load_workspace()
    if ws is None:
        return {"first_run": True, "workspace": None, "people": []}
    people_dir = ws / "people"
    people = sorted(p.name for p in people_dir.iterdir() if p.is_dir()) if people_dir.is_dir() else []
    return {"first_run": len(people) == 0, "workspace": str(ws), "people": people}


def init(path) -> Path:
    ws = Path(path).expanduser().resolve()
    (ws / "people").mkdir(parents=True, exist_ok=True)
    workspace.save_workspace(ws)
    return ws


def _scaffold(person: Path, full: str) -> None:
    shutil.copytree(TEMPLATE, person, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".env.example"))
    (person / ".person").write_text(full + "\n", encoding="utf-8")

    env = person / ".env"
    if not env.exists():
        env.write_text((TEMPLATE / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        if os.name != "nt":
            os.chmod(env, 0o600)

    profile = person / "profile.md"
    text = profile.read_text(encoding="utf-8")
    text = (
        text.replace("{{NAME}}", full)
        .replace("{{DATE}}", date.today().isoformat())
        .replace("{{N}}", "0")
    )
    profile.write_text(text, encoding="utf-8")

    for sub in ("raw", "cvs", "roles"):
        (person / sub).mkdir(exist_ok=True)

    ledger.init_files(person)


def create_person(ws: Path, full_name: str, on_migrate=None) -> tuple[str, Path]:
    """Create or resolve a person directory under ws/people.

    Returns (state, path) where state is "created" (a new directory was made)
    or "exists" (the person was already tracked at that path).

    On a first-name collision with a DIFFERENT person, the existing person's
    directory is renamed to first_last to free the bare first-name slot, and
    the new person is scaffolded there too (or at first_last directly, if the
    slot was taken). The new person's own returned state is still "created";
    the migration itself is not reflected in the return value, only in the
    directory layout (and the optional on_migrate callback below), so a
    caller that needs to report the move either reads it off the filesystem
    or passes on_migrate.

    on_migrate, if given, is called as on_migrate(old_path, new_path, held_by)
    right after the existing person's directory is renamed, so a CLI can
    print the move before printing the new person's own created/exists line.

    Raises ValueError if the existing person's name has no last word to
    disambiguate with (nothing to rename them to), instead of silently
    renaming their directory onto itself.
    """
    people = ws / "people"
    people.mkdir(parents=True, exist_ok=True)

    dirs = [d for d in people.iterdir() if d.is_dir()]
    for d in dirs:
        if name_of(d).lower() == full_name.lower():
            return "exists", d

    first, first_last = candidates(full_name)
    existing = workspace.person_dir(ws, first)
    first_taken = any(d.name.startswith(first + "_") for d in dirs)

    if existing.is_dir():
        held_by = name_of(existing)
        if not held_by:
            raise ValueError(
                f"people/{first} exists but has no .person marker; "
                f"write the full name into people/{first}/.person, then re-run."
            )

        old_first, old_first_last = candidates(held_by)
        if old_first_last == old_first:
            raise ValueError(
                f"cannot migrate people/{first}: existing person {held_by!r} "
                "has no last word to disambiguate with"
            )

        moved_to = workspace.person_dir(ws, old_first_last)
        if moved_to.exists():
            raise ValueError(f"cannot migrate: {moved_to} already exists")
        existing.rename(moved_to)
        if on_migrate is not None:
            on_migrate(existing, moved_to, held_by)

        target = workspace.person_dir(ws, first_last)
    elif first_taken:
        if first_last == first:
            raise ValueError(
                f"another {first}_* person is tracked; give a last name to disambiguate"
            )
        target = workspace.person_dir(ws, first_last)
    else:
        target = workspace.person_dir(ws, first)

    if target.exists():
        if name_of(target).lower() == full_name.lower():
            return "exists", target
        raise ValueError(f"people/{target.name} is taken by {name_of(target)!r}")

    _scaffold(target, full_name)
    return "created", target


BYPASS = "bypassPermissions"


def claude_settings_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base).expanduser() / "settings.json"


def _read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return data


def _write_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".job-hunt.bak")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def permission_mode() -> str | None:
    return _read_settings(claude_settings_path()).get("permissions", {}).get("defaultMode")


def set_bypass(on: bool) -> str:
    """Turn the user-level bypass default on, or remove it. Returns the new mode."""
    path = claude_settings_path()
    data = _read_settings(path)
    perms = data.setdefault("permissions", {})
    if on:
        perms["defaultMode"] = BYPASS
    elif perms.get("defaultMode") == BYPASS:
        del perms["defaultMode"]
    if not perms:
        del data["permissions"]
    _write_settings(path, data)
    return perms.get("defaultMode", "default")


def _require_workspace() -> Path:
    ws = workspace.load_workspace()
    if ws is None:
        print(
            "No workspace configured. Run: onboard.py init <path>",
            file=sys.stderr,
        )
        sys.exit(2)
    return ws


def main(argv=None) -> int:
    workspace.utf8_stdio()
    parser = argparse.ArgumentParser(prog="onboard.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_init = sub.add_parser("init")
    p_init.add_argument("path")
    p_person = sub.add_parser("person")
    p_person.add_argument("full_name")
    sub.add_parser("list")
    p_perm = sub.add_parser("permissions")
    p_perm.add_argument("action", choices=["status", "bypass", "restore"])
    args = parser.parse_args(argv)

    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0

    if args.cmd == "init":
        ws = init(Path(args.path))
        print(f"workspace initialized: {ws}")
        return 0

    if args.cmd == "person":
        ws = _require_workspace()

        def _print_migration(old: Path, new: Path, held_by: str) -> None:
            print(f"migrated   people/{old.name} -> people/{new.name}   ({held_by})")

        try:
            state, d = create_person(ws, args.full_name, on_migrate=_print_migration)
        except ValueError as e:
            print(f"onboard: {e}", file=sys.stderr)
            return 3
        print(f"{state}   people/{d.name}")
        return 0

    if args.cmd == "list":
        ws = _require_workspace()
        people_dir = ws / "people"
        if people_dir.is_dir():
            for d in sorted(p for p in people_dir.iterdir() if p.is_dir()):
                print(f"{d.name:20} {name_of(d) or '(no .person marker)'}")
        return 0

    if args.cmd == "permissions":
        path = claude_settings_path()
        try:
            if args.action == "status":
                mode = permission_mode() or "default"
            else:
                mode = set_bypass(args.action == "bypass")
        except (ValueError, json.JSONDecodeError) as e:
            print(f"onboard: cannot use {path}: {e}", file=sys.stderr)
            return 3
        print(f"defaultMode {mode}   {path}")
        if mode == BYPASS:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                print("warning: Claude Code refuses bypass mode when run as root", file=sys.stderr)
            print("takes effect the next time Claude Code starts", file=sys.stderr)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
