#!/usr/bin/env python3
"""Fail a commit (or a branch) that carries a term from the maintainer's .scrub-names list.

    python3 tools/scrub_check.py                    # staged changes (the pre-commit hook)
    python3 tools/scrub_check.py --history <base>   # every patch in <base>..HEAD

.scrub-names lives at the repo root, is gitignored, and holds one term per line (blank lines
and # comments ignored). Matching is case-insensitive on whole words. Only added lines are
checked. Exit 1 lists file:line for every hit; exit 0 when clean or when no list exists.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

NAMES_FILE = ".scrub-names"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def read_terms(root: Path) -> list[str]:
    f = root / NAMES_FILE
    if not f.exists():
        return []
    terms = []
    for raw in f.read_text(encoding="utf-8").splitlines():
        term = raw.split("#", 1)[0].strip()
        if term:
            terms.append(term)
    return terms


def scan(patch: str, pattern: re.Pattern) -> list[str]:
    """Return 'commit:file:line' (or 'file:line') for each added line matching pattern."""
    hits, commit, path, line = [], "", "", 0
    for ln in patch.splitlines():
        if ln.startswith("commit "):
            commit = ln.split()[1][:12]
        elif ln.startswith("+++ "):
            path = ln[6:] if ln.startswith("+++ b/") else ln[4:]
        elif ln.startswith("@@"):
            m = HUNK.match(ln)
            line = int(m.group(1)) if m else 0
        elif ln.startswith("+"):
            if pattern.search(ln[1:]):
                hits.append(f"{commit + ':' if commit else ''}{path}:{line}")
            line += 1
        elif ln.startswith(" "):
            line += 1
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scrub_check.py")
    parser.add_argument("--history", metavar="BASE", help="scan every patch in BASE..HEAD instead")
    args = parser.parse_args(argv)

    root = Path(git("rev-parse", "--show-toplevel").strip())
    terms = read_terms(root)
    if not terms:
        print(f"scrub_check: no {NAMES_FILE} at {root}; nothing to check", file=sys.stderr)
        return 0
    pattern = re.compile("|".join(rf"(?<!\w){re.escape(t)}(?!\w)" for t in terms), re.I)

    if args.history:
        patch = git("log", "-p", "-U0", "--no-color", "--no-ext-diff", f"{args.history}..HEAD")
    else:
        patch = git("diff", "--cached", "-U0", "--no-color", "--no-ext-diff")

    hits = scan(patch, pattern)
    if hits:
        print("scrub_check: a term from .scrub-names is in:")
        for h in hits:
            print(f"  {h}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
