"""Act 1 encounters as data, plus the director that plays them. Pure module."""

from __future__ import annotations

import random
from dataclasses import dataclass

from space_shooter.config import LOOP_HULL_CAP, LOOP_HULL_STEP

DRIFT_TIME = 6.0
WARDEN_INDEX = 5


@dataclass(frozen=True)
class Spawn:
    at: float
    kind: str
    x_frac: float


@dataclass(frozen=True)
class SpawnEntry:
    at: float
    pattern: str  # line | vee | column | pincer | scatter | single
    kind: str
    count: int
    x: float


@dataclass(frozen=True)
class Encounter:
    index: int
    name: str
    time_cap: float | None
    script: tuple[SpawnEntry, ...]
    hazards: tuple[str, ...] = ()
    moments: tuple[tuple[float, str], ...] = ()
    hull: float = 1.0  # enemy hull multiplier for this encounter (campaign twists)


def _e(at: float, pattern: str, kind: str, count: int, x: float = 0.5) -> SpawnEntry:
    return SpawnEntry(at, pattern, kind, count, x)


ENCOUNTERS: tuple[Encounter, ...] = (
    Encounter(
        0,
        "COLD WAKE",
        60,
        (
            _e(2, "line", "drone", 3),
            _e(8, "vee", "drone", 5, 0.4),
            _e(16, "line", "drone", 4, 0.6),
            _e(24, "column", "drone", 3, 0.3),
            _e(32, "vee", "drone", 3, 0.7),
        ),
        moments=((0.0, "first_drop"),),
    ),
    Encounter(
        1,
        "ASH SHELF",
        70,
        (
            _e(2, "line", "drone", 4),
            _e(6, "single", "zigzag", 1, 0.3),
            _e(7, "single", "zigzag", 1, 0.7),
            _e(12, "vee", "drone", 5),
            _e(20, "column", "zigzag", 3, 0.5),
            _e(28, "line", "drone", 4, 0.4),
            _e(36, "pincer", "zigzag", 4),
            _e(44, "scatter", "drone", 2),
        ),
        hazards=("ash",),
        moments=((25.0, "blackout"),),
    ),
    Encounter(
        2,
        "GRAVEYARD",
        75,
        (
            _e(2, "line", "drone", 4),
            _e(6, "single", "diver", 1, 0.25),
            _e(7, "single", "diver", 1, 0.75),
            _e(12, "vee", "drone", 5),
            _e(20, "pincer", "diver", 4),
            _e(28, "column", "drone", 4, 0.6),
            _e(36, "scatter", "diver", 3),
            _e(44, "line", "drone", 4, 0.4),
            _e(52, "pincer", "diver", 2),
        ),
        hazards=("hulks",),
        moments=((30.0, "hulk_breach"),),
    ),
    Encounter(
        3,
        "PICKET LINE",
        80,
        (
            _e(2, "line", "drone", 5),
            _e(6, "line", "gunner", 3),
            _e(14, "vee", "drone", 5),
            _e(20, "pincer", "gunner", 2),
            _e(26, "column", "drone", 4, 0.35),
            _e(34, "line", "gunner", 3, 0.6),
            _e(40, "vee", "drone", 5, 0.45),
            _e(48, "scatter", "drone", 3),
            _e(54, "single", "gunner", 1, 0.5),
            _e(58, "single", "drone", 1, 0.2),
        ),
    ),
    Encounter(
        4,
        "LAST LIGHT",
        90,
        (
            _e(2, "vee", "drone", 5),
            _e(8, "pincer", "zigzag", 4),
            _e(14, "line", "diver", 3),
            _e(20, "line", "gunner", 2, 0.5),
            _e(26, "column", "drone", 4, 0.7),
            _e(32, "scatter", "zigzag", 4),
            _e(38, "pincer", "diver", 4),
            _e(50, "pincer", "gunner", 2),
            _e(56, "line", "drone", 5),
            _e(62, "vee", "zigzag", 3, 0.4),
            _e(68, "scatter", "diver", 4),
        ),
        hazards=("debris", "hulks"),
        moments=((45.0, "flare"),),
    ),
    Encounter(WARDEN_INDEX, "THE WARDEN", None, (_e(0, "single", "warden", 1),)),
)

