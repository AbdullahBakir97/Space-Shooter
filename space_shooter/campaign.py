"""The war: a star-system map where each loop is one turn. Pure module: no pygame import."""

from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path

from space_shooter.encounters import ENCOUNTERS, Encounter

SYSTEM_PATH = Path(__file__).resolve().parent / "data" / "system.json"
HOME = "home"
GATE = "c1"
CORE = "c2"
GATE_NEEDS_MIDDLE = 4
MAX_ROUTE = 3
SWARM_HULL = 1.25
HIVE_HULL = 1.5
HIVE_PACE = 0.8  # hive scripts run 20% faster
HIVE_AGE = 3  # turns of swarm control before ground becomes a hive
PART_COST = 800
FORTIFY_COST = 1000
MAX_REQUISITION = 2
PART_KINDS = ("turret", "slug", "tractor", "armour", "thruster", "claw")


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    ring: str
    kind: str
    template: int
    yield_: int
    ground: bool
    pos: tuple[int, int]


@dataclass(frozen=True)
class System:
    nodes: dict[str, Node]
    lanes: dict[str, frozenset[str]]
    swarm_start: tuple[str, ...]

    def neighbours(self, node_id: str) -> frozenset[str]:
        return self.lanes.get(node_id, frozenset())

    def distance_to_home(self, node_id: str) -> int:
        """Lane steps from home (home itself is 0)."""
        seen, queue = {HOME: 0}, deque([HOME])
        while queue:
            current = queue.popleft()
            for nxt in self.neighbours(current):
                if nxt not in seen:
                    seen[nxt] = seen[current] + 1
                    queue.append(nxt)
        return seen.get(node_id, 10**6)

    def ring_ids(self, ring: str) -> list[str]:
        return [n for n, node in self.nodes.items() if node.ring == ring]


def load_system(path: Path | None = None) -> System:
    """Load and validate the system map; raise ValueError on any problem."""
    try:
        raw = json.loads(Path(path or SYSTEM_PATH).read_text(encoding="utf-8"))
        nodes: dict[str, Node] = {}
        for item in raw["nodes"]:
            node = Node(
                id=str(item["id"]),
                name=str(item["name"]),
                ring=str(item["ring"]),
                kind=str(item["kind"]),
                template=int(item["template"]),
                yield_=int(item.get("yield", 0)),
                ground=bool(item.get("ground", False)),
                pos=(int(item["pos"][0]), int(item["pos"][1])),
            )
            if node.id in nodes:
                raise ValueError(f"duplicate node {node.id!r}")
            if not 0 <= node.template < len(ENCOUNTERS):
                raise ValueError(f"node {node.id!r} has an unknown template")
            nodes[node.id] = node
        lanes: dict[str, set[str]] = {n: set() for n in nodes}
        for a, b in raw["lanes"]:
            if a not in nodes or b not in nodes:
                raise ValueError(f"lane {a}-{b} names an unknown node")
            lanes[a].add(b)
            lanes[b].add(a)
        swarm = tuple(raw.get("swarm_start", []))
    except (OSError, KeyError, TypeError, IndexError) as exc:
        raise ValueError(f"bad system data: {exc}") from exc
    if HOME not in nodes or any(s not in nodes for s in swarm):
        raise ValueError("system needs a home node and known swarm starts")
    return System(nodes, {n: frozenset(v) for n, v in lanes.items()}, swarm)


@dataclass
class CampaignState:
    owner: dict[str, str]
    hive_age: dict[str, int] = field(default_factory=dict)
    fortified: set[str] = field(default_factory=set)
    salvage: int = 0
    turn: int = 0
    status: str = "active"  # active | won | lost
    requisition: list[str] = field(default_factory=list)

    def held(self) -> list[str]:
        return [n for n, o in self.owner.items() if o == "player"]

    def is_hive(self, node_id: str) -> bool:
        return self.owner.get(node_id) == "swarm" and self.hive_age.get(node_id, 0) >= HIVE_AGE

    def to_dict(self) -> dict:
        return {
            "owner": dict(self.owner),
            "hive_age": dict(self.hive_age),
            "fortified": sorted(self.fortified),
            "salvage": self.salvage,
            "turn": self.turn,
            "status": self.status,
            "requisition": list(self.requisition),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> CampaignState:
        return cls(
            owner={str(k): str(v) for k, v in raw["owner"].items()},
            hive_age={str(k): int(v) for k, v in raw.get("hive_age", {}).items()},
            fortified=set(raw.get("fortified", [])),
            salvage=int(raw.get("salvage", 0)),
            turn=int(raw.get("turn", 0)),
            status=str(raw.get("status", "active")),
            requisition=[str(k) for k in raw.get("requisition", [])],
        )


@dataclass
class TurnReport:
    claimed: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)
    swarm_took: list[str] = field(default_factory=list)
    hives: list[str] = field(default_factory=list)
    fortify_spent: list[str] = field(default_factory=list)
    home_threatened: bool = False
    status: str = "active"
    salvage_gained: int = 0


