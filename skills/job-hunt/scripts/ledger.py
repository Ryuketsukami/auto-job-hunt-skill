"""The only writer of a job seeker's two CSV ledgers: applications.csv and deferred.csv."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path

import workspace

COLUMNS = [
    "batch", "date", "company", "role", "location", "arrangement", "url",
    "channel", "cv_file", "status", "status_date", "stretch",
    "reason_or_notes", "proof",
]
DEFERRED_COLUMNS = COLUMNS + ["needs"]

STATUS = {
    "sent": "✅ sent",
    "interview": "\U0001f4ac interview",
    "offer": "\U0001f3c6 offer",
    "rejected": "❌ rejected",
    "no-response": "⏳ no-response",
    "dropped": "⛔ dropped",
    "deferred": "⚠️ deferred",
}


class DuplicateRole(Exception):
    pass


def _apps_path(person: Path) -> Path:
    return person / "applications.csv"


def _deferred_path(person: Path) -> Path:
    return person / "deferred.csv"


def _state_path(person: Path) -> Path:
    return person / ".state.json"


def _today_iso() -> str:
    return date_cls.today().isoformat()


def _atomic_write(path: Path, columns: list[str], rows: list[dict]) -> None:
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in columns})
    os.replace(tmp, path)


def _read_rows(path: Path, columns: list[str]) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def init_files(person: Path) -> None:
    person.mkdir(parents=True, exist_ok=True)
    apps = _apps_path(person)
    if not apps.exists():
        _atomic_write(apps, COLUMNS, [])
    deferred = _deferred_path(person)
    if not deferred.exists():
        _atomic_write(deferred, DEFERRED_COLUMNS, [])


def current_batch(person: Path) -> int:
    state = _state_path(person)
    if state.exists():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            if "batch" in data:
                return int(data["batch"])
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    max_batch = 0
    for path, columns in ((_apps_path(person), COLUMNS), (_deferred_path(person), DEFERRED_COLUMNS)):
        for row in _read_rows(path, columns):
            try:
                max_batch = max(max_batch, int(row.get("batch", 0)))
            except ValueError:
                pass
    return max_batch if max_batch else 1


def _save_batch(person: Path, batch: int) -> None:
    state = _state_path(person)
    tmp = state.parent / (state.name + ".tmp")
    tmp.write_text(json.dumps({"batch": batch}), encoding="utf-8")
    os.replace(tmp, state)


def new_batch(person: Path) -> int:
    batch = current_batch(person) + 1
    _save_batch(person, batch)
    return batch


def set_batch(person: Path, batch: int) -> None:
    """Set the batch counter directly, bypassing new_batch()'s +1.

    For migration: seeds .state.json with the highest batch number found in
    imported data, so the next new_batch() continues the numbering instead of
    restarting from 1.
    """
    _save_batch(person, batch)


def write_rows(person: Path, applications: list[dict], deferred: list[dict]) -> None:
    """Bulk-write both ledgers exactly as given, bypassing add()/defer().

    For migration only: writes every row as-is, in order, without the
    duplicate-url check (imported data legitimately contains duplicate and
    empty urls) or batch assignment (imported rows carry their own original
    batch numbers). This is still the only function outside add()/defer()
    that touches the CSVs, so ledger stays the sole writer.
    """
    person.mkdir(parents=True, exist_ok=True)
    _atomic_write(_apps_path(person), COLUMNS, applications)
    _atomic_write(_deferred_path(person), DEFERRED_COLUMNS, deferred)


def _url_exists(person: Path, url: str) -> bool:
    if not url:
        return False
    for path, columns in ((_apps_path(person), COLUMNS), (_deferred_path(person), DEFERRED_COLUMNS)):
        for row in _read_rows(path, columns):
            if row.get("url", "") == url:
                return True
    return False


def _status_icon(status: str) -> str:
    if status not in STATUS:
        raise ValueError(f"unknown status: {status}")
    return STATUS[status]


def _applications_icon(status: str) -> str:
    """Icon for a row in applications.csv; deferred rows only ever live in deferred.csv."""
    if status == "deferred":
        raise ValueError("deferred is not an applications.csv status; use defer()")
    return _status_icon(status)


def add(person: Path, *, company, role, url, status, location="", arrangement="",
        channel="", cv_file="", stretch="", notes="", proof="", date=None) -> dict:
    icon = _applications_icon(status)
    if _url_exists(person, url):
        raise DuplicateRole(f"url already present: {url}")
    row_date = date or _today_iso()
    row = {
        "batch": str(current_batch(person)),
        "date": row_date,
        "company": company,
        "role": role,
        "location": location,
        "arrangement": arrangement,
        "url": url,
        "channel": channel,
        "cv_file": cv_file,
        "status": icon,
        "status_date": row_date,
        "stretch": stretch,
        "reason_or_notes": notes,
        "proof": proof,
    }
    rows = _read_rows(_apps_path(person), COLUMNS)
    rows.append(row)
    _atomic_write(_apps_path(person), COLUMNS, rows)
    return row


def defer(person: Path, *, needs, company, role, url, location="", arrangement="",
          channel="", cv_file="", stretch="", notes="", proof="", date=None, status="deferred") -> dict:
    if _url_exists(person, url):
        raise DuplicateRole(f"url already present: {url}")
    row_date = date or _today_iso()
    row = {
        "batch": str(current_batch(person)),
        "date": row_date,
        "company": company,
        "role": role,
        "location": location,
        "arrangement": arrangement,
        "url": url,
        "channel": channel,
        "cv_file": cv_file,
        "status": STATUS["deferred"],
        "status_date": row_date,
        "stretch": stretch,
        "reason_or_notes": notes,
        "proof": proof,
        "needs": needs,
    }
    rows = _read_rows(_deferred_path(person), DEFERRED_COLUMNS)
    rows.append(row)
    _atomic_write(_deferred_path(person), DEFERRED_COLUMNS, rows)
    return row


def promote(person: Path, url: str, *, status, proof="", cv_file="") -> dict:
    icon = _applications_icon(status)
    deferred_rows = _read_rows(_deferred_path(person), DEFERRED_COLUMNS)
    match = None
    remaining = []
    for row in deferred_rows:
        if row.get("url") == url and match is None:
            match = row
        else:
            remaining.append(row)
    if match is None:
        raise ValueError(f"no deferred row for url: {url}")
    _atomic_write(_deferred_path(person), DEFERRED_COLUMNS, remaining)

    from_batch = match.get("batch", "")
    today = _today_iso()
    notes = match.get("reason_or_notes", "")
    note_suffix = f"deferred from batch {from_batch}"
    notes = f"{notes}; {note_suffix}" if notes else note_suffix
    new_row = {
        "batch": str(current_batch(person)),
        "date": match.get("date", today),
        "company": match.get("company", ""),
        "role": match.get("role", ""),
        "location": match.get("location", ""),
        "arrangement": match.get("arrangement", ""),
        "url": url,
        "channel": match.get("channel", ""),
        "cv_file": cv_file or match.get("cv_file", ""),
        "status": icon,
        "status_date": today,
        "stretch": match.get("stretch", ""),
        "reason_or_notes": notes,
        "proof": proof or match.get("proof", ""),
    }
    rows = _read_rows(_apps_path(person), COLUMNS)
    rows.append(new_row)
    _atomic_write(_apps_path(person), COLUMNS, rows)
    return new_row


def set_status(person: Path, url: str, status: str) -> dict:
    icon = _applications_icon(status)
    rows = _read_rows(_apps_path(person), COLUMNS)
    today = _today_iso()
    updated = None
    for row in rows:
        if row.get("url") == url:
            row["status"] = icon
            row["status_date"] = today
            updated = row
    if updated is None:
        raise ValueError(f"no application row for url: {url}")
    _atomic_write(_apps_path(person), COLUMNS, rows)
    return updated


def age(person: Path, days: int = 30, today: str | None = None) -> int:
    today_dt = datetime.fromisoformat(today).date() if today else date_cls.today()
    rows = _read_rows(_apps_path(person), COLUMNS)
    count = 0
    changed = False
    for row in rows:
        if row.get("status") != STATUS["sent"]:
            continue
        try:
            status_dt = datetime.fromisoformat(row.get("status_date", "")).date()
        except ValueError:
            continue
        if (today_dt - status_dt) > timedelta(days=days):
            row["status"] = STATUS["no-response"]
            row["status_date"] = today_dt.isoformat()
            count += 1
            changed = True
    if changed:
        _atomic_write(_apps_path(person), COLUMNS, rows)
    return count


def find(person: Path, url: str | None = None, company: str | None = None, role: str | None = None) -> list[dict]:
    results = []
    for path, columns in ((_apps_path(person), COLUMNS), (_deferred_path(person), DEFERRED_COLUMNS)):
        for row in _read_rows(path, columns):
            if url is not None and row.get("url") != url:
                continue
            if company is not None and row.get("company", "").lower() != company.lower():
                continue
            if role is not None and row.get("role", "").lower() != role.lower():
                continue
            results.append(row)
    return results


def validate(person: Path) -> list[str]:
    problems = []
    known_icons = set(STATUS.values())
    deferred_icon = STATUS["deferred"]
    for path, columns in ((_apps_path(person), COLUMNS), (_deferred_path(person), DEFERRED_COLUMNS)):
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            raw_rows = list(csv.reader(f))
        if not raw_rows:
            problems.append(f"{path.name}: missing header")
            continue
        header = raw_rows[0]
        if header != columns:
            problems.append(f"{path.name}: wrong header")
        data_rows = raw_rows[1:]
        last_batch = None
        for i, raw in enumerate(data_rows, start=2):
            if len(raw) != len(columns):
                problems.append(f"{path.name}: line {i}: wrong column count")
                continue
            row = dict(zip(columns, raw))
            st = row.get("status")
            if st not in known_icons:
                problems.append(f"{path.name}: line {i}: unknown status '{st}'")
            elif (st == deferred_icon) != (path.name == "deferred.csv"):
                problems.append(f"{path.name}: line {i}: status '{st}' does not belong in {path.name}")
            try:
                batch_num = int(row.get("batch", ""))
            except ValueError:
                problems.append(f"{path.name}: line {i}: invalid batch number")
                continue
            if last_batch is not None and batch_num < last_batch:
                problems.append(f"{path.name}: line {i}: batch numbers not ascending")
            last_batch = batch_num
    return problems


def _resolve_person(args) -> Path:
    ws = workspace.load_workspace()
    if ws is None:
        print("No workspace configured. Run the workspace setup before using ledger.py.", file=sys.stderr)
        sys.exit(2)
    person = workspace.person_dir(ws, args.person)
    if args.cmd != "init" and not person.is_dir():
        print(f"ledger: no person {args.person!r} under {ws / 'people'}; "
              "run onboard.py list to see who is tracked", file=sys.stderr)
        sys.exit(2)
    return person


def _print_row(row: dict) -> None:
    print(json.dumps(row, ensure_ascii=False))


def main(argv=None) -> int:
    workspace.utf8_stdio()
    parser = argparse.ArgumentParser(prog="ledger.py")
    parser.add_argument("cmd", choices=[
        "init", "new-batch", "add", "defer", "promote", "set-status", "age", "find", "validate",
    ])
    parser.add_argument("--person", required=True)
    parser.add_argument("--company", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--url", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--location", default="")
    parser.add_argument("--arrangement", default="")
    parser.add_argument("--channel", default="")
    parser.add_argument("--cv-file", default="")
    parser.add_argument("--stretch", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--proof", default="")
    parser.add_argument("--date", default=None)
    parser.add_argument("--needs", default="")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)

    person = _resolve_person(args)

    try:
        if args.cmd == "init":
            init_files(person)
            print("initialized")
        elif args.cmd == "new-batch":
            print(new_batch(person))
        elif args.cmd == "add":
            row = add(
                person, company=args.company, role=args.role, url=args.url, status=args.status,
                location=args.location, arrangement=args.arrangement, channel=args.channel,
                cv_file=args.cv_file, stretch=args.stretch, notes=args.notes, proof=args.proof,
                date=args.date,
            )
            _print_row(row)
        elif args.cmd == "defer":
            row = defer(
                person, needs=args.needs, company=args.company, role=args.role, url=args.url,
                location=args.location, arrangement=args.arrangement, channel=args.channel,
                cv_file=args.cv_file, stretch=args.stretch, notes=args.notes, proof=args.proof,
                date=args.date,
            )
            _print_row(row)
        elif args.cmd == "promote":
            row = promote(person, args.url, status=args.status, proof=args.proof, cv_file=args.cv_file)
            _print_row(row)
        elif args.cmd == "set-status":
            row = set_status(person, args.url, args.status)
            _print_row(row)
        elif args.cmd == "age":
            print(age(person, days=args.days))
        elif args.cmd == "find":
            for row in find(person, url=args.url, company=args.company or None, role=args.role or None):
                _print_row(row)
        elif args.cmd == "validate":
            problems = validate(person)
            for p in problems:
                print(p)
            if problems:
                return 1
    except DuplicateRole as e:
        print(f"duplicate role: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
