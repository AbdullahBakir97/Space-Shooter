"""Versioned campaign save: loop count, echoes, story flags and records.

Pure module: no pygame import.
"""

from __future__ import annotations

import base64
import contextlib
import json
import shutil
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path

from space_shooter.paths import user_data_dir

SAVE_FILE = "save.json"
LEGACY_SCORES = "high_scores.json"
SAVE_VERSION = 1
MAX_RECORDS = 10
RESET_NOTICE = "Save data was unreadable and has been reset. A backup was kept."

# (encounter index, time within encounter, x, y, fired since previous sample)
Sample = tuple[int, float, float, float, bool]
_SAMPLE = struct.Struct("<Bfff?")


@dataclass
class Record:
    loop: int
    reached: int
    salvage: int
    time: float
    difficulty: str = "normal"


@dataclass
class EchoData:
    loop: int
    reached: int
    duration: float
    samples: str
    loadouts: list[dict] = field(default_factory=list)


@dataclass
class SaveData:
    version: int = SAVE_VERSION
    loop: int = 1
    echoes: list[EchoData] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)
    read_logs: list[str] = field(default_factory=list)
    records: list[Record] = field(default_factory=list)
    act1_complete: bool = False
    notice: str | None = None  # shown once in the hangar; never persisted


def pack_samples(samples: list[Sample]) -> str:
    raw = b"".join(_SAMPLE.pack(int(e), float(t), float(x), float(y), bool(f)) for e, t, x, y, f in samples)
    return base64.b64encode(raw).decode("ascii")


def unpack_samples(text: str) -> list[Sample]:
    raw = base64.b64decode(text.encode("ascii"))
    return [tuple(row) for row in _SAMPLE.iter_unpack(raw)]  # type: ignore[misc]


def _sort_records(records: list[Record]) -> None:
    records.sort(key=lambda r: (-r.reached, -r.salvage, r.loop))


def add_record(data: SaveData, record: Record) -> int | None:
    """Insert a record; return its 1-based rank, or None if it did not chart."""
    data.records.append(record)
    _sort_records(data.records)
    del data.records[MAX_RECORDS:]
    for i, r in enumerate(data.records):
        if r is record:
            return i + 1
    return None


def _from_dict(raw: dict) -> SaveData:
    return SaveData(
        version=int(raw.get("version", SAVE_VERSION)),
        loop=max(1, int(raw.get("loop", 1))),
        echoes=[EchoData(**e) for e in raw.get("echoes", [])],
        flags=set(raw.get("flags", [])),
        read_logs=list(raw.get("read_logs", [])),
        records=[Record(**r) for r in raw.get("records", [])],
        act1_complete=bool(raw.get("act1_complete", False)),
    )


def _migrate_legacy(directory: Path) -> list[Record]:
    try:
        raw = json.loads((directory / LEGACY_SCORES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    records = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and isinstance(item.get("score"), int):
            records.append(Record(0, 0, item["score"], 0.0, str(item.get("difficulty", "normal"))))
    _sort_records(records)
    return records[:MAX_RECORDS]


def load_save(directory: Path | None = None) -> SaveData:
    directory = directory or user_data_dir()
    path = directory / SAVE_FILE
    if not path.exists():
        return SaveData(records=_migrate_legacy(directory))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or int(raw.get("version", 0)) > SAVE_VERSION:
            raise ValueError("unsupported save")
        return _from_dict(raw)
    except (OSError, ValueError, TypeError, KeyError):
        with contextlib.suppress(OSError):
            shutil.copyfile(path, directory / (SAVE_FILE + ".bak"))
        return SaveData(notice=RESET_NOTICE)


def write_save(data: SaveData, directory: Path | None = None) -> bool:
    """Write the save; return False instead of raising if it cannot be written."""
    payload = asdict(data)
    payload.pop("notice", None)
    payload["flags"] = sorted(data.flags)
    try:
        directory = directory or user_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / (SAVE_FILE + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(directory / SAVE_FILE)
    except OSError:
        return False
    return True