def new_campaign(system: System) -> CampaignState:
    owner = dict.fromkeys(system.nodes, "neutral")
    owner[HOME] = "player"
    for node_id in system.swarm_start:
        owner[node_id] = "swarm"
    return CampaignState(owner=owner)


def locked(system: System, state: CampaignState, node_id: str) -> bool:
    """The gate opens once four middle-ring locations are held; the core needs the gate."""
    if node_id == GATE:
        held_middle = sum(1 for n in system.ring_ids("middle") if state.owner.get(n) == "player")
        return held_middle < GATE_NEEDS_MIDDLE
    if node_id == CORE:  # a route may still pass through the gate on its way in (see valid_route)
        return state.owner.get(GATE) != "player"
    return False


def valid_route(system: System, state: CampaignState, route: list[str]) -> bool:
    if not 1 <= len(route) <= MAX_ROUTE or len(set(route)) != len(route):
        return False
    held = set(state.held())
    for i, node_id in enumerate(route):
        if node_id not in system.nodes or node_id == HOME or node_id in held:
            return False
        if locked(system, state, node_id) and not (node_id == CORE and i > 0 and route[i - 1] == GATE):
            return False
        anchors = held if i == 0 else {route[i - 1]}
        if not system.neighbours(node_id) & anchors:
            return False
    return True


def valid_prefix(system: System, state: CampaignState, route: list[str]) -> list[str]:
    """The longest leading part of ``route`` that is still a valid route."""
    for end in range(len(route), 0, -1):
        if valid_route(system, state, route[:end]):
            return list(route[:end])
    return []


def route_encounters(system: System, state: CampaignState, route: list[str]) -> tuple[Encounter, ...]:
    """Each location plays as its base encounter, renamed, toughened on swarm ground and hives."""
    out = []
    for node_id in route:
        node = system.nodes[node_id]
        base = ENCOUNTERS[node.template]
        enc = replace(base, name=node.name)
        if state.is_hive(node_id):
            script = tuple(replace(e, at=e.at * HIVE_PACE) for e in base.script)
            enc = replace(enc, hull=HIVE_HULL, script=script)
        elif state.owner.get(node_id) == "swarm":
            enc = replace(enc, hull=SWARM_HULL)
        out.append(enc)
    return tuple(out)


def spread_count(state: CampaignState) -> int:
    hives = sum(1 for n in state.owner if state.is_hive(n))
    return min(3, 1 + state.turn // 4) + hives // 2


def swarm_turn(system: System, state: CampaignState, rng: random.Random, report: TurnReport) -> None:
    """The swarm ages its ground into hives, then spreads toward home."""
    for node_id, who in state.owner.items():
        if who == "swarm":
            state.hive_age[node_id] = state.hive_age.get(node_id, 0) + 1
            if state.hive_age[node_id] == HIVE_AGE:
                report.hives.append(node_id)
        else:
            state.hive_age.pop(node_id, None)
    for _ in range(spread_count(state)):
        swarm = {n for n, o in state.owner.items() if o == "swarm"}
        candidates = {n for s in swarm for n in system.neighbours(s)} - swarm
        if not candidates:
            break
        closest = min(system.distance_to_home(n) for n in candidates)
        target = rng.choice(sorted(n for n in candidates if system.distance_to_home(n) == closest))
        if target in state.fortified:
            state.fortified.discard(target)
            report.fortify_spent.append(target)
            continue
        if state.owner[target] == "player":
            report.lost.append(target)
        state.owner[target] = "swarm"
        report.swarm_took.append(target)
        if target == HOME:
            state.status = "lost"
            break
    report.home_threatened = any(state.owner.get(n) == "swarm" for n in system.neighbours(HOME))
    report.status = state.status


def apply_run(
    system: System,
    state: CampaignState,
    route: list[str],
    cleared: int,
    run_salvage: int,
    warden_killed: bool,
    rng: random.Random,
) -> TurnReport:
    """Close one turn: claim cleared ground, pay salvage and yields, then let the swarm move."""
    report = TurnReport()
    for node_id in route[: max(0, cleared)]:
        state.owner[node_id] = "player"
        state.hive_age.pop(node_id, None)
        report.claimed.append(node_id)
    yields = sum(system.nodes[n].yield_ for n in state.held())
    report.salvage_gained = run_salvage + yields
    state.salvage += report.salvage_gained
    if warden_killed:
        state.status = "won"
        report.status = "won"
    else:
        swarm_turn(system, state, rng, report)
    state.turn += 1
    return report


def requisition(state: CampaignState, kind: str) -> bool:
    """Buy a part to be fitted at the next launch."""
    if kind not in PART_KINDS or len(state.requisition) >= MAX_REQUISITION or state.salvage < PART_COST:
        return False
    state.salvage -= PART_COST
    state.requisition.append(kind)
    return True


def fortify(state: CampaignState, node_id: str) -> bool:
    """Protect a held location against one swarm attack."""
    if state.owner.get(node_id) != "player" or node_id in state.fortified or state.salvage < FORTIFY_COST:
        return False
    state.salvage -= FORTIFY_COST
    state.fortified.add(node_id)
    return True
