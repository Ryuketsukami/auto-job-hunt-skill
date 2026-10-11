"""One-time, non-destructive converter from the v1 per-repo layout to a v2 workspace.

    python3 migrate.py --from <v1-repo-root> [--person NAME]

Reads a v1 repo's people/<name>/ directories (applications.csv, source_data/,
created_data/, sent_archive/, .env, .preflight, .person) and writes each
person into the currently configured v2 workspace at people/<name>/. Never
modifies the v1 tree. Refuses (exit 1) if the target person directory already
exists in the workspace, and requires a configured workspace (exit 2) before
doing anything.

Mapping from v1's applications.csv (columns: presented, batch, company, role,
location, arrangement, url, source, years_asked, stretch, decision, cv_status,
ats_score, added_technologies, channel, date_sent, proof, response,
response_date, notes; an optional leading id column is ignored), applied in
this order per row:

1. cv_status starts with "sent" -> applications.csv; response containing
   "reject" -> rejected, containing "interview" -> interview, else sent.
2. decision starts with "no" or "dropped", or cv_status is "not sent" or
   "skipped" -> applications.csv, dropped.
3. cv_status starts with "deferred" or "blocked" -> deferred.csv, needs =
   the cv_status text.
4. decision is "pending" -> deferred.csv, needs = "your decision: apply or
   skip".
5. anything else not sent -> deferred.csv, needs = whichever of cv_status /
   decision is non-empty (joined with " / " if both are).

date = date_sent if set, else presented. status_date = response_date if set,
else that date. Every row is kept, including duplicate or empty urls, since
add()/defer() would reject those one at a time; migrate writes through
ledger.write_rows() instead. Rows are stable-sorted by batch per output file.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import ledger
import workspace

V1_SENT_PREFIX = "sent"
V1_DROP_DECISION_PREFIXES = ("no", "dropped")
V1_DROP_CV_STATUS = {"not sent", "skipped"}
V1_DEFER_CV_STATUS_PREFIXES = ("deferred", "blocked")


class TargetExists(Exception):
    """Raised when the v2 person directory already exists; migration refuses to overwrite it."""


def _batch_of(raw: str | None) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _read_v1_applications(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    with open(csv_path, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _map_row(row: dict) -> tuple[str, dict]:
    """Map one v1 row to ('applications'|'deferred', a ledger-column-shaped dict)."""
    cv_status = (row.get("cv_status") or "").strip()
    decision = (row.get("decision") or "").strip()
    cv_status_l = cv_status.lower()
    decision_l = decision.lower()

    date = row.get("date_sent") or row.get("presented") or ""
    status_date = row.get("response_date") or date

    common = {
        "batch": str(_batch_of(row.get("batch"))),
        "date": date,
        "company": row.get("company", ""),
        "role": row.get("role", ""),
        "location": row.get("location", ""),
        "arrangement": row.get("arrangement", ""),
        "url": row.get("url", ""),
        "channel": row.get("channel", ""),
        "cv_file": "",
        "status_date": status_date,
        "stretch": row.get("stretch", ""),
        "reason_or_notes": row.get("notes", ""),
        "proof": row.get("proof", ""),
    }

    if cv_status_l.startswith(V1_SENT_PREFIX):
        response = (row.get("response") or "").lower()
        if "reject" in response:
            status = "rejected"
        elif "interview" in response:
            status = "interview"
        else:
            status = "sent"
        return "applications", dict(common, status=ledger.STATUS[status])

    if decision_l.startswith(V1_DROP_DECISION_PREFIXES) or cv_status_l in V1_DROP_CV_STATUS:
        return "applications", dict(common, status=ledger.STATUS["dropped"])

    if cv_status_l.startswith(V1_DEFER_CV_STATUS_PREFIXES):
        return "deferred", dict(common, status=ledger.STATUS["deferred"], needs=cv_status)

    if decision_l == "pending":
        return "deferred", dict(common, status=ledger.STATUS["deferred"], needs="your decision: apply or skip")

    parts = [p for p in (cv_status, decision) if p]
    needs = " / ".join(parts) if parts else "needs review"
    return "deferred", dict(common, status=ledger.STATUS["deferred"], needs=needs)


def _map_applications(v1_person: Path) -> tuple[list[dict], list[dict]]:
    applications, deferred = [], []
    for row in _read_v1_applications(v1_person / "applications.csv"):
        bucket, mapped = _map_row(row)
        (applications if bucket == "applications" else deferred).append(mapped)
    applications.sort(key=lambda r: int(r["batch"]))
    deferred.sort(key=lambda r: int(r["batch"]))
    return applications, deferred


def _derive_name(v1_person: Path) -> str:
    marker = v1_person / ".person"
    if marker.exists():
        name = marker.read_text(encoding="utf-8").strip()
        if name:
            return name
    profile = v1_person / "source_data" / "profile.md"
    if profile.exists():
        for line in profile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
                heading = re.split(r" - |:", heading)[0].strip()
                if heading:
                    return heading
    return v1_person.name.replace("_", " ").replace("-", " ").title()


def _copy_merge(src: Path, dst: Path, incoming_tag: str) -> int:
    """Copy every file under src into dst, recreating its relative layout.

    On a name clash with a file already at the destination, the incoming
    (src) file is kept alongside it, suffixed with incoming_tag instead of
    overwriting. Returns the number of files copied.
    """
    if not src.is_dir():
        return 0
    count = 0
    for item in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}-{incoming_tag}{target.suffix}")
            n = 2
            while target.exists():
                target = target.with_name(f"{target.stem}-{n}{target.suffix}")
                n += 1
        shutil.copy2(item, target)
        count += 1
    return count


def _copy_pdfs_to_cvs(sent_archive_dir: Path, role_name: str, cvs_dir: Path) -> int:
    pdfs = sorted(sent_archive_dir.glob("*.pdf")) if sent_archive_dir.is_dir() else []
    if not pdfs:
        return 0
    cvs_dir.mkdir(parents=True, exist_ok=True)
    if len(pdfs) == 1:
        shutil.copy2(pdfs[0], cvs_dir / f"{role_name}.pdf")
    else:
        for pdf in pdfs:
            shutil.copy2(pdf, cvs_dir / f"{role_name}-{pdf.stem}.pdf")
    return len(pdfs)


def _template_settings_block() -> str:
    """The '## Settings' section of the person template, up to the next '## ' heading."""
    text = (workspace.SKILL_DIR / "templates" / "person" / "profile.md").read_text(encoding="utf-8")
    m = re.search(r"^## Settings\n.*?(?=^## )", text, flags=re.S | re.M)
    return m.group(0).rstrip("\n") + "\n"


def _ensure_settings(profile: Path) -> None:
    """v1 profiles predate Settings; insert the template's empty block after the title."""
    text = profile.read_text(encoding="utf-8")
    if re.search(r"^## Settings\s*$", text, flags=re.M):
        return
    lines = text.splitlines(keepends=True)
    at = next((i + 1 for i, ln in enumerate(lines) if ln.startswith("# ")), 0)
    if at and not lines[at - 1].endswith("\n"):
        lines[at - 1] += "\n"
    head, rest = "".join(lines[:at]), "".join(lines[at:]).lstrip("\n")
    block = ("\n" if head else "") + _template_settings_block() + ("\n" + rest if rest else "")
    profile.write_text(head + block, encoding="utf-8")


