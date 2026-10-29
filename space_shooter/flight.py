"""Flying the star system: lanes, the tug's drift and ash wear, swarm patrols.

Pure module: no pygame import. World units are pixels of the scrolling region.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from space_shooter.campaign import HOME, CampaignState, Node, System, patrol_count

SCALE = 3
WORLD = (2400, 1920)
BASE_SPEED = 260.0
LANE_BOOST = 1.6
LANE_WIDTH = 40.0
ASH_PERIOD = 4.0  # seconds off a lane per point of hull worn away
EASE = 0.25  # seconds for the tug's velocity to settle on the input
MARKER_RADIUS = 48.0
DOCK_RADIUS = 90.0
PATROL_SPEED = 140.0
CHASE_SPEED = 220.0
DETECT = 320.0
DETECT_ON_LANE = 160.0
GIVE_UP = 4.0
CATCH = 26.0
SPAWN_CLEARANCE = 600.0
REPAIR = 25
RADAR_RANGE = 900.0

Point = tuple[float, float]


def world_pos(node: Node) -> Point:
    return (node.pos[0] * SCALE, node.pos[1] * SCALE)


def _closest_on_segment(p: Point, a: Point, b: Point) -> tuple[float, Point]:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length_sq))
    q = (ax + dx * t, ay + dy * t)
    return math.hypot(p[0] - q[0], p[1] - q[1]), q


class Lanes:
    """The system's lanes as world-space segments."""

    def __init__(self, system: System) -> None:
        self.system = system
        seen: set[frozenset[str]] = set()
        self.segments: list[tuple[str, str, Point, Point]] = []
        for a in sorted(system.lanes):
            for b in sorted(system.lanes[a]):
                key = frozenset((a, b))
                if key not in seen:
                    seen.add(key)
                    self.segments.append((a, b, world_pos(system.nodes[a]), world_pos(system.nodes[b])))

    def nearest(self, point: Point) -> tuple[float, Point, tuple[str, str]]:
        best = None
        for a, b, pa, pb in self.segments:
            dist, q = _closest_on_segment(point, pa, pb)
            if best is None or dist < best[0]:
                best = (dist, q, (a, b))
        return best

    def on_lane(self, point: Point) -> bool:
        return self.nearest(point)[0] <= LANE_WIDTH


@dataclass
class Tug:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    ash: float = 0.0

    def step(self, move: tuple[float, float], dt: float, on_lane: bool) -> int:
        """Drift toward the input; return the hull worn away by ash this step (0 or 1)."""
        speed = BASE_SPEED * (LANE_BOOST if on_lane else 1.0)
        mx, my = move
        norm = math.hypot(mx, my)
        if norm > 1:
            mx, my = mx / norm, my / norm
        k = min(1.0, dt / EASE)
        self.vx += (mx * speed - self.vx) * k
        self.vy += (my * speed - self.vy) * k
        self.x = max(0.0, min(WORLD[0], self.x + self.vx * dt))
        self.y = max(0.0, min(WORLD[1], self.y + self.vy * dt))
        if on_lane:
            self.ash = 0.0
            return 0
        self.ash += dt
        if self.ash >= ASH_PERIOD:
            self.ash -= ASH_PERIOD
            return 1
        return 0


@dataclass
class Patrol:
    a: str
    b: str
    along: float  # px travelled from a toward b while wandering
    mode: str = "wander"  # wander | chase | return
    unseen: float = 0.0
    x: float = 0.0
    y: float = 0.0
    seen_x: float = 0.0  # where the tug was last spotted
    seen_y: float = 0.0


def _lane_point(system: System, a: str, b: str, along: float) -> Point:
    pa, pb = world_pos(system.nodes[a]), world_pos(system.nodes[b])
    length = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1.0
    t = max(0.0, min(1.0, along / length))
    return (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)


def patrol_pos(system: System, p: Patrol) -> Point:
    if p.mode == "wander":
        return _lane_point(system, p.a, p.b, p.along)
    return (p.x, p.y)


