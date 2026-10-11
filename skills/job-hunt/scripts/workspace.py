"""Path resolution and workspace configuration for job-hunt.

Requires Python 3.8+ (onboard.py relies on shutil.copytree(dirs_exist_ok=True)).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 so status icons print on a cp1252 Windows console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def _expand(path) -> Path:
    return Path(path).expanduser().resolve()


def config_path() -> Path:
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return (base / 'job-hunt' / 'config.json').resolve()


def load_workspace() -> Path | None:
    if 'JOB_HUNT_WORKSPACE' in os.environ:
        return _expand(os.environ['JOB_HUNT_WORKSPACE'])

    cfg_path = config_path()
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
            if 'workspace' in data:
                return _expand(data['workspace'])
        except (json.JSONDecodeError, OSError):
            pass
    return None


def save_workspace(path) -> None:
    cfg_path = config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    data = {'workspace': str(_expand(path))}
    cfg_path.write_text(json.dumps(data))


def person_dir(workspace: Path, person: str) -> Path:
    return workspace / 'people' / person
