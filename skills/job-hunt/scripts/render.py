"""Render a role directory's cv.html (or cover-letter.html) to a one-page PDF.

    python3 render.py <role-dir>
    python3 render.py <role-dir> --cover

Ports the behaviour of the v1 bash renderer: the same browser flags, the
same output naming from the person's `.person` file, and the same byte-level
`/Count` read of the produced PDF (no pdfinfo/qpdf dependency). Runs on Linux,
macOS and Windows: finds a Chromium-based browser via PATH first, then a short
list of fixed install locations, and never pops a visible window on Windows.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import workspace

#: shutil.which names tried, in order, before the fixed paths.
BROWSER_NAMES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "msedge",
    "microsoft-edge",
    "chrome",
)

RENDER_TIMEOUT_S = 120

# Explicit transliteration before stripping, mirroring v1's sed pipeline: a plain
# strip would delete "u" with no trace of the umlaut rather than writing "ue".
_TRANSLITERATE = {
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
    "é": "e", "è": "e", "ê": "e", "á": "a", "à": "a", "í": "i", "ó": "o",
    "ú": "u", "ñ": "n", "ç": "c",
}


class RenderError(Exception):
    """Raised when no browser can be found, or a CV does not render to one page."""


def _fixed_browser_paths() -> list[str]:
    """Fixed install locations tried after PATH, in order. A function so tests can patch it."""
    paths: list[str] = []
    if os.name == "nt":
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env_var)
            if not base:
                continue
            paths.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
            paths.append(str(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"))
    elif sys.platform == "darwin":
        paths.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        paths.append("/Applications/Chromium.app/Contents/MacOS/Chromium")
        paths.append("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    return paths


def find_browser() -> str | None:
    """Find a Chromium-based browser. Honours JOB_HUNT_BROWSER first."""
    env_browser = os.environ.get("JOB_HUNT_BROWSER")
    if env_browser:
        return env_browser

    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found

    for path in _fixed_browser_paths():
        if Path(path).is_file():
            return path

    return None


def page_count(pdf: Path) -> int:
    """Read /Type /Pages ... /Count N out of the PDF bytes, no pdfinfo/qpdf needed."""
    data = pdf.read_bytes()
    matches = re.findall(rb"/Count\s+(\d+)", data)
    if not matches:
        raise RenderError(f"render: could not read a page count from {pdf}")
    # The Pages tree root is written last by Chrome's PDF writer, and its /Count is
    # the true total; earlier matches belong to nested /Pages nodes with partial counts.
    return int(matches[-1])


def safe_name(name: str) -> str:
    """Build the filename-safe person name v1 used for the output PDF."""
    transliterated = "".join(_TRANSLITERATE.get(ch, ch) for ch in name)
    normalized = unicodedata.normalize("NFKD", transliterated)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    underscored = stripped.replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_-]", "", underscored)


def _person_name(role_dir: Path) -> str:
    person_dir = role_dir.parent.parent
    marker = person_dir / ".person"
    if marker.exists():
        first_line = marker.read_text(encoding="utf-8").splitlines()
        if first_line:
            return first_line[0].strip()
    return person_dir.name


def _run_browser(browser: str, src: Path, out: Path) -> None:
    cmd = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out}",
        src.as_uri(),
    ]
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=RENDER_TIMEOUT_S,
            **kwargs,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"render: browser timed out after {RENDER_TIMEOUT_S}s rendering {src}") from exc


def render(role_dir: Path, cover: bool = False) -> Path:
    """Render role_dir/cv.html (or cover-letter.html) to a PDF in role_dir.

    Copies the CV (not the cover letter) into people/<person>/cvs/<role-dir>.pdf.
    Raises RenderError if no browser is found, or if a CV renders to other than
    one page.
    """
    role_dir = role_dir.resolve()
    src = role_dir / ("cover-letter.html" if cover else "cv.html")
    if not src.is_file():
        raise RenderError(f"render: missing {src}")

    browser = find_browser()
    if browser is None:
        raise RenderError(
            "render: no browser found. Install Google Chrome or Microsoft Edge, "
            "or set JOB_HUNT_BROWSER to a Chromium-based browser path"
        )

    suffix = "Cover_Letter" if cover else "CV"
    name = safe_name(_person_name(role_dir))
    out = role_dir / f"{name}_{suffix}.pdf"
    # A stale PDF from an earlier run must never pass for this render's output.
    out.unlink(missing_ok=True)

    _run_browser(browser, src, out)

    if not out.is_file() or out.stat().st_size == 0:
        raise RenderError(f"render: produced no output at {out}")

    pages = page_count(out)
    print(f"pages {pages}")
    print(f"wrote {out}")

    if not cover and pages != 1:
        raise RenderError(
            "render: NOT one page. Cut the least-relevant filler, never the "
            "protected evidence, and re-run."
        )

    if not cover:
        cvs_dir = role_dir.parent.parent / "cvs"
        cvs_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, cvs_dir / f"{role_dir.name}.pdf")

    return out


def main(argv: list[str] | None = None) -> int:
    workspace.utf8_stdio()
    parser = argparse.ArgumentParser(description="Render a role directory's CV or cover letter to PDF.")
    parser.add_argument("role_dir", type=Path, help="people/<person>/roles/<role-dir>")
    parser.add_argument("--cover", action="store_true", help="render cover-letter.html instead of cv.html")
    args = parser.parse_args(argv)

    if not args.role_dir.is_dir():
        print(f"render: not a directory: {args.role_dir}", file=sys.stderr)
        return 2

    src = args.role_dir / ("cover-letter.html" if args.cover else "cv.html")
    if not src.is_file():
        print(f"render: missing {src}", file=sys.stderr)
        return 2

    try:
        render(args.role_dir, cover=args.cover)
    except RenderError as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
