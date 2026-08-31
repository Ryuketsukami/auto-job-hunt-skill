#!/usr/bin/env python3
"""Fail a CV that breaks the voice rules, leaks an agent, or reveals a handling instruction.

    python3 scripts/preflight.py people/hanna/created_data/acme-backend-engineer

Exit 0 means every outward artifact in that directory is clean. Exit 1 means at least
one ERROR. Warnings never fail the run but are always printed.

This is not advisory. Run it before every render, and again before anything is sent.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

CONVENTIONAL_SECTIONS = {
    "summary", "profile", "objective",
    "skills", "technical skills", "core skills",
    "experience", "work experience", "professional experience", "employment",
    "projects", "selected projects", "personal projects",
    "education", "certifications", "licenses", "licences",
    "languages", "publications", "awards", "volunteering", "references",
    # German-market CVs use German labels; German ATS parsers recognise these.
    "profil", "kenntnisse", "berufserfahrung", "praktische erfahrung",
    "praktika", "projekte", "ausbildung", "bildungsweg", "zertifikate",
    "weiterbildung", "sprachen",
}

# Phrases that only ever appear when an agent leaked into the document.
# Deliberately excludes genuine skill terms (LLM, MCP, Copilot) — those belong on a CV.
FINGERPRINTS = [
    r"\bas an? (?:AI|language model)\b",
    r"\bI (?:cannot|can't|do not have|don't have) (?:access|the ability)\b",
    r"\b(?:AI|auto|machine)[- ]generated\b",
    r"\bgenerated (?:by|using|with) (?:an? )?(?:AI|assistant|model|agent)\b",
    r"\bbased on the (?:provided|information provided|above) (?:data|information|CV|resume)\b",
    r"\baccording to the provided\b",
    r"\bthis (?:CV|r[ée]sum[ée]|document|letter) (?:was|has been) (?:generated|created|written|tailored)\b",
    r"\bon behalf of\b",
    r"\bplaceholder\b",
    r"\blorem ipsum\b",
    r"\[\s*insert[^\]]{0,40}\]",
    r"\b(?:TODO|TBD|FIXME)\b",
]

# Markers that announce something was left out or presented generously.
DISCLOSURE = [
    r"\((?:omitted|redacted|withheld|stretched|approx\.?|see note|not shown|n/a)\)",
    r"\bdetails? (?:available|furnished) (?:on|upon) request\b",
    r"\bwithheld (?:on|at) request\b",
]

SOFT_DISCLOSURE = [
    r"\broughly \d",
    r"\bapprox(?:\.|imately) \d",
    r"\bsome ?where (?:around|near) \d",
]

THIRD_PERSON_HARD = r"\b(?:he|she|him|his|hers|herself|himself)\b"
THIRD_PERSON_SOFT = r"^\s*(?:they|their|them)\b"
FIRST_PERSON = r"(?:\bI\b|\bI'(?:m|ve|ll|d)\b|\bmy\b|\bme\b|\bmine\b|\bmyself\b)"

STRUCTURAL = [
    (r"<table\b", "a <table> element — ATS parsers flatten or drop tabular data"),
    (r"<img\b", "an <img> element — text inside an image is invisible to a parser"),
    (r"<svg\b", "an <svg> element — same problem as an image"),
    (r"\bwidth:\s*\d+%[^;]*;\s*[^}]*background[^}]*(?:bar|meter|level)", "what looks like a rating bar"),
    (r'class="[^"]*\b(?:rating|skill-bar|proficiency-bar|stars?)\b', "a rating bar or star widget"),
]


class Finding:
    def __init__(self, level: str, path: Path, line: int, rule: str, excerpt: str):
        self.level, self.path, self.line, self.rule, self.excerpt = level, path, line, rule, excerpt

    def __str__(self) -> str:
        return f"{self.level:5} {self.path.name}:{self.line}  {self.rule}\n        …{self.excerpt.strip()}…"


def strip_tags(markup: str) -> str:
    """Drop comments, script, style and tags. Keeps line count stable so numbers stay useful."""
    def blank(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    markup = re.sub(r"<!--.*?-->", blank, markup, flags=re.S)
    markup = re.sub(r"<(script|style)\b.*?</\1>", blank, markup, flags=re.S | re.I)
    markup = re.sub(r"<[^>]+>", " ", markup)
    return html.unescape(markup)


def visible_lines(path: Path) -> list[tuple[int, str]]:
    text = strip_tags(path.read_text(encoding="utf-8", errors="replace"))
    return [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if ln.strip()]


def excerpt_at(line: str, m: re.Match) -> str:
    return line[max(0, m.start() - 40): m.end() + 40]


def person_dir(role_dir: Path) -> Path | None:
    """people/<person>/created_data/<role> -> people/<person>."""
    p = role_dir.resolve()
    if p.parent.name == "created_data":
        return p.parent.parent
    return None


def read_banned(person: Path | None) -> list[str]:
    if person is None:
        return []
    f = person / ".preflight"
    if not f.exists():
        return []
    out = []
    for raw in f.read_text(encoding="utf-8").splitlines():
        term = raw.split("#", 1)[0].strip()
        if term:
            out.append(term)
    return out


def read_person_names(person: Path | None) -> list[str]:
    """Name tokens that must not appear in the body of the person's own CV."""
    if person is None:
        return []
    marker = person / ".person"
    full = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if not full:
        profile = person / "source_data" / "profile.md"
        if profile.exists():
            m = re.search(r"^#\s*(.+?)\s*—", profile.read_text(encoding="utf-8"), re.M)
            full = m.group(1).strip() if m else ""
    if not full:
        return []
    parts = [p for p in re.split(r"\s+", full) if len(p) > 2]
    return sorted(set(parts + [full]), key=len, reverse=True)


