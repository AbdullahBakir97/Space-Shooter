"""Radio logs: flag-triggered story lines. Pure module: no pygame import."""

from __future__ import annotations

import json
import operator
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from space_shooter.save import SaveData

SPEAKERS = ("pilot", "fleet", "warden", "unknown")
MAX_LINES = 3
LOGS_PATH = Path(__file__).resolve().parent / "data" / "act1_logs.json"
BAD_LOGS_NOTICE = "Radio logs could not be read. The story is silent this session."

_FIELDS = ("loop", "reached", "echoes_lost")
_OPS: dict[str, Callable[[int, int], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
}


@dataclass(frozen=True)
class StoryState:
    loop: int
    reached: int
    echoes_lost: int
    flags: frozenset[str]


@dataclass(frozen=True)
class LogEntry:
    id: str
    speaker: str
    lines: tuple[str, ...]
    when: str
    priority: int = 0


Condition = Callable[[StoryState], bool]


def _clause(text: str) -> Condition:
    text = text.strip()
    if text == "always":
        return lambda s: True
    negate = text.startswith("not ")
    if negate:
        text = text[4:].strip()
    if text.startswith("flag:"):
        name = text[5:].strip()
        if not name or " " in name:
            raise ValueError(f"bad flag clause {text!r}")
        if negate:
            return lambda s: name not in s.flags
        return lambda s: name in s.flags
    if negate:
        raise ValueError(f"'not' only applies to flags: {text!r}")
    parts = text.split()
    if len(parts) != 3 or parts[0] not in _FIELDS or parts[1] not in _OPS:
        raise ValueError(f"bad condition clause {text!r}")
    field_name, op = parts[0], _OPS[parts[1]]
    try:
        value = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"bad number in {text!r}") from exc
    return lambda s: op(getattr(s, field_name), value)


def parse_condition(text: str) -> Condition:
    """Parse ``clause and clause ...`` into a predicate over StoryState."""
    if not text or not text.strip():
        raise ValueError("empty condition")
    clauses = [_clause(c) for c in text.split(" and ")]
    if any(not c.strip() for c in text.split(" and ")):
        raise ValueError(f"dangling 'and' in {text!r}")
    return lambda s: all(c(s) for c in clauses)


def load_logs(path: Path | None = None) -> list[LogEntry]:
    """Load and validate logs; raise ValueError on any problem."""
    path = path or LOGS_PATH
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read logs: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("logs file must be a list")
    logs: list[LogEntry] = []
    seen: set[str] = set()
    for item in raw:
        try:
            entry = LogEntry(
                id=str(item["id"]),
                speaker=str(item["speaker"]),
                lines=tuple(str(line) for line in item["lines"]),
                when=str(item["when"]),
                priority=int(item.get("priority", 0)),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"malformed log entry {item!r}") from exc
        if entry.id in seen:
            raise ValueError(f"duplicate log id {entry.id!r}")
        if entry.speaker not in SPEAKERS:
            raise ValueError(f"unknown speaker {entry.speaker!r}")
        if not 1 <= len(entry.lines) <= MAX_LINES:
            raise ValueError(f"log {entry.id!r} must have 1 to {MAX_LINES} lines")
        parse_condition(entry.when)
        seen.add(entry.id)
        logs.append(entry)
    return logs


def load_logs_safe(path: Path | None = None) -> tuple[list[LogEntry], str | None]:
    try:
        return load_logs(path), None
    except ValueError:
        return [], BAD_LOGS_NOTICE


class LogDirector:
    def __init__(self, logs: list[LogEntry], read: list[str]) -> None:
        self.logs = logs
        self.read = read  # shared with SaveData.read_logs
        self._conditions = {log.id: parse_condition(log.when) for log in logs}

    def get(self, log_id: str) -> LogEntry | None:
        return next((log for log in self.logs if log.id == log_id), None)

    def next_log(self, state: StoryState) -> LogEntry | None:
        """Highest-priority unread log whose condition holds (file order breaks ties)."""
        best: LogEntry | None = None
        for log in self.logs:
            if log.id in self.read or not self._conditions[log.id](state):
                continue
            if best is None or log.priority > best.priority:
                best = log
        return best

    def mark_read(self, log_id: str) -> None:
        if log_id not in self.read:
            self.read.append(log_id)

    def unlocked(self) -> list[LogEntry]:
        return [log for log in self.logs if log.id in self.read]


def state_from_save(save: SaveData, reached: int | None = None) -> StoryState:
    if reached is None:
        reached = max((r.reached for r in save.records), default=0)
    lost = sum(1 for f in save.flags if f.startswith("echo_lost:"))
    return StoryState(save.loop, reached, lost, frozenset(save.flags))
