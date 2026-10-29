"""Filesystem locations for bundled assets and per-user data."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"
SOUNDS_DIR = (
    REPO_ROOT / "sounds" / "The Essential Retro Video Game Sound Effects Collection [512 sounds] By Juhani Junkala"
)

APP_NAME = "space-shooter"


def user_data_dir() -> Path:
    """Return (and create) the directory used for settings and high scores.

    ``SPACE_SHOOTER_DATA_DIR`` overrides the platform default, which is handy
    for tests and portable installs.
    """
    override = os.environ.get("SPACE_SHOOTER_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base