URLISH = re.compile(r"\S*(?:@|://|\bwww\.|\.(?:com|net|org|io|dev|ai|co|me|il|uk)\b)\S*", re.I)


def name_legal_lines(markup: str) -> set[int]:
    """Lines where the person's own name belongs: title, name heading, contact block, sign-off."""
    out = set()
    for i, ln in enumerate(markup.splitlines(), 1):
        if re.search(r"<title\b|<h1\b|class=\"(?:name|contact|sign)\"", ln, re.I):
            out.add(i)
    return out


def check_file(path: Path, banned: list[str], names: list[str], is_letter: bool) -> list[Finding]:
    findings: list[Finding] = []
    markup = path.read_text(encoding="utf-8", errors="replace")
    header = name_legal_lines(markup)

    def add(level, line, rule, m, ln):
        findings.append(Finding(level, path, line, rule, excerpt_at(ln, m)))

    # Raw markup checks — these must see the tags.
    for i, ln in enumerate(markup.splitlines(), 1):
        for pat, why in STRUCTURAL:
            m = re.search(pat, ln, re.I)
            if m:
                add("ERROR", i, f"structural: {why}", m, ln)
        m = re.search(r"\{\{[^}]*\}\}", ln)
        if m and not re.match(r"\s*(?:<!--|#|\*)", ln):
            add("ERROR", i, "an unfilled {{TEMPLATE}} marker survived into the artifact", m, ln)
        if not is_letter and not re.match(r"\s*(?:<!--|#|\*)", ln):
            m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", ln)
            if m and "mailto:" not in ln:
                add("ERROR", i, "a visible email that is not a mailto: hyperlink — contact details must be clickable", m, ln)
            m = re.search(r"linkedin\.com/\S+", ln, re.I)
            if m and not re.search(r"href=\"https?://[^\"]*linkedin\.com", ln, re.I):
                add("ERROR", i, "a visible LinkedIn URL that is not an https hyperlink — contact details must be clickable", m, ln)

    # Visible-text checks.
    for i, ln in visible_lines(path):
        m = re.search(THIRD_PERSON_HARD, ln, re.I)
        if m:
            add("ERROR", i, "third person — a CV uses the implied subject: \"Built the pipeline\"", m, ln)

        m = re.search(THIRD_PERSON_SOFT, ln, re.I)
        if m:
            add("ERROR", i, "a bullet opening in third person", m, ln)

        if not is_letter:
            m = re.search(FIRST_PERSON, ln)
            if m:
                add("ERROR", i, "first person — a CV uses the implied subject, not \"I\"", m, ln)

        for pat in FINGERPRINTS:
            m = re.search(pat, ln, re.I)
            if m:
                add("ERROR", i, "an agent fingerprint", m, ln)

        for pat in DISCLOSURE:
            m = re.search(pat, ln, re.I)
            if m:
                add("ERROR", i, "this reveals that something was omitted or presented generously", m, ln)

        for pat in SOFT_DISCLOSURE:
            m = re.search(pat, ln, re.I)
            if m:
                add("WARN", i, "a hedge on a number invites the question it is hiding", m, ln)

        for term in banned:
            m = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", ln, re.I)
            if m:
                add("ERROR", i, f"banned for this person by their .preflight: {term!r}", m, ln)

        if i not in header:
            # A handle or profile URL legitimately contains the name; prose does not.
            prose = URLISH.sub(" ", ln)
            for name in names:
                m = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", prose, re.I)
                if m:
                    add("ERROR", i, "the person's own name in the body — bullets take the implied subject", m, prose)
                    break

        m = re.match(r"\s*([A-Za-z][A-Za-z /&']{2,30})\s*$", ln)
        if m and i not in header:
            heading = m.group(1).strip()
            in_heading_tag = re.search(
                rf'(?:class="sec-title"|<h[23])\b[^>]*>\s*{re.escape(heading)}\s*<', markup, re.I)
            if in_heading_tag and heading.lower() not in CONVENTIONAL_SECTIONS:
                add("WARN", i, f"section heading {heading!r} is not one parsers recognise", m, ln)

    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    role_dir = Path(argv[1])
    if not role_dir.is_dir():
        print(f"preflight: not a directory: {role_dir}", file=sys.stderr)
        return 2

    person = person_dir(role_dir)
    banned = read_banned(person)
    names = read_person_names(person)

    targets = sorted(p for p in role_dir.glob("*.html"))
    if not targets:
        print(f"preflight: no .html artifact in {role_dir}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for path in targets:
        findings += check_file(path, banned, names, is_letter="cover" in path.name.lower())

    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]

    for f in errors + warns:
        print(f)

    checked = ", ".join(p.name for p in targets)
    if errors:
        print(f"\npreflight FAILED — {len(errors)} error(s), {len(warns)} warning(s) in {checked}")
        return 1

    print(f"preflight OK — {checked}"
          + (f" ({len(warns)} warning(s))" if warns else "")
          + (f" · {len(banned)} banned term(s) checked" if banned else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
