"""User settings persisted as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from space_shooter.config import DIFFICULTY_ORDER
from space_shooter.paths import user_data_dir

SETTINGS_FILE = "settings.json"


@dataclass
class Settings:
    sfx_volume: float = 0.8
    screen_shake: bool = True
    difficulty: str = "normal"
    fullscreen: bool = False
    show_fps: bool = False

    def normalised(self) -> Settings:
        """Return a copy with every field clamped to a valid value."""
        return Settings(
            sfx_volume=min(1.0, max(0.0, float(self.sfx_volume))),
            screen_shake=bool(self.screen_shake),
            difficulty=self.difficulty if self.difficulty in DIFFICULTY_ORDER else "normal",
            fullscreen=bool(self.fullscreen),
            show_fps=bool(self.show_fps),
        )


def settings_path(directory: Path | None = None) -> Path:
    return (directory or user_data_dir()) / SETTINGS_FILE


def load_settings(directory: Path | None = None) -> Settings:
    """Load settings, falling back to defaults on any problem."""
    path = settings_path(directory)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(raw, dict):
        return Settings()
    known = {f.name for f in fields(Settings)}
    data = {k: v for k, v in raw.items() if k in known}
    try:
        return Settings(**data).normalised()
    except (TypeError, ValueError):
        return Settings()


def save_settings(settings: Settings, directory: Path | None = None) -> None:
    path = settings_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings.normalised()), indent=2), encoding="utf-8")