def migrate_person(v1_person: Path, target: Path) -> dict:
    """Migrate one v1 person directory into the v2 target directory.

    Raises TargetExists without touching anything if target already exists.
    Returns a summary dict: {"applications": Counter(status -> count),
    "deferred": int, "files_copied": int}.
    """
    if target.exists():
        raise TargetExists(f"{target} already exists; refusing to overwrite")

    name = _derive_name(v1_person)
    target.mkdir(parents=True)
    (target / "raw").mkdir()
    (target / "cvs").mkdir()
    (target / "roles").mkdir()

    files_copied = 0

    profile_src = v1_person / "source_data" / "profile.md"
    if profile_src.exists():
        shutil.copy2(profile_src, target / "profile.md")
        _ensure_settings(target / "profile.md")
        files_copied += 1

    raw_src = v1_person / "source_data" / "raw"
    files_copied += _copy_merge(raw_src, target / "raw", incoming_tag="raw")

    created_dirs = v1_person / "created_data"
    if created_dirs.is_dir():
        for d in sorted(p for p in created_dirs.iterdir() if p.is_dir()):
            files_copied += _copy_merge(d, target / "roles" / d.name, incoming_tag="created")

    sent_dirs = v1_person / "sent_archive"
    if sent_dirs.is_dir():
        for d in sorted(p for p in sent_dirs.iterdir() if p.is_dir()):
            files_copied += _copy_merge(d, target / "roles" / d.name, incoming_tag="sent-archive")
            files_copied += _copy_pdfs_to_cvs(d, d.name, target / "cvs")

    for marker in (".env", ".preflight"):
        src = v1_person / marker
        if src.exists():
            shutil.copy2(src, target / marker)
            files_copied += 1

    (target / ".person").write_text(name + "\n", encoding="utf-8")
    files_copied += 1

    applications, deferred = _map_applications(v1_person)
    ledger.write_rows(target, applications, deferred)

    batches = [int(r["batch"]) for r in applications + deferred]
    if batches:
        ledger.set_batch(target, max(batches))

    return {
        "applications": Counter(r["status"] for r in applications),
        "deferred": len(deferred),
        "files_copied": files_copied,
    }


def _print_summary(name: str, summary: dict) -> None:
    print(f"{name}:")
    for status, count in sorted(summary["applications"].items()):
        print(f"  applications.csv  {status}: {count}")
    print(f"  deferred.csv      rows: {summary['deferred']}")
    print(f"  files copied: {summary['files_copied']}")


def main(argv=None) -> int:
    workspace.utf8_stdio()
    parser = argparse.ArgumentParser(prog="migrate.py")
    parser.add_argument("--from", dest="v1_root", required=True)
    parser.add_argument("--person", default=None)
    args = parser.parse_args(argv)

    ws = workspace.load_workspace()
    if ws is None:
        print("No workspace configured. Run: onboard.py init <path>", file=sys.stderr)
        return 2

    v1_root = Path(args.v1_root).resolve()
    v1_people_dir = v1_root / "people"
    if not v1_people_dir.is_dir():
        print(f"migrate: no people/ directory found under {v1_root}", file=sys.stderr)
        return 1

    if args.person:
        names = [args.person]
    else:
        names = sorted(p.name for p in v1_people_dir.iterdir() if p.is_dir())

    for name in names:
        v1_person = v1_people_dir / name
        if not v1_person.is_dir():
            print(f"migrate: no such person {name!r} under {v1_people_dir}", file=sys.stderr)
            return 1
        target = workspace.person_dir(ws, name)
        try:
            summary = migrate_person(v1_person, target)
        except TargetExists as e:
            print(f"migrate: {e}", file=sys.stderr)
            return 1
        _print_summary(name, summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
