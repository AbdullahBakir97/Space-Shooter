"""Hardpoints, salvage parts and drop rolls. Pure module: no pygame import."""

from __future__ import annotations

import random
from dataclasses import dataclass

SLOTS = ("fore_l", "fore_r", "wing_l", "wing_r", "aft_l", "aft_r")
# Offsets from the ship centre in drawn pixels (left slots negative x).
SLOT_OFFSETS: dict[str, tuple[int, int]] = {
    "fore_l": (-14, -30),
    "fore_r": (14, -30),
    "wing_l": (-30, 2),
    "wing_r": (30, 2),
    "aft_l": (-16, 30),
    "aft_r": (16, 30),
}

KNOCK_CHANCE = 0.35
DROP_BASE = 0.18
PATCH_HULL = 20
ARMOUR_HITS = 2
RARE_EFFECT = 1.5


@dataclass(frozen=True)
class PartType:
    kind: str
    slots: tuple[str, ...]
    label: str


def _slots(*groups: str) -> tuple[str, ...]:
    return tuple(s for s in SLOTS if s.split("_")[0] in groups)


PART_TYPES: dict[str, PartType] = {
    "turret": PartType("turret", _slots("wing", "aft"), "AUTO-TURRET"),
    "slug": PartType("slug", _slots("fore"), "SLUG CANNON"),
    "tractor": PartType("tractor", _slots("aft"), "TRACTOR"),
    "armour": PartType("armour", SLOTS, "ARMOUR PLATE"),
    "thruster": PartType("thruster", _slots("aft"), "THRUSTER"),
    "claw": PartType("claw", _slots("fore"), "SALVAGE CLAW"),
}
PAIR_NAMES = {
    "turret": "TWIN TURRETS",
    "slug": "BROADSIDE",
    "tractor": "GRAVITY WELL",
    "armour": "BULKHEAD",
    "thruster": "AFTERBURNER",
    "claw": "SCRAPPER",
}
PART_DROP_WEIGHTS = {"turret": 25, "slug": 15, "tractor": 15, "armour": 20, "thruster": 15, "claw": 10}


@dataclass
class Part:
    kind: str
    rare: bool = False
    armour_left: int = ARMOUR_HITS

    @property
    def code(self) -> str:
        return self.kind + ("*" if self.rare else "")

    @property
    def effect(self) -> float:
        return RARE_EFFECT if self.rare else 1.0


def part_from_code(code: str) -> Part | None:
    kind = code.rstrip("*")
    if kind not in PART_TYPES:
        return None
    return Part(kind, rare=code.endswith("*"))


@dataclass
class HitOutcome:
    kind: str  # "armour" | "knocked" | "hull"
    slot: str | None = None
    part: Part | None = None


