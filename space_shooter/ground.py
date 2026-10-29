"""The ground war: the pilot on foot, hand weapons, the swarm and the garrison's last survivors.

Pure module: no pygame import. World units are pixels of the planet map.
"""

from __future__ import annotations

import math
import random
import zlib
from collections import deque
from dataclasses import dataclass, field

Point = tuple[float, float]

# -- the map ---------------------------------------------------------------------
TILE = 32
MAP_W, MAP_H = 75, 40
FLOOR, ROCK, WRECK = 0, 1, 2
PAD_TILE = (4, 35)
ROCK_BLOBS = 34
WRECKS = 12
POINT_CLEARANCE = 400.0  # objectives, survivors and crates sit at least this far from the pad
POINT_SPACING = 180.0
NESTS_BY_MISSION = {"nests": 4, "carry": 2, "hold": 0}
SURVIVORS = 3
CRATES = 4
LOS_STEP = 8.0

# -- the pilot and weapons -------------------------------------------------------
PILOT_HEALTH = 100
PILOT_SPEED = 210.0
PILOT_RADIUS = 12
ROLL_TIME = 0.35
ROLL_SPEED = 520.0
ROLL_COOLDOWN = 1.2
SHOT_SPEED = 700.0
SHOT_LIFE = 0.9
START_GRENADES = 2
MAX_GRENADES = 4
GRENADE_RANGE = 300.0
GRENADE_SPEED = 420.0
GRENADE_FUSE = 1.2
GRENADE_DAMAGE = 12
GRENADE_RADIUS = 90.0
SLOTS = ("sidearm", "rifle", "scattergun")


@dataclass(frozen=True)
class Weapon:
    name: str
    damage: float
    shots: int
    spread: float  # the whole cone, radians
    period: float
    mag: int | None  # None: never runs dry
    reserve: int
    reload: float


WEAPONS = {
    "sidearm": Weapon("SIDEARM", 2, 1, 0.03, 0.25, None, 0, 0.0),
    "rifle": Weapon("RIFLE", 2, 1, 0.06, 0.10, 30, 90, 1.6),
    "scattergun": Weapon("SCATTERGUN", 2, 6, 0.35, 0.70, 6, 24, 2.0),
}


