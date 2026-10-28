"""Pure wave design: turns a wave number into a timed spawn plan.

No pygame here, so this module is unit-tested directly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from space_shooter.config import BOSS_EVERY

ENEMY_KINDS = ("drone", "zigzag", "diver", "gunner")


@dataclass(frozen=True)
class Spawn:
    """One enemy to spawn ``at`` seconds after the wave starts."""

    at: float
    kind: str
    x_frac: float  # horizontal position as a fraction of the playfield width


def is_boss_wave(wave: int) -> bool:
    return wave > 0 and wave % BOSS_EVERY == 0


def enemy_count(wave: int) -> int:
    """How many regular enemies a wave contains."""
    return min(8 + wave * 3, 60)


def kind_weights(wave: int) -> dict[str, int]:
    """Unlock harder enemy types as the waves progress."""
    weights = {"drone": 60, "zigzag": 0, "diver": 0, "gunner": 0}
    if wave >= 2:
        weights["zigzag"] = 25 + min(wave * 2, 20)
    if wave >= 3:
        weights["diver"] = 15 + min(wave * 2, 20)
    if wave >= 4:
        weights["gunner"] = 10 + min(wave * 2, 25)
    return weights


def _spawn_interval(wave: int, spawn_rate: float) -> float:
    base = max(0.35, 1.1 - wave * 0.05)
    return base / spawn_rate


def build_wave(wave: int, spawn_rate: float = 1.0, rng: random.Random | None = None) -> list[Spawn]:
    """Return the sorted spawn plan for ``wave``.

    Boss waves contain only the boss. ``spawn_rate`` > 1 compresses the plan.
    A seeded ``rng`` makes the plan deterministic.
    """
    rng = rng or random.Random()
    if is_boss_wave(wave):
        return [Spawn(0.0, "boss", 0.5)]

    weights = kind_weights(wave)
    kinds = [k for k in ENEMY_KINDS if weights[k] > 0]
    pool = [weights[k] for k in kinds]
    interval = _spawn_interval(wave, spawn_rate)
    plan: list[Spawn] = []
    t = 0.0
    count = enemy_count(wave)
    i = 0
    while i < count:
        kind = rng.choices(kinds, pool)[0]
        # Occasionally spawn a tight formation of drones for visual rhythm.
        if kind == "drone" and rng.random() < 0.25 and i + 3 <= count:
            centre = rng.uniform(0.25, 0.75)
            for j in range(3):
                plan.append(Spawn(t + j * 0.12, "drone", centre + (j - 1) * 0.09))
            i += 3
        else:
            plan.append(Spawn(t, kind, rng.uniform(0.08, 0.92)))
            i += 1
        t += interval * rng.uniform(0.7, 1.3)
    plan.sort(key=lambda s: s.at)
    return plan
