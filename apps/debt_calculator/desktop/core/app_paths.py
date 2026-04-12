from __future__ import annotations

import os
import sys
from pathlib import Path

APP_VENDOR = "Lovely1 Solutions LLC"
APP_NAME = "DebtCalculator"


def user_data_dir() -> Path:
    """Return a per-user writable directory for app data."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_VENDOR / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_VENDOR / APP_NAME
    # Linux/other
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_VENDOR / APP_NAME
    return Path.home() / ".local" / "share" / APP_VENDOR / APP_NAME


def project_resource_path(rel: str) -> Path:
    """Find a bundled resource when packaged with PyInstaller."""
    # When frozen, PyInstaller sets sys._MEIPASS
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return Path(__file__).resolve().parents[1] / rel
