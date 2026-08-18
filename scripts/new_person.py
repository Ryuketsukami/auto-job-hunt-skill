#!/usr/bin/env python3
"""Scaffold a person directory under people/, resolving first-name collisions.

    python3 scripts/new_person.py "Hanna Levi"
    python3 scripts/new_person.py --list

Naming: first name, lowercased -> people/hanna. If that directory is already taken
by a DIFFERENT person, the new person becomes first_last AND the existing one is
migrated to first_last too, so a bare first name never stays ambiguous.

Creates .env from the template if absent, and never touches an existing one.
"""
from __future__ import annotations

import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEOPLE = ROOT / "people"
TPL = ROOT / "templates" / "person"


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


def scaffold(person: Path, full: str) -> None:
    shutil.copytree(TPL, person, dirs_exist_ok=True)
    (person / ".person").write_text(full + "\n", encoding="utf-8")

    env = person / ".env"
    if not env.exists():
        shutil.copy(person / ".env.example", env)

    profile = person / "source_data" / "profile.md"
    text = profile.read_text(encoding="utf-8")
    text = text.replace("{{NAME}}", full).replace("{{DATE}}", date.today().isoformat()).replace("{{N}}", "0")
    profile.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    PEOPLE.mkdir(exist_ok=True)

    if len(argv) == 2 and argv[1] == "--list":
        for d in sorted(p for p in PEOPLE.iterdir() if p.is_dir()):
            print(f"{d.name:20} {name_of(d) or '(no .person marker)'}")
        return 0

    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    full = " ".join(argv[1].split())
    if not full:
        print("new_person: empty name", file=sys.stderr)
        return 2

    first, first_last = candidates(full)
    existing = PEOPLE / first

    if existing.is_dir():
        held_by = name_of(existing)
        if held_by.lower() == full.lower():
            print(f"already tracked: people/{first}")
            return 0

        if not held_by:
            print(f"new_person: people/{first} exists but has no .person marker.\n"
                  f"  Write the full name into people/{first}/.person, then re-run.", file=sys.stderr)
            return 3

        # Both people move to first_last. A bare first name never stays ambiguous.
        moved_to = PEOPLE / candidates(held_by)[1]
        if moved_to.exists():
            print(f"new_person: cannot migrate — {moved_to} already exists", file=sys.stderr)
            return 3
        existing.rename(moved_to)
        print(f"migrated  people/{first} -> people/{moved_to.name}   ({held_by})")

        target = PEOPLE / first_last
    else:
        target = PEOPLE / first

    if target.exists():
        if name_of(target).lower() == full.lower():
            print(f"already tracked: people/{target.name}")
            return 0
        print(f"new_person: people/{target.name} is taken by {name_of(target)!r}", file=sys.stderr)
        return 3

    scaffold(target, full)
    print(f"created   people/{target.name}   ({full})")
    print(f"  source_data/raw/      drop everything they send you here, untouched")
    print(f"  source_data/profile.md  compile the fact base into this — the only source a CV may use")
    print(f"  created_data/         one directory per role")
    print(f"  applications.csv      every role ever presented, and what happened to it")
    print(f"  .env                  their mail credential. Gitignored. Never printed.")
    print(f"  .preflight            terms that must never appear in an outward artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