class Loadout:
    def __init__(self) -> None:
        self.slots: dict[str, Part | None] = dict.fromkeys(SLOTS)
        self._order: list[str] = []  # occupied slots, oldest first

    # -- mutation ------------------------------------------------------------
    def attach(self, part: Part, contact: tuple[float, float]) -> tuple[str, Part | None]:
        """Bolt ``part`` on; return (slot used, part ejected to make room)."""
        ptype = PART_TYPES.get(part.kind)
        if ptype is None:
            raise ValueError(f"unknown part kind {part.kind!r}")
        free = [s for s in ptype.slots if self.slots[s] is None]
        if free:
            cx, cy = contact
            slot = min(free, key=lambda s: (SLOT_OFFSETS[s][0] - cx) ** 2 + (SLOT_OFFSETS[s][1] - cy) ** 2)
            ejected = None
        else:
            slot = next(s for s in self._order if s in ptype.slots)
            ejected = self._remove(slot)
        self.slots[slot] = part
        self._order.append(slot)
        if part.kind == "armour":
            hits = self.armour_hits()
            part.armour_left = hits
            if hits > ARMOUR_HITS:  # BULKHEAD: every fitted plate is reinforced
                for _, other in self.parts():
                    if other.kind == "armour":
                        other.armour_left = max(other.armour_left, hits)
        return slot, ejected

    def _remove(self, slot: str) -> Part | None:
        part = self.slots[slot]
        self.slots[slot] = None
        if slot in self._order:
            self._order.remove(slot)
        return part

    def absorb_hit(self, rng: random.Random) -> HitOutcome:
        """Decide what takes a hit: an armour plate, a knocked-off part, or the hull."""
        for slot in SLOTS:
            part = self.slots[slot]
            if part is not None and part.kind == "armour" and part.armour_left > 0:
                part.armour_left -= 1
                if part.armour_left <= 0:
                    self._remove(slot)
                return HitOutcome("armour", slot, part)
        occupied = [s for s in SLOTS if self.slots[s] is not None]
        if occupied and rng.random() < KNOCK_CHANCE:
            slot = rng.choice(occupied)
            return HitOutcome("knocked", slot, self._remove(slot))
        return HitOutcome("hull")

    # -- queries -------------------------------------------------------------
    def parts(self) -> list[tuple[str, Part]]:
        return [(s, p) for s, p in self.slots.items() if p is not None]

    def count(self, kind: str) -> int:
        return sum(1 for _, p in self.parts() if p.kind == kind)

    def effect(self, kind: str) -> float:
        return sum(p.effect for _, p in self.parts() if p.kind == kind)

    def speed_multiplier(self) -> float:
        return 1.0 + 0.15 * min(2.0, self.effect("thruster"))

    def drop_chance(self, base: float) -> float:
        return min(0.9, base * (1.0 + 0.5 * self.effect("claw")))

    def patch_share(self) -> float:
        return 0.10 + 0.15 * min(1.0, self.effect("claw"))

    # -- signature moves and pair bonuses ------------------------------------
    def pairs(self) -> list[str]:
        """Kinds fitted twice or more, in PART_TYPES order."""
        return [kind for kind in PART_TYPES if self.count(kind) >= 2]

    def paired(self, kind: str) -> bool:
        return self.count(kind) >= 2

    def heavy_every(self) -> int | None:
        if not self.count("slug"):
            return None
        return 3 if self.paired("slug") else 4

    def armour_hits(self) -> int:
        return ARMOUR_HITS + 1 if self.paired("armour") else ARMOUR_HITS

    def dash_charges(self) -> int:
        return min(2, self.count("thruster"))

    def dash_recharge(self) -> float:
        base = 2.0 if self.paired("thruster") else 2.5
        scarred = sum(1 for _, p in self.parts() if p.kind == "thruster" and p.rare)
        return max(1.0, base - 0.5 * scarred)

    def turret_period(self) -> float:
        return 0.35 if self.paired("turret") else 0.5

    def tractor_range(self) -> float:
        if not self.count("tractor"):
            return 0.0
        return 2000.0 if self.paired("tractor") else 360.0

    def drops_scarred(self) -> bool:
        return self.paired("claw")

    def to_codes(self) -> dict[str, str]:
        return {s: p.code for s, p in self.parts()}

    @classmethod
    def from_codes(cls, codes: dict[str, str]) -> Loadout:
        lo = cls()
        for slot, code in codes.items():
            part = part_from_code(code)
            if slot in lo.slots and part is not None and slot in PART_TYPES[part.kind].slots:
                lo.slots[slot] = part
                lo._order.append(slot)
        return lo


def roll_drop(rng: random.Random, chance: float, patch_share: float = 0.2) -> str | None:
    """Return "patch", a part kind, or None."""
    if rng.random() >= chance:
        return None
    if rng.random() < patch_share:
        return "patch"
    kinds = list(PART_DROP_WEIGHTS)
    return rng.choices(kinds, [PART_DROP_WEIGHTS[k] for k in kinds])[0]
