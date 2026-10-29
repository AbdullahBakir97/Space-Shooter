import math
import random

import pytest

from space_shooter import flight
from space_shooter.campaign import load_system, new_campaign, patrol_count
from space_shooter.flight import Lanes, Patrol, Tug


@pytest.fixture(scope="module")
def system():
    return load_system()


@pytest.fixture(scope="module")
def lanes(system):
    return Lanes(system)


def run_tug(tug, move, seconds, on_lane):
    worn = 0
    for _ in range(round(seconds * 60)):
        worn += tug.step(move, 1 / 60, on_lane)
    return worn


def test_world_pos_scales(system):
    assert flight.world_pos(system.nodes["home"]) == (1200, 1770)


def test_on_lane(system, lanes):
    home, o1 = flight.world_pos(system.nodes["home"]), flight.world_pos(system.nodes["o1"])
    mid = ((home[0] + o1[0]) / 2, (home[1] + o1[1]) / 2)
    assert lanes.on_lane(mid)
    dx, dy = o1[0] - home[0], o1[1] - home[1]
    length = math.hypot(dx, dy)
    nx, ny = dy / length, -dx / length
    assert not lanes.on_lane((mid[0] + nx * 41, mid[1] + ny * 41))
    assert not lanes.on_lane((5, 5))
    dist, point, lane = lanes.nearest(mid)
    assert dist == pytest.approx(0, abs=1e-6) and set(lane) == {"home", "o1"}


def test_tug_speed_on_and_off_lane():
    off, on = Tug(100, 100), Tug(100, 100)
    run_tug(off, (1, 0), 2, on_lane=False)
    run_tug(on, (1, 0), 2, on_lane=True)
    assert math.hypot(off.vx, off.vy) == pytest.approx(260, rel=0.01)
    assert math.hypot(on.vx, on.vy) == pytest.approx(416, rel=0.01)


def test_tug_stays_in_world():
    tug = Tug(10, 10)
    run_tug(tug, (-1, -1), 2, on_lane=True)
    assert (tug.x, tug.y) == (0, 0)
    tug = Tug(2390, 1910)
    run_tug(tug, (1, 1), 2, on_lane=True)
    assert (tug.x, tug.y) == flight.WORLD


def test_ash_wear_every_four_seconds():
    assert run_tug(Tug(100, 100), (0, 0), 8.05, on_lane=False) == 2
    assert run_tug(Tug(100, 100), (0, 0), 8.05, on_lane=True) == 0
    tug = Tug(100, 100)
    run_tug(tug, (0, 0), 3, on_lane=False)
    run_tug(tug, (0, 0), 0.1, on_lane=True)  # a lane clears the ash
    assert run_tug(tug, (0, 0), 3, on_lane=False) == 0


def swarmed(system):
    s = new_campaign(system)
    for n in ("o3", "o4", "m3", "m4"):
        s.owner[n] = "swarm"
    return s


def test_patrols_spawn_clear_of_tug(system, lanes):
    s = swarmed(system)
    tug = flight.world_pos(system.nodes["home"])
    patrols = flight.spawn_patrols(system, lanes, s, tug, random.Random(0))
    assert len(patrols) == patrol_count(s) == 3
    for p in patrols:
        x, y = flight.patrol_pos(system, p)
        assert math.hypot(x - tug[0], y - tug[1]) >= flight.SPAWN_CLEARANCE
        assert "swarm" in (s.owner[p.a], s.owner[p.b]) and s.owner[p.b] != "player"


def test_patrol_wanders_on_lanes(system, lanes):
    s = swarmed(system)
    s.owner["m1"] = "player"
    rng = random.Random(3)
    patrols = flight.spawn_patrols(system, lanes, s, (0, 0), rng)
    far = (2400, 0)  # never close enough to notice
    for _ in range(30 * 60):
        for p in patrols:
            assert not flight.step_patrol(p, system, lanes, s, far, True, 1 / 60, rng)
            assert p.mode == "wander" and lanes.on_lane(flight.patrol_pos(system, p))
            assert s.owner[p.b] != "player"


def patrol_at(system, a="o3", b="m3"):
    p = Patrol(a, b, 10.0)
    return p, flight.patrol_pos(system, p)


def test_patrol_detects_by_range(system, lanes):
    s = swarmed(system)
    rng = random.Random(0)
    for tug_on_lane, offset, chases in ((False, 300, True), (True, 300, False), (True, 150, True)):
        p, (x, y) = patrol_at(system)
        flight.step_patrol(p, system, lanes, s, (x, y - offset), tug_on_lane, 1 / 60, rng)
        assert (p.mode == "chase") is chases, (tug_on_lane, offset)


def test_patrol_gives_up(system, lanes):
    s = swarmed(system)
    rng = random.Random(0)
    p, (x, y) = patrol_at(system)
    flight.step_patrol(p, system, lanes, s, (x, y - 200), False, 1 / 60, rng)
    assert p.mode == "chase"
    gone = (x + 1500, y - 1000)
    for _ in range(round(3.9 * 60)):
        flight.step_patrol(p, system, lanes, s, gone, False, 1 / 60, rng)
    assert p.mode == "chase"
    for _ in range(12):
        flight.step_patrol(p, system, lanes, s, gone, False, 1 / 60, rng)
    assert p.mode != "chase"
    for _ in range(20 * 60):  # it finds its way back onto a lane and wanders again
        flight.step_patrol(p, system, lanes, s, gone, False, 1 / 60, rng)
    assert p.mode == "wander" and lanes.on_lane(flight.patrol_pos(system, p))


def test_patrol_catch(system, lanes):
    s = swarmed(system)
    p, (x, y) = patrol_at(system)
    assert flight.step_patrol(p, system, lanes, s, (x + 10, y), False, 1 / 60, random.Random(0))


def test_repairable(system):
    s = new_campaign(system)
    s.owner.update({"m2": "player", "m1": "player"})
    repaired: set[str] = set()
    assert flight.repairable(system, s, "m2", repaired)
    repaired.add("m2")
    assert not flight.repairable(system, s, "m2", repaired)
    assert not flight.repairable(system, s, "m1", repaired)  # a planet, not a station
    assert not flight.repairable(system, s, "home", repaired)
    assert not flight.repairable(system, s, "o2", repaired)  # not held
