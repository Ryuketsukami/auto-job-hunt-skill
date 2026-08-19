#!/usr/bin/env python3
"""Read and send mail as a person, using the app password in their .env.

    python3 scripts/mailbox.py --person hanna list -n 20
    python3 scripts/mailbox.py --person hanna search 'FROM "jobs-noreply@linkedin.com"' -n 30
    python3 scripts/mailbox.py --person hanna read <uid>
    python3 scripts/mailbox.py --person hanna send --to careers@acme.com \
        --subject "Backend Engineer application" --body-file note.txt \
        --attach people/hanna/created_data/acme-backend-engineer/Hanna_Levi_CV.pdf

`search` takes IMAP criteria, not Gmail query syntax: FROM "x", SUBJECT "y",
SINCE 01-Aug-2026, UNSEEN. `from:x` will not work. The result limit is -n.

The credential is read from people/<person>/.env and is never printed, echoed,
logged, or included in an error message. If you add output to this file, keep it
that way.
"""
from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import mimetypes
import smtplib
import ssl
import sys
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "IMAP_HOST": "imap.gmail.com", "IMAP_PORT": "993",
    "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "465",
}


def load_env(person: str) -> dict[str, str]:
    env_path = ROOT / "people" / person / ".env"
    if not env_path.exists():
        sys.exit(f"mailbox: no credential at people/{person}/.env — "
                 f"copy templates/person/.env.example and fill it, or hand applications over manually")
    cfg = dict(DEFAULTS)
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    if not cfg.get("MAIL_ADDRESS") or not cfg.get("MAIL_APP_PASSWORD"):
        sys.exit(f"mailbox: people/{person}/.env is missing MAIL_ADDRESS or MAIL_APP_PASSWORD")
    return cfg


def connect_imap(cfg: dict[str, str]) -> imaplib.IMAP4_SSL:
    try:
        M = imaplib.IMAP4_SSL(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]))
        M.login(cfg["MAIL_ADDRESS"], cfg["MAIL_APP_PASSWORD"])
    except imaplib.IMAP4.error:
        # The server echoes the credential in some failure bodies. Never surface it.
        sys.exit("mailbox: IMAP login rejected. Check the address and that the app password "
                 "is still valid; it may have been revoked.")
    M.select("INBOX")
    return M


def decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def show(M: imaplib.IMAP4_SSL, uids: list[bytes], limit: int) -> None:
    for uid in list(reversed(uids))[:limit]:
        ok, data = M.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if ok != "OK" or not data or not isinstance(data[0], tuple):
            continue
        msg = email.message_from_bytes(data[0][1])
        when = decode(msg.get("Date"))
        try:
            when = email.utils.parsedate_to_datetime(when).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        print(f"{uid.decode():>8}  {when:16}  {decode(msg.get('From'))[:42]:42}  {decode(msg.get('Subject'))[:70]}")


def body_of(msg: email.message.Message) -> str:
    if not msg.is_multipart():
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            import re
            raw = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            raw = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.S | re.I)
            return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", " ", raw))
    return ""


def cmd_send(cfg: dict[str, str], args: argparse.Namespace) -> int:
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else (args.body or "")
    if not body.strip():
        sys.exit("mailbox: refusing to send an empty body")

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_ADDRESS"]
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    # Domain from the sending address, not the local hostname — the default leaks the
    # machine name into the raw headers, and headers must not fingerprint the setup.
    msg["Message-ID"] = email.utils.make_msgid(domain=cfg["MAIL_ADDRESS"].rpartition("@")[2])
    msg.set_content(body)

    for path in args.attach or []:
        p = Path(path)
        if not p.is_file():
            sys.exit(f"mailbox: attachment not found: {p}")
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name)

    if args.dry_run:
        print(f"DRY RUN — not sent\n  to:      {args.to}\n  subject: {args.subject}")
        for path in args.attach or []:
            print(f"  attach:  {Path(path).name}")
        print(f"\n{body}")
        return 0

    ctx = ssl.create_default_context()
    port = int(cfg["SMTP_PORT"])
    # 587 is the STARTTLS submission port; anything else gets implicit TLS. Some hosts
    # block outbound 465 (Hetzner does) — set SMTP_PORT=587 in .env if sends time out.
    if port == 587:
        S = smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=30)
    else:
        S = smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, context=ctx, timeout=30)
    with S:
        if port == 587:
            S.starttls(context=ctx)
        try:
            S.login(cfg["MAIL_ADDRESS"], cfg["MAIL_APP_PASSWORD"])
        except smtplib.SMTPAuthenticationError:
            sys.exit("mailbox: SMTP login rejected. The app password may have been revoked.")
        S.send_message(msg)

    # This id is the proof the application left. Record it in applications.csv.
    print(f"sent {msg['Message-ID']}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--person", required=True, help="directory name under people/")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list"); p.add_argument("-n", type=int, default=20)
    p = sub.add_parser("search"); p.add_argument("criteria"); p.add_argument("-n", type=int, default=20)
    p = sub.add_parser("read"); p.add_argument("uid"); p.add_argument("--chars", type=int, default=4000)
    p = sub.add_parser("send")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--attach", action="append")
    p.add_argument("--dry-run", action="store_true")

    args = ap.parse_args(argv[1:])
    cfg = load_env(args.person)

    if args.cmd == "send":
        return cmd_send(cfg, args)

    M = connect_imap(cfg)
    try:
        if args.cmd == "list":
            ok, data = M.uid("search", None, "ALL")
        elif args.cmd == "search":
            ok, data = M.uid("search", None, args.criteria)
        else:
            ok, data = M.uid("fetch", args.uid, "(RFC822)")
            if ok != "OK" or not data or not isinstance(data[0], tuple):
                sys.exit(f"mailbox: no message with uid {args.uid}")
            msg = email.message_from_bytes(data[0][1])
            print(f"From:    {decode(msg.get('From'))}")
            print(f"Date:    {decode(msg.get('Date'))}")
            print(f"Subject: {decode(msg.get('Subject'))}\n")
            print(body_of(msg)[:args.chars])
            return 0

        if ok != "OK":
            sys.exit(f"mailbox: {args.cmd} failed — IMAP criteria, not Gmail syntax "
                     f"(FROM \"x\", SUBJECT \"y\", SINCE 01-Aug-2026, UNSEEN)")
        show(M, data[0].split(), args.n)
        return 0
    finally:
        try:
            M.close(); M.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
