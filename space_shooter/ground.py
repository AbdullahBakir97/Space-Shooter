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


# -- the swarm, the squad and the missions -----------------------------------------
CRAWLER_HP, CRAWLER_SPEED, CRAWLER_RADIUS, CRAWLER_SCORE = 6, 150.0, 11, 10
CRAWLER_DAMAGE, CRAWLER_COOLDOWN = 8, 0.6
SPITTER_HP, SPITTER_SPEED, SPITTER_RADIUS, SPITTER_SCORE = 8, 70.0, 12, 20
SPIT_RANGE, SPIT_PERIOD, SPIT_DAMAGE, SPIT_SPEED = 260.0, 1.6, 6, 320.0
NEST_HP, NEST_RADIUS, NEST_SCORE = 40, 22, 60
NEST_PERIOD, NEST_CAP, NEST_WAKE = 5.0, 6, 700.0
CHASE_DIRECT = 200.0  # within this, with a clear line, the swarm runs straight at its prey
FLOW_PERIOD = 0.5
SURVIVOR_HP, SURVIVOR_RADIUS, SURVIVOR_SPEED = 60, 12, 190.0
JOIN_RANGE, FOLLOW_NEAR, FOLLOW_FAR = 80.0, 70.0, 140.0
SURVIVOR_RANGE, SURVIVOR_DAMAGE, SURVIVOR_PERIOD, SURVIVOR_SPREAD = 380.0, 2, 0.45, 0.05
SURVIVOR_DROP = 30
SQUAD_BONUS = 100
PICKUP_RADIUS = 30.0
BEACON_RADIUS, HOLD_TIME, WAVE_PERIOD = 120.0, 90.0, 12.0
WAVE = (("crawler", 3), ("spitter", 1))
WAVE_CLEARANCE = 600.0
CORE_PICKUP, CARRY_SLOW, PAD_RADIUS = 40.0, 0.8, 60.0
KINDS = {
    "crawler": (CRAWLER_HP, CRAWLER_SPEED, CRAWLER_RADIUS, CRAWLER_SCORE),
    "spitter": (SPITTER_HP, SPITTER_SPEED, SPITTER_RADIUS, SPITTER_SCORE),
}
OBJECTIVES = {"nests": "DESTROY THE BROOD NESTS", "hold": "HOLD THE BEACON", "carry": "RECOVER THE CORE"}


class Enemy:
    def __init__(self, kind: str, x: float, y: float, hp_mult: float = 1.0, nest: Nest | None = None) -> None:
        hp, self.speed, radius, self.score = KINDS[kind]
        self.kind = kind
        self.body = Body(x, y, radius, hp * hp_mult, hp * hp_mult)
        self.cooldown = 0.0
        self.nest = nest
        self.frozen = False  # held still (tests and set pieces)

    @property
    def pos(self) -> Point:
        return self.body.pos


@dataclass
class Nest:
    body: Body
    period: float
    timer: float = 0.0
    children: int = 0

    @property
    def alive(self) -> bool:
        return self.body.hp > 0


class Survivor:
    def __init__(self, x: float, y: float, state: str = "waiting") -> None:
        self.body = Body(x, y, SURVIVOR_RADIUS, SURVIVOR_HP, SURVIVOR_HP)
        self.state = state  # waiting | follow | hold | move
        self.goal: Point | None = None
        self.goal_field: dict[tuple[int, int], int] | None = None
        self.cooldown = 0.0

    @property
    def x(self) -> float:
        return self.body.x

    @property
    def y(self) -> float:
        return self.body.y

    @property
    def pos(self) -> Point:
        return self.body.pos

    @property
    def alive(self) -> bool:
        return self.body.hp > 0

    @property
    def active(self) -> bool:
        return self.alive and self.state != "waiting"


@dataclass
class GroundInputs:
    move: Point = (0.0, 0.0)
    aim: Point = (0.0, 0.0)
    fire: bool = False
    roll: bool = False
    reload: bool = False
    slot: int | None = None
    grenade: bool = False
    order: object = None  # "follow" | "hold" | ("move", x, y)


def _norm(dx: float, dy: float) -> Point:
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (0.0, 0.0)