# A patrol caught the tug in flight: one short wave, fought for salvage, never for ground.
AMBUSH = Encounter(
    6,
    "AMBUSH",
    25,
    (
        _e(1, "vee", "drone", 4),
        _e(6, "pincer", "zigzag", 2),
        _e(12, "line", "drone", 4, 0.4),
        _e(17, "column", "zigzag", 3, 0.6),
    ),
)


def loop_hull_multiplier(loop: int) -> float:
    """Enemy hull scale for a given loop number (loop 1 is unscaled)."""
    return 1.0 + min(LOOP_HULL_CAP, LOOP_HULL_STEP * max(0, loop - 1))


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def expand(entry: SpawnEntry, rng: random.Random) -> list[Spawn]:
    """Turn one script entry into concrete timed spawns."""
    n, at, x, kind = entry.count, entry.at, entry.x, entry.kind
    centre = (n - 1) / 2
    if entry.pattern == "line":
        out = [Spawn(at, kind, _clamp(x + 0.08 * (i - centre))) for i in range(n)]
    elif entry.pattern == "vee":
        out = [Spawn(at + 0.15 * abs(i - centre), kind, _clamp(x + 0.08 * (i - centre))) for i in range(n)]
    elif entry.pattern == "column":
        out = [Spawn(at + 0.35 * i, kind, _clamp(x)) for i in range(n)]
    elif entry.pattern == "pincer":
        out = [Spawn(at + 0.25 * (i // 2), kind, 0.06 if i % 2 == 0 else 0.94) for i in range(n)]
    elif entry.pattern == "scatter":
        out = [Spawn(at + 0.2 * i, kind, rng.uniform(0.08, 0.92)) for i in range(n)]
    elif entry.pattern == "single":
        out = [Spawn(at, kind, _clamp(x))]
    else:
        raise ValueError(f"unknown spawn pattern {entry.pattern!r}")
    return out


class EncounterDirector:
    """Drift -> active -> clearing -> next drift ... -> complete after the Warden."""

    def __init__(
        self,
        rng: random.Random,
        encounters: tuple[Encounter, ...] = ENCOUNTERS,
        first_drift: float = DRIFT_TIME,
    ) -> None:
        self.rng = rng
        self.encounters = encounters
        self.index = 0
        self.state = "drift"
        self.timer = first_drift
        self.t_rel = 0.0
        self.plan: list[Spawn] = []
        self.cursor = 0
        self.fired_moments: set[str] = set()
        self.retreated = False
        self.cleared = 0  # encounters fully cleared this run
        self._events: list[tuple[str, object]] = [("drift_start", 0)]

    @property
    def encounter(self) -> Encounter:
        return self.encounters[self.index]

    def drain_events(self) -> list[tuple[str, object]]:
        events, self._events = self._events, []
        return events

    def _start_encounter(self) -> None:
        enc = self.encounter
        self.plan = sorted((s for e in enc.script for s in expand(e, self.rng)), key=lambda s: s.at)
        self.cursor = 0
        self.t_rel = 0.0
        self.fired_moments = set()
        self.retreated = False
        self.state = "active"
        self._events.append(("encounter_start", self.index))

    def _tick_encounter(self) -> list[Spawn]:
        enc = self.encounter
        for at, name in enc.moments:
            if at <= self.t_rel and name not in self.fired_moments:
                self.fired_moments.add(name)
                self._events.append(("moment", name))
        if enc.time_cap is not None and self.t_rel >= enc.time_cap and not self.retreated:
            self.retreated = True
            self.cursor = len(self.plan)
            self._events.append(("retreat", self.index))
        due: list[Spawn] = []
        while self.cursor < len(self.plan) and self.plan[self.cursor].at <= self.t_rel:
            due.append(self.plan[self.cursor])
            self.cursor += 1
        if self.state == "active" and self.cursor >= len(self.plan):
            self.state = "clearing"
        return due

    def update(self, dt: float, enemies_alive: int) -> list[Spawn]:
        if self.state == "complete":
            return []
        if self.state == "drift":
            self.timer -= dt
            if self.timer > 0:
                return []
            self._start_encounter()
            return self._tick_encounter()
        if self.state == "clearing" and enemies_alive == 0:
            self._events.append(("encounter_end", self.index))
            self.cleared += 1
            if self.index >= len(self.encounters) - 1:
                self.state = "complete"
                self._events.append(("run_complete", None))
            else:
                self.index += 1
                self.state = "drift"
                self.timer = DRIFT_TIME
                self._events.append(("drift_start", self.index))
            return []
        self.t_rel += dt
        return self._tick_encounter()