def spawn_patrols(
    system: System, lanes: Lanes, state: CampaignState, tug_pos: Point, rng: random.Random
) -> list[Patrol]:
    """Patrols start on lanes touching swarm ground, heading away from your ground, clear of the tug."""
    options = []
    for a, b, _, _ in lanes.segments:
        if "swarm" not in (state.owner[a], state.owner[b]):
            continue
        if state.owner[b] == "player" or b == HOME:
            a, b = b, a
        if state.owner[b] == "player":
            continue
        options.append((a, b))
    patrols: list[Patrol] = []
    for _ in range(patrol_count(state)):
        rng.shuffle(options)
        for a, b in options:
            pa, pb = world_pos(system.nodes[a]), world_pos(system.nodes[b])
            length = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            along = rng.uniform(0.2, 0.8) * length
            x, y = _lane_point(system, a, b, along)
            if math.hypot(x - tug_pos[0], y - tug_pos[1]) >= SPAWN_CLEARANCE:
                patrols.append(Patrol(a, b, along, x=x, y=y))
                break
    return patrols


def _toward(p: Patrol, target: Point, speed: float, dt: float) -> None:
    dx, dy = target[0] - p.x, target[1] - p.y
    dist = math.hypot(dx, dy)
    if dist <= speed * dt or dist == 0:
        p.x, p.y = target
    else:
        p.x += dx / dist * speed * dt
        p.y += dy / dist * speed * dt


def _next_lane(system: System, state: CampaignState, p: Patrol, rng: random.Random) -> None:
    here = p.b
    onward = sorted(n for n in system.neighbours(here) if n != p.a and state.owner[n] != "player")
    p.a, p.b, p.along = here, (rng.choice(onward) if onward else p.a), 0.0


def step_patrol(
    p: Patrol,
    system: System,
    lanes: Lanes,
    state: CampaignState,
    tug_pos: Point,
    tug_on_lane: bool,
    dt: float,
    rng: random.Random,
) -> bool:
    """Advance one patrol; return True when it catches the tug."""
    if p.mode == "wander":
        p.along += PATROL_SPEED * dt
        pa, pb = world_pos(system.nodes[p.a]), world_pos(system.nodes[p.b])
        if p.along >= math.hypot(pb[0] - pa[0], pb[1] - pa[1]):
            _next_lane(system, state, p, rng)
        p.x, p.y = _lane_point(system, p.a, p.b, p.along)
    elif p.mode == "return":
        _dist, target, (a, b) = lanes.nearest((p.x, p.y))
        _toward(p, target, PATROL_SPEED, dt)
        if (p.x, p.y) == target:
            if state.owner[b] == "player":
                a, b = b, a
            pa = world_pos(system.nodes[a])
            p.a, p.b, p.along, p.mode = a, b, math.hypot(p.x - pa[0], p.y - pa[1]), "wander"
    dist = math.hypot(tug_pos[0] - p.x, tug_pos[1] - p.y)
    if dist <= (DETECT_ON_LANE if tug_on_lane else DETECT):
        p.mode, p.unseen = "chase", 0.0
        p.seen_x, p.seen_y = tug_pos
    elif p.mode == "chase":
        p.unseen += dt
        if p.unseen >= GIVE_UP:
            p.mode = "return"
    if p.mode == "chase":
        _toward(p, (p.seen_x, p.seen_y), CHASE_SPEED, dt)
        dist = math.hypot(tug_pos[0] - p.x, tug_pos[1] - p.y)
    return dist <= CATCH


def repairable(system: System, state: CampaignState, node_id: str, repaired: set[str]) -> bool:
    """A held station (never home) patches the hull once per loop."""
    node = system.nodes.get(node_id)
    return (
        node is not None
        and node_id != HOME
        and node.kind == "station"
        and state.owner.get(node_id) == "player"
        and node_id not in repaired
    )