class GroundWorld:
    """One ground fight, advanced by ``step``; everything the scene draws lives here."""

    def __init__(
        self,
        node_id: str,
        mission: str | None = None,
        hull: float = 1.0,
        pace: float = 1.0,
        seed: int = 0,
        gmap: GroundMap | None = None,
    ) -> None:
        self.mission = mission or MISSIONS.get(node_id, "nests")
        self.map = gmap or generate_map(node_id, self.mission)
        self.hull, self.pace = hull, pace
        self.rng = random.Random(seed)
        self.pilot = Body(*self.map.pad, PILOT_RADIUS, PILOT_HEALTH, PILOT_HEALTH)
        self.arsenal = Arsenal()
        self.aim: Point = (self.pilot.x, self.pilot.y - 100)
        self.enemies: list[Enemy] = []
        self.nests = [
            Nest(Body(x, y, NEST_RADIUS, NEST_HP * hull, NEST_HP * hull), NEST_PERIOD * pace) for x, y in self.map.nests
        ]
        self.survivors = [Survivor(x, y) for x, y in self.map.survivors]
        self.pickups: list[list] = [["crate", x, y] for x, y in self.map.crates]
        self.shots: list[Shot] = []
        self.grenades: list[Grenade] = []
        self.core: Point | None = self.map.core
        self.carrying = False
        self.hold_time = 0.0
        self.wave_timer = WAVE_PERIOD * pace
        self.score = 0
        self.complete = False
        self.dead = False
        self.time = 0.0
        self.roll_timer = 0.0
        self.roll_cooldown = 0.0
        self.roll_dir: Point = (0.0, -1.0)
        self.invulnerable_for_tests = False
        self.flow: dict[tuple[int, int], int] = {}
        self.flow_timer = 0.0
        self._events: list[tuple[str, object]] = []

    # -- state ---------------------------------------------------------------
    @property
    def rolling(self) -> bool:
        return self.roll_timer > 0

    @property
    def invulnerable(self) -> bool:
        return self.rolling or self.invulnerable_for_tests

    def at_pad(self) -> bool:
        return math.dist(self.pilot.pos, self.map.pad) <= PAD_RADIUS

    def squad_bonus(self) -> int:
        return SQUAD_BONUS * sum(1 for s in self.survivors if s.active)

    def objective_text(self) -> str:
        if self.complete:
            return "RETURN TO THE TUG"
        title = OBJECTIVES[self.mission]
        if self.mission == "nests":
            dead = sum(1 for n in self.nests if not n.alive)
            return f"{title}  {dead}/{len(self.nests)}"
        if self.mission == "hold":
            return f"{title}  {int(self.hold_time)}/{int(HOLD_TIME)} s"
        return "CARRY THE CORE TO THE TUG" if self.carrying else title

    # -- changes -------------------------------------------------------------
    def spawn(self, kind: str, x: float, y: float, nest: Nest | None = None) -> Enemy:
        enemy = Enemy(kind, x, y, self.hull, nest)
        self.enemies.append(enemy)
        if nest is not None:
            nest.children += 1
        return enemy

    def give_weapon(self, kind: str) -> str:
        return self.arsenal.give(kind)

    def damage_pilot(self, amount: float) -> None:
        if self.invulnerable or self.dead:
            return
        self.pilot.hp -= amount
        self._events.append(("pilot_hit", amount))

    def damage_survivor(self, s: Survivor, amount: float) -> None:
        if not s.alive:
            return
        s.body.hp -= amount
        if not s.alive:
            self.pickups.append(["ammo", s.x, s.y])
            self._events.append(("survivor_down", self.survivors.index(s)))

    def damage_enemy(self, e: Enemy, amount: float) -> None:
        if e not in self.enemies:
            return
        e.body.hp -= amount
        self._events.append(("hit", e.kind))
        if e.body.hp <= 0:
            self.enemies.remove(e)
            if e.nest is not None:
                e.nest.children -= 1
            self.score += e.score
            self._events.append(("kill", e.kind))

    def damage_nest(self, n: Nest, amount: float) -> None:
        if not n.alive:
            return
        n.body.hp -= amount
        self._events.append(("hit", "nest"))
        if not n.alive:
            self.score += NEST_SCORE
            self._events.append(("kill", "nest"))

    # -- the step ------------------------------------------------------------
    def step(self, dt: float, inputs: GroundInputs) -> list[tuple[str, object]]:
        if self.dead:
            return []
        self._events = []
        self.time += dt
        self._pilot(dt, inputs)
        self._orders(inputs.order)
        self.flow_timer -= dt
        if self.flow_timer <= 0:
            self.flow = self.map.distances_from(self.pilot.pos)
            self.flow_timer = FLOW_PERIOD
        self._survivors(dt)
        self._nests(dt)
        self._enemies(dt)
        self._shots(dt)
        self._grenades(dt)
        self._pickups()
        self._mission(dt)
        if self.pilot.hp <= 0:
            self.dead = True
            self._events.append(("pilot_dead", None))
        return self._events

    def _pilot(self, dt: float, inputs: GroundInputs) -> None:
        self.aim = inputs.aim
        self.roll_timer = max(0.0, self.roll_timer - dt)
        self.roll_cooldown = max(0.0, self.roll_cooldown - dt)
        move = _norm(*inputs.move)
        if inputs.roll and self.roll_cooldown <= 0:
            self.roll_dir = (
                move if move != (0.0, 0.0) else _norm(inputs.aim[0] - self.pilot.x, inputs.aim[1] - self.pilot.y)
            )
            self.roll_timer, self.roll_cooldown = ROLL_TIME, ROLL_COOLDOWN
        if self.rolling:
            dx, dy = self.roll_dir[0] * ROLL_SPEED * dt, self.roll_dir[1] * ROLL_SPEED * dt
        else:
            speed = PILOT_SPEED * (CARRY_SLOW if self.carrying else 1.0)
            dx, dy = move[0] * speed * dt, move[1] * speed * dt
        move_body(self.map, self.pilot, dx, dy)
        a = self.arsenal
        a.update(dt)
        if inputs.slot is not None:
            a.select(inputs.slot)
        if inputs.reload:
            a.reload()
        if inputs.fire and not self.rolling:
            shots = a.trigger(self.pilot.pos, inputs.aim, self.rng)
            if shots:
                self.shots += shots
                self._events.append(("shot", a.current))
        if inputs.grenade:
            g = a.throw(self.map, self.pilot.pos, inputs.aim)
            if g is not None:
                self.grenades.append(g)

    def _orders(self, order) -> None:
        if order is None:
            return
        squad = [s for s in self.survivors if s.active]
        if order in ("follow", "hold"):
            for s in squad:
                s.state, s.goal, s.goal_field = order, None, None
        elif isinstance(order, tuple) and order[0] == "move":
            goal = (float(order[1]), float(order[2]))
            for i, s in enumerate(squad):
                offset = (i - (len(squad) - 1) / 2) * 30
                spot = self.map.cast(goal, (goal[0] + offset, goal[1]))
                s.state, s.goal = "move", spot
                s.goal_field = self.map.distances_from(spot)

    def _step_toward(self, body: Body, target: Point, field: dict, speed: float, dt: float) -> None:
        """Run straight at a close, visible target; otherwise follow the flow field downhill."""
        if math.dist(body.pos, target) <= CHASE_DIRECT and self.map.line_of_sight(body.pos, target):
            aim = target
        else:
            tx, ty = _tile_of(body.pos)
            here = field.get((tx, ty))
            best = None
            for nxt in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                d = field.get(nxt)
                if d is not None and (best is None or d < best[0]):
                    best = (d, nxt)
            downhill = best is not None and (here is None or best[0] < here)
            aim = _centre(best[1]) if downhill else target
        ux, uy = _norm(aim[0] - body.x, aim[1] - body.y)
        step = min(speed * dt, math.dist(body.pos, aim))
        move_body(self.map, body, ux * step, uy * step)

    def _survivors(self, dt: float) -> None:
        for i, s in enumerate(self.survivors):
            if not s.alive:
                continue
            if s.state == "waiting":
                if math.dist(s.pos, self.pilot.pos) <= JOIN_RANGE:
                    s.state = "follow"
                    self._events.append(("joined", i))
                continue
            if s.state == "follow" and math.dist(s.pos, self.pilot.pos) > FOLLOW_NEAR:
                if math.dist(s.pos, self.pilot.pos) > FOLLOW_FAR or s.goal is not None:
                    s.goal = self.pilot.pos  # walk in until comfortably close
                    self._step_toward(s.body, self.pilot.pos, self.flow, SURVIVOR_SPEED, dt)
            elif s.state == "follow":
                s.goal = None
            elif s.state == "move" and s.goal is not None:
                self._step_toward(s.body, s.goal, s.goal_field or {}, SURVIVOR_SPEED, dt)
                if math.dist(s.pos, s.goal) < 8:
                    s.state, s.goal, s.goal_field = "hold", None, None
            s.cooldown = max(0.0, s.cooldown - dt)
            if s.cooldown <= 0:
                target = self._nearest_foe(s.pos, SURVIVOR_RANGE)
                if target is not None:
                    a = math.atan2(target[1] - s.y, target[0] - s.x) + self.rng.uniform(
                        -SURVIVOR_SPREAD, SURVIVOR_SPREAD
                    )
                    self.shots.append(
                        Shot(s.x, s.y, math.cos(a) * SHOT_SPEED, math.sin(a) * SHOT_SPEED, SURVIVOR_DAMAGE, True)
                    )
                    s.cooldown = SURVIVOR_PERIOD

    def _nearest_foe(self, origin: Point, reach: float) -> Point | None:
        targets = [e.pos for e in self.enemies] + [n.body.pos for n in self.nests if n.alive]
        seen = [p for p in targets if math.dist(origin, p) <= reach and self.map.line_of_sight(origin, p)]
        return min(seen, key=lambda p: math.dist(origin, p)) if seen else None

    def _prey(self, origin: Point) -> tuple[Point, object]:
        """The nearest of the pilot and the active survivors."""
        best: tuple[Point, object] = (self.pilot.pos, None)
        for s in self.survivors:
            if s.active and math.dist(origin, s.pos) < math.dist(origin, best[0]):
                best = (s.pos, s)
        return best

    def _hurt(self, victim, amount: float) -> None:
        if victim is None:
            self.damage_pilot(amount)
        else:
            self.damage_survivor(victim, amount)

    def _nests(self, dt: float) -> None:
        for n in self.nests:
            if not n.alive or math.dist(n.body.pos, self.pilot.pos) > NEST_WAKE:
                continue
            n.timer += dt
            if n.timer >= n.period:
                n.timer -= n.period
                if n.children < NEST_CAP:
                    self.spawn("crawler", n.body.x, n.body.y, nest=n)

    def _enemies(self, dt: float) -> None:
        for e in list(self.enemies):
            e.cooldown = max(0.0, e.cooldown - dt)
            if e.frozen:
                continue
            prey, victim = self._prey(e.pos)
            dist = math.dist(e.pos, prey)
            if e.kind == "crawler":
                if dist > e.body.radius + PILOT_RADIUS:
                    self._step_toward(e.body, prey, self.flow, e.speed, dt)
                elif e.cooldown <= 0:
                    self._hurt(victim, CRAWLER_DAMAGE)
                    e.cooldown = CRAWLER_COOLDOWN
                continue
            sight = self.map.line_of_sight(e.pos, prey)
            if sight and dist < SPIT_RANGE - 30:
                ux, uy = _norm(e.body.x - prey[0], e.body.y - prey[1])
                move_body(self.map, e.body, ux * e.speed * dt, uy * e.speed * dt)
            elif not sight or dist > SPIT_RANGE:
                self._step_toward(e.body, prey, self.flow, e.speed, dt)
            if sight and dist <= SPIT_RANGE + 40 and e.cooldown <= 0:
                ux, uy = _norm(prey[0] - e.body.x, prey[1] - e.body.y)
                self.shots.append(Shot(e.body.x, e.body.y, ux * SPIT_SPEED, uy * SPIT_SPEED, SPIT_DAMAGE, False, 2.0))
                e.cooldown = SPIT_PERIOD

    def _shots(self, dt: float) -> None:
        for shot in list(self.shots):
            shot.x += shot.vx * dt
            shot.y += shot.vy * dt
            shot.life -= dt
            if shot.life <= 0 or self.map.blocked(shot.x, shot.y):
                self.shots.remove(shot)
                continue
            hit = False
            if shot.friendly:
                for e in self.enemies:
                    if math.dist((shot.x, shot.y), e.pos) <= e.body.radius:
                        self.damage_enemy(e, shot.damage)
                        hit = True
                        break
                if not hit:
                    for n in self.nests:
                        if n.alive and math.dist((shot.x, shot.y), n.body.pos) <= n.body.radius:
                            self.damage_nest(n, shot.damage)
                            hit = True
                            break
            else:
                if math.dist((shot.x, shot.y), self.pilot.pos) <= self.pilot.radius:
                    self.damage_pilot(shot.damage)
                    hit = not self.invulnerable  # a rolling pilot lets the spit pass
                else:
                    for s in self.survivors:
                        if s.active and math.dist((shot.x, shot.y), s.pos) <= s.body.radius:
                            self.damage_survivor(s, shot.damage)
                            hit = True
                            break
            if hit:
                self.shots.remove(shot)

    def _grenades(self, dt: float) -> None:
        for g in list(self.grenades):
            ux, uy = _norm(g.tx - g.x, g.ty - g.y)
            step = min(GRENADE_SPEED * dt, math.dist((g.x, g.y), (g.tx, g.ty)))
            g.x, g.y = g.x + ux * step, g.y + uy * step
            g.fuse -= dt
            if g.fuse > 0:
                continue
            self.grenades.remove(g)
            centre = (g.x, g.y)
            self._events.append(("explosion", centre))
            for e in list(self.enemies):
                if math.dist(centre, e.pos) <= GRENADE_RADIUS:
                    self.damage_enemy(e, GRENADE_DAMAGE)
            for n in self.nests:
                if math.dist(centre, n.body.pos) <= GRENADE_RADIUS + n.body.radius:
                    self.damage_nest(n, GRENADE_DAMAGE)

    def _pickups(self) -> None:
        for item in list(self.pickups):
            kind, x, y = item
            if math.dist((x, y), self.pilot.pos) > PICKUP_RADIUS + self.pilot.radius:
                continue
            self.pickups.remove(item)
            if kind == "crate":
                text = self.arsenal.open_crate(self.rng)
            else:
                self.arsenal.add_ammo("rifle", SURVIVOR_DROP)
                text = f"+{SURVIVOR_DROP} RIFLE AMMO"
            self._events.append(("pickup", text))
        if self.core is not None and not self.carrying and math.dist(self.core, self.pilot.pos) <= CORE_PICKUP:
            self.carrying = True
            self._events.append(("pickup", "CORE"))

    def _spawn_wave(self) -> None:
        w, h = self.map.size
        for kind, count in WAVE:
            for _ in range(count):
                for _ in range(200):
                    tx = self.rng.choice(
                        (self.rng.randrange(1, 4), self.rng.randrange(int(w // TILE) - 4, int(w // TILE) - 1))
                    )
                    ty = self.rng.randrange(1, int(h // TILE) - 1)
                    p = _centre((tx, ty))
                    if not self.map.blocked(*p) and math.dist(p, self.pilot.pos) >= WAVE_CLEARANCE:
                        self.spawn(kind, *p)
                        break

    def _mission(self, dt: float) -> None:
        if self.complete:
            return
        if self.mission == "nests":
            done = all(not n.alive for n in self.nests)
        elif self.mission == "hold":
            if self.map.beacon is not None and math.dist(self.pilot.pos, self.map.beacon) <= BEACON_RADIUS:
                self.hold_time += dt
            if self.hold_time > 0:
                self.wave_timer -= dt
                if self.wave_timer <= 0:
                    self.wave_timer += WAVE_PERIOD * self.pace
                    self._spawn_wave()
            done = self.hold_time >= HOLD_TIME
        else:
            if self.carrying:
                self.core = self.pilot.pos
            done = self.carrying and self.at_pad()
        if done:
            self.complete = True
            self._events.append(("complete", self.mission))
