"""Top-ten high score table with JSON persistence."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from space_shooter.paths import REPO_ROOT, user_data_dir

SCORES_FILE = "high_scores.json"
LEGACY_FILE = REPO_ROOT / "high_scores.txt"
MAX_ENTRIES = 10
DEFAULT_NAME = "AAA"


@dataclass(frozen=True)
class ScoreEntry:
    name: str
    score: int
    wave: int
    difficulty: str = "normal"
    timestamp: float = 0.0


class HighScoreTable:
    def __init__(self, entries: list[ScoreEntry] | None = None) -> None:
        self.entries: list[ScoreEntry] = []
        for entry in entries or []:
            self._insert(entry)

    # -- queries -------------------------------------------------------------
    @property
    def best(self) -> int:
        return self.entries[0].score if self.entries else 0

    def qualifies(self, score: int) -> bool:
        if score <= 0:
            return False
        if len(self.entries) < MAX_ENTRIES:
            return True
        return score > self.entries[-1].score

    def rank_of(self, score: int) -> int | None:
        """1-based rank the score would take, or None if it would not chart."""
        if not self.qualifies(score):
            return None
        return sum(1 for e in self.entries if e.score >= score) + 1

    # -- mutation ------------------------------------------------------------
    def add(self, name: str, score: int, wave: int, difficulty: str = "normal") -> int | None:
        rank = self.rank_of(score)
        if rank is None:
            return None
        clean = (name.strip().upper() or DEFAULT_NAME)[:3]
        self._insert(ScoreEntry(clean, int(score), int(wave), difficulty, time.time()))
        return rank

    def _insert(self, entry: ScoreEntry) -> None:
        self.entries.append(entry)
        self.entries.sort(key=lambda e: (-e.score, e.timestamp))
        del self.entries[MAX_ENTRIES:]

    # -- persistence ---------------------------------------------------------
    @classmethod
    def load(cls, directory: Path | None = None) -> HighScoreTable:
        directory = directory or user_data_dir()
        path = directory / SCORES_FILE
        table = cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for item in raw if isinstance(raw, list) else []:
                try:
                    table._insert(ScoreEntry(**item))
                except TypeError:
                    continue
        except (OSError, ValueError):
            pass
        if not path.exists():
            table._import_legacy()
        return table

    def _import_legacy(self) -> None:
        """Pull scores from the pre-rewrite ``high_scores.txt`` if it exists."""
        try:
            lines = LEGACY_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if line.isdigit() and int(line) > 0:
                self._insert(ScoreEntry(DEFAULT_NAME, int(line), 1, "normal", 0.0))

    def save(self, directory: Path | None = None) -> None:
        directory = directory or user_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self.entries]
        (directory / SCORES_FILE).write_text(json.dumps(payload, indent=2), encoding="utf-8")
