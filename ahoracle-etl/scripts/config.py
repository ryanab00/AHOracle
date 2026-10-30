
"""Configuration and WoW install detection for AHOracle Watcher.

Config is stored at ~/.ahoracle/config.json (or %USERPROFILE%\\.ahoracle
on Windows).  Handles first-run WoW auto-detection by checking:
  1. Common install paths on every drive letter (Windows)
  2. Blizzard's registry keys (Windows)
  3. Home-relative paths (macOS / Linux / Wine)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


APP_DIR     = Path.home() / ".ahoracle"
CONFIG_FILE = APP_DIR / "config.json"

SV_FILENAME = "AHOracle.lua"

DEFAULTS = {
    "sv_file":        None,
    "db_url":         "sqlite:///ahoracle.db",
    "poll_seconds":   2,
    "stable_seconds": 3,
}


# ─── Config I/O ──────────────────────────────────────────────────────────

def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ─── WoW install detection ───────────────────────────────────────────────

WOW_INSTALL_HINTS = [
    # Windows, most common first
    r"C:\Program Files (x86)\World of Warcraft",
    r"C:\Program Files\World of Warcraft",
    r"C:\World of Warcraft",
    r"C:\Games\World of Warcraft",
    r"C:\Battle.net\World of Warcraft",
    r"D:\World of Warcraft",
    r"D:\Games\World of Warcraft",
    r"E:\World of Warcraft",
    r"E:\Games\World of Warcraft",
    # macOS
    "/Applications/World of Warcraft",
    # Linux / Wine
    "~/.wine/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files/World of Warcraft",
    "~/Games/World of Warcraft",
]

CLIENT_FOLDERS = ["_classic_era_", "_classic_", "_retail_", "_ptr_"]


def _candidates_from_hint(hint: str) -> list[Path]:
    base = Path(os.path.expanduser(hint))
    if not base.exists():
        return []

    found: list[Path] = []
    for client in CLIENT_FOLDERS:
        acct_root = base / client / "WTF" / "Account"
        if not acct_root.exists():
            continue
        try:
            for account in acct_root.iterdir():
                sv = account / "SavedVariables" / SV_FILENAME
                if sv.exists():
                    found.append(sv)
        except (PermissionError, OSError):
            continue
    return found


def _candidates_from_registry() -> list[Path]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except ImportError:
        return []

    found: list[Path] = []
    keys = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Blizzard Entertainment\World of Warcraft"),
    ]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, "InstallPath")
                if value:
                    found.extend(_candidates_from_hint(value))
        except (FileNotFoundError, OSError):
            continue
    return found


def find_sv_file() -> Path | None:
    """Return the most recently modified AHOracle.lua, or None."""
    found: list[Path] = []
    for hint in WOW_INSTALL_HINTS:
        found.extend(_candidates_from_hint(hint))
    found.extend(_candidates_from_registry())

    if not found:
        return None

    # Dedupe by resolved path, pick most recently modified
    unique = {str(p.resolve()): p for p in found}
    return max(unique.values(), key=lambda p: p.stat().st_mtime)


def is_valid_sv_file(path) -> bool:
    p = Path(path)
    return p.is_file() and p.name == SV_FILENAME