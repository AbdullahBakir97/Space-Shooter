"""Echoes: recordings of past loops that fly again beside the player.

Pure module: no pygame import. Traces are keyed by encounter so playback
re-synchronises at the start of every encounter (spec 5.4).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from space_shooter.save import EchoData, Sample, pack_samples, unpack_samples

SAMPLE_RATE = 20
MAX_ACTIVE = 5
MAX_STORED = 12
MIN_SECONDS = 10.0
ECHO_HP = 6
ECHO_DAMAGE = 0.6

LoadoutEntry = tuple[int, float, dict[str, str]]


@dataclass
class EchoTrace:
    loop: int
    reached: int
    duration: float
    samples: list[Sample]
    loadouts: list[LoadoutEntry] = field(default_factory=list)

    def to_data(self) -> EchoData:
        return EchoData(
            self.loop,
            self.reached,
            self.duration,
            pack_samples(self.samples),
            [{"encounter": e, "t": t, "parts": dict(p)} for e, t, p in self.loadouts],
        )

    @classmethod
    def from_data(cls, data: EchoData) -> EchoTrace:
        loadouts = [(int(d["encounter"]), float(d["t"]), dict(d["parts"])) for d in data.loadouts]
        return cls(data.loop, data.reached, data.duration, unpack_samples(data.samples), loadouts)


class EchoRecorder:
    def __init__(self, loop: int) -> None:
        self.loop = loop
        self.samples: list[Sample] = []
        self.loadouts: list[LoadoutEntry] = []
        self.encounter = 0
        self._count = 0  # samples stored in the current encounter
        self._fired = False
        self._now = 0.0
        self._codes: dict[str, str] = {}
        self._begun: set[int] = set()

    def begin_encounter(self, index: int) -> None:
        self._begun.add(index)
        self.encounter = index
        self._count = 0
        self._now = 0.0

    def has_encounter(self, index: int) -> bool:
        return index in self._begun

    def note_fire(self) -> None:
        self._fired = True

    def note_loadout(self, codes: dict[str, str]) -> None:
        if codes != self._codes:
            self._codes = dict(codes)
            self.loadouts.append((self.encounter, self._now, dict(codes)))

    def sample(self, t_rel: float, x: float, y: float) -> None:
        self._now = t_rel
        if t_rel + 1e-6 < self._count / SAMPLE_RATE:
            return
        self.samples.append((self.encounter, t_rel, float(x), float(y), self._fired))
        self._fired = False
        self._count += 1

    def finish(self, reached: int, duration: float) -> EchoTrace:
        return EchoTrace(self.loop, reached, duration, list(self.samples), list(self.loadouts))


@dataclass
class EchoState:
    x: float
    y: float
    fired: bool
    ended: bool
    loadout: dict[str, str]


class EchoPlayback:
    def __init__(self, trace: EchoTrace) -> None:
        self.trace = trace
        self.segments: dict[int, list[Sample]] = {}
        for s in trace.samples:
            self.segments.setdefault(s[0], []).append(s)
        self.times = {e: [s[1] for s in seg] for e, seg in self.segments.items()}
        self.last_encounter = max(self.segments, default=-1)
        self._cursor: dict[int, float] = {}

    def has_encounter(self, index: int) -> bool:
        return index in self.segments

    def _loadout_at(self, index: int, t_rel: float) -> dict[str, str]:
        current: dict[str, str] = {}
        own = any(e == index for e, _, _ in self.trace.loadouts)
        for e, t, parts in self.trace.loadouts:
            # a segment that logged its own loadout (every flown fight does) wears only that, since flown
            # fights are keyed by type, not in order; older traces carry the last loadout forward
            if (e == index and t <= t_rel) or (not own and e < index):
                current = parts
        return dict(current)

    def advance(self, index: int, t_rel: float) -> EchoState | None:
        seg = self.segments.get(index)
        if not seg:
            return None
        times = self.times[index]
        prev = self._cursor.get(index, -math.inf)
        self._cursor[index] = t_rel
        lo = bisect.bisect_right(times, prev)
        hi = bisect.bisect_right(times, t_rel)
        fired = any(seg[i][4] for i in range(lo, hi))
        if t_rel >= times[-1]:
            x, y = seg[-1][2], seg[-1][3]
            ended = index == self.last_encounter
        elif hi == 0:
            x, y, ended = seg[0][2], seg[0][3], False
        else:
            a, b = seg[hi - 1], seg[hi]
            f = (t_rel - a[1]) / ((b[1] - a[1]) or 1.0)
            x, y, ended = a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f, False
        return EchoState(x, y, fired, ended, self._loadout_at(index, t_rel))


def select_roster(traces: list[EchoTrace], limit: int = MAX_ACTIVE) -> list[EchoTrace]:
    """The echoes that fly this loop: furthest reached first, then most recent."""
    return sorted(traces, key=lambda t: (-t.reached, -t.loop))[:limit]


def store_trace(traces: list[EchoTrace], new: EchoTrace) -> list[EchoTrace]:
    kept = list(traces) + ([new] if new.duration >= MIN_SECONDS else [])
    kept.sort(key=lambda t: -t.duration)
    return kept[:MAX_STORED]


def densest_cluster(
    points: list[tuple[float, float]], radius: float = 90.0, fallback: tuple[float, float] = (0.0, 0.0)
) -> tuple[float, float]:
    """Centre of the most crowded circle of ``radius`` around any point."""
    if not points:
        return fallback
    r2 = radius * radius
    best: list[tuple[float, float]] = []
    for cx, cy in points:
        members = [(x, y) for x, y in points if (x - cx) ** 2 + (y - cy) ** 2 <= r2]
        if len(members) > len(best):
            best = members
    return (sum(x for x, _ in best) / len(best), sum(y for _, y in best) / len(best))