def _tile_of(p: Point) -> tuple[int, int]:
    return (int(p[0] // TILE), int(p[1] // TILE))


def _centre(tile: tuple[int, int]) -> Point:
    return ((tile[0] + 0.5) * TILE, (tile[1] + 0.5) * TILE)


@dataclass
class GroundMap:
    tiles: list[list[int]]
    pad: Point = (0.0, 0.0)
    nests: list[Point] = field(default_factory=list)
    survivors: list[Point] = field(default_factory=list)
    crates: list[Point] = field(default_factory=list)
    beacon: Point | None = None
    core: Point | None = None

    @classmethod
    def empty(cls, w: int, h: int) -> GroundMap:
        return cls([[FLOOR] * w for _ in range(h)], pad=_centre((1, h - 2)))

    @property
    def size(self) -> Point:
        return (len(self.tiles[0]) * TILE, len(self.tiles) * TILE)

    def tile(self, tx: int, ty: int) -> int:
        if 0 <= ty < len(self.tiles) and 0 <= tx < len(self.tiles[0]):
            return self.tiles[ty][tx]
        return ROCK

    def blocked(self, x: float, y: float) -> bool:
        return self.tile(int(x // TILE), int(y // TILE)) != FLOOR

    def cast(self, a: Point, b: Point) -> Point:
        """The last free point walking from ``a`` toward ``b``."""
        dist = math.dist(a, b)
        steps = max(1, int(dist / LOS_STEP))
        last = a
        for i in range(1, steps + 1):
            t = i / steps
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if self.blocked(*p):
                return last
            last = p
        return last

    def line_of_sight(self, a: Point, b: Point) -> bool:
        return self.cast(a, b) == b or math.dist(self.cast(a, b), b) < 1e-6

    def distances_from(self, p: Point) -> dict[tuple[int, int], int]:
        """Tile steps from ``p`` to every reachable floor tile (four-way)."""
        start = _tile_of(p)
        dist = {start: 0}
        queue = deque([start])
        while queue:
            tx, ty = queue.popleft()
            for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                if (nx, ny) not in dist and self.tile(nx, ny) == FLOOR:
                    dist[(nx, ny)] = dist[(tx, ty)] + 1
                    queue.append((nx, ny))
        return dist

    def reachable_from_pad(self, p: Point) -> bool:
        return _tile_of(p) in self.distances_from(self.pad)


def _clear(tiles: list[list[int]], tx: int, ty: int, r: int) -> None:
    for y in range(ty - r, ty + r + 1):
        for x in range(tx - r, tx + r + 1):
            if 0 < y < MAP_H - 1 and 0 < x < MAP_W - 1:
                tiles[y][x] = FLOOR


def _carve(tiles: list[list[int]], a: tuple[int, int], b: tuple[int, int]) -> None:
    """An L-shaped corridor two tiles wide."""
    (ax, ay), (bx, by) = a, b
    for x in range(min(ax, bx), max(ax, bx) + 1):
        _clear(tiles, x, ay, 1)
    for y in range(min(ay, by), max(ay, by) + 1):
        _clear(tiles, bx, y, 1)


def generate_map(node_id: str, mission: str | None = None) -> GroundMap:
    """A planet's battlefield: the same layout every time for the same planet."""
    mission = mission or MISSIONS.get(node_id, "nests")
    rng = random.Random(zlib.crc32(node_id.encode()))
    tiles = [[FLOOR] * MAP_W for _ in range(MAP_H)]
    for x in range(MAP_W):
        tiles[0][x] = tiles[MAP_H - 1][x] = ROCK
    for y in range(MAP_H):
        tiles[y][0] = tiles[y][MAP_W - 1] = ROCK
    for _ in range(ROCK_BLOBS):
        cx, cy, r = rng.randrange(2, MAP_W - 2), rng.randrange(2, MAP_H - 2), rng.randint(1, 3)
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if 0 < y < MAP_H - 1 and 0 < x < MAP_W - 1 and (x - cx) ** 2 + (y - cy) ** 2 <= r * r + rng.random():
                    tiles[y][x] = ROCK
    for _ in range(WRECKS):
        x, y = rng.randrange(2, MAP_W - 5), rng.randrange(2, MAP_H - 4)
        w, h = rng.randint(2, 3), rng.randint(1, 2)
        for ty in range(y, y + h):
            for tx in range(x, x + w):
                tiles[ty][tx] = WRECK
    _clear(tiles, *PAD_TILE, 2)
    pad = _centre(PAD_TILE)
    taken: list[Point] = [pad]

    def place(min_from_pad: float = POINT_CLEARANCE) -> Point:
        for _ in range(500):
            tile = (rng.randrange(3, MAP_W - 3), rng.randrange(3, MAP_H - 3))
            p = _centre(tile)
            if math.dist(p, pad) >= min_from_pad and all(math.dist(p, q) >= POINT_SPACING for q in taken):
                break
        _clear(tiles, *tile, 1)
        taken.append(p)
        return p

    gmap = GroundMap(tiles, pad=pad)
    gmap.nests = [place() for _ in range(NESTS_BY_MISSION[mission])]
    if mission == "hold":
        gmap.beacon = place(900)
    if mission == "carry":
        gmap.core = place(1500)
    gmap.survivors = [place() for _ in range(SURVIVORS)]
    gmap.crates = [place() for _ in range(CRATES)]
    reach = gmap.distances_from(pad)
    for p in taken[1:]:
        if _tile_of(p) not in reach:
            _carve(tiles, PAD_TILE, _tile_of(p))
            reach = gmap.distances_from(pad)
    return gmap


# -- bodies ----------------------------------------------------------------------
@dataclass
class Body:
    x: float
    y: float
    radius: float
    hp: float
    max_hp: float

    @property
    def pos(self) -> Point:
        return (self.x, self.y)


def _fits(gmap: GroundMap, x: float, y: float, r: float) -> bool:
    return not any(gmap.blocked(x + dx, y + dy) for dx in (-r, r) for dy in (-r, r))


def move_body(gmap: GroundMap, body: Body, dx: float, dy: float) -> None:
    """Slide along walls: each axis moves on its own, in steps no longer than a quarter tile."""
    steps = max(1, math.ceil(max(abs(dx), abs(dy)) / (TILE / 4)))
    sx, sy = dx / steps, dy / steps
    for _ in range(steps):
        if _fits(gmap, body.x + sx, body.y, body.radius):
            body.x += sx
        if _fits(gmap, body.x, body.y + sy, body.radius):
            body.y += sy


# -- weapons ---------------------------------------------------------------------
@dataclass
class Shot:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    friendly: bool
    life: float = SHOT_LIFE


@dataclass
class Grenade:
    x: float
    y: float
    tx: float
    ty: float
    fuse: float = GRENADE_FUSE


class Arsenal:
    def __init__(self) -> None:
        self.owned = ["sidearm"]
        self.current = "sidearm"
        self.mag = {k: 0 for k in WEAPONS}
        self.reserve = {k: 0 for k in WEAPONS}
        self.grenades = START_GRENADES
        self.cooldown = 0.0
        self.reloading = 0.0

    @property
    def weapon(self) -> Weapon:
        return WEAPONS[self.current]

    def select(self, slot: int) -> None:
        if 1 <= slot <= len(SLOTS) and SLOTS[slot - 1] in self.owned and SLOTS[slot - 1] != self.current:
            self.current = SLOTS[slot - 1]
            self.reloading = 0.0

    def reload(self) -> None:
        w = self.weapon
        if w.mag is not None and self.reloading <= 0 and self.mag[self.current] < w.mag and self.reserve[self.current]:
            self.reloading = w.reload

    def update(self, dt: float) -> None:
        self.cooldown = max(-0.02, self.cooldown - dt)
        if self.reloading > 0:
            self.reloading -= dt
            if self.reloading <= 0:
                self.reloading = 0.0
                kind, w = self.current, self.weapon
                take = min(w.mag - self.mag[kind], self.reserve[kind])
                self.mag[kind] += take
                self.reserve[kind] -= take

    def trigger(self, origin: Point, aim: Point, rng: random.Random) -> list[Shot]:
        w = self.weapon
        if self.cooldown > 1e-9 or self.reloading > 0:
            return []
        if w.mag is not None:
            if self.mag[self.current] <= 0:
                self.reload()
                return []
            self.mag[self.current] -= 1
        self.cooldown = max(0.0, self.cooldown) + w.period
        base = math.atan2(aim[1] - origin[1], aim[0] - origin[0])
        shots = []
        for _ in range(w.shots):
            a = base + rng.uniform(-w.spread / 2, w.spread / 2)
            shots.append(Shot(origin[0], origin[1], math.cos(a) * SHOT_SPEED, math.sin(a) * SHOT_SPEED, w.damage, True))
        if w.mag is not None and self.mag[self.current] == 0:
            self.reload()
        return shots

    def give(self, kind: str) -> str:
        """Own a weapon with a full magazine and reserve, or top up its ammo if already owned."""
        w = WEAPONS[kind]
        if kind not in self.owned:
            self.owned.append(kind)
            self.owned.sort(key=SLOTS.index)
            self.mag[kind], self.reserve[kind] = w.mag or 0, w.reserve
            return w.name
        self.reserve[kind] += (w.mag or 0) * 2
        return f"{w.name} AMMO"

    def add_ammo(self, kind: str, amount: int) -> None:
        self.reserve[kind] += amount

    def open_crate(self, rng: random.Random) -> str:
        missing = [k for k in SLOTS[1:] if k not in self.owned]
        text = self.give(rng.choice(missing) if missing else rng.choice(SLOTS[1:]))
        if self.grenades < MAX_GRENADES:
            self.grenades += 1
            text += " + GRENADE"
        return text

    def throw(self, gmap: GroundMap, origin: Point, aim: Point) -> Grenade | None:
        if self.grenades <= 0:
            return None
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        dist = math.hypot(dx, dy)
        if dist > GRENADE_RANGE:
            aim = (origin[0] + dx / dist * GRENADE_RANGE, origin[1] + dy / dist * GRENADE_RANGE)
        tx, ty = gmap.cast(origin, aim)
        self.grenades -= 1
        return Grenade(origin[0], origin[1], tx, ty)


MISSIONS = {"m1": "nests", "m3": "hold", "m5": "carry"}
