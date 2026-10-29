import math
import random

import pytest

from space_shooter import ground
from space_shooter.ground import Arsenal, Body, GroundMap, generate_map, move_body


def walled_map():
    """An empty field with a rock wall at tile column 10, rows 0..19 (one gap at row 15)."""
    gmap = GroundMap.empty(30, 20)
    for row in range(20):
        if row != 15:
            gmap.tiles[row][10] = ground.ROCK
    return gmap


def test_map_size_and_determinism():
    a, b = generate_map("m1"), generate_map("m1")
    assert len(a.tiles) == ground.MAP_H and len(a.tiles[0]) == ground.MAP_W
    assert a.tiles == b.tiles and a.nests == b.nests and a.survivors == b.survivors
    assert generate_map("m3").tiles != a.tiles
    assert len(a.nests) == 4 and len(generate_map("m5").nests) == 2 and not generate_map("m3").nests
    assert generate_map("m3").beacon is not None and generate_map("m5").core is not None
    assert len(a.survivors) == 3 and len(a.crates) == 4
    assert not a.blocked(*a.pad)


@pytest.mark.parametrize("node", ["m1", "m3", "m5"])
def test_points_reachable(node):
    gmap = generate_map(node)
    points = [*gmap.nests, *gmap.survivors, *gmap.crates]
    points += [p for p in (gmap.beacon, gmap.core) if p is not None]
    for p in points:
        assert not gmap.blocked(*p) and gmap.reachable_from_pad(p), (node, p)
        assert math.dist(p, gmap.pad) >= 400


def corners_free(gmap, body):
    r = body.radius
    return all(not gmap.blocked(body.x + dx, body.y + dy) for dx in (-r, r) for dy in (-r, r))


def test_bodies_never_inside_rock():
    gmap = generate_map("m1")
    rng = random.Random(4)
    body = Body(*gmap.pad, radius=12, hp=10, max_hp=10)
    for _ in range(600):
        move_body(gmap, body, rng.uniform(-30, 30), rng.uniform(-30, 30))
        assert corners_free(gmap, body)
    wall = walled_map()
    body = Body(9 * 32 + 4, 5 * 32, radius=12, hp=1, max_hp=1)
    for _ in range(20):
        move_body(wall, body, 20, 0)  # straight into the wall
        assert corners_free(wall, body) and body.x < 10 * 32


def test_line_of_sight_blocked_by_rock():
    gmap = walled_map()
    assert not gmap.line_of_sight((5 * 32, 5 * 32), (15 * 32, 5 * 32))
    assert gmap.line_of_sight((5 * 32, 15.5 * 32), (15 * 32, 15.5 * 32))  # through the gap
    hit = gmap.cast((5 * 32, 5 * 32), (15 * 32, 5 * 32))
    assert hit[0] < 10 * 32 and not gmap.blocked(*hit)


def test_weapon_numbers():
    w = ground.WEAPONS
    assert (w["sidearm"].damage, w["sidearm"].shots, w["sidearm"].period, w["sidearm"].mag) == (2, 1, 0.25, None)
    assert (w["rifle"].damage, w["rifle"].period, w["rifle"].mag, w["rifle"].reserve, w["rifle"].reload) == (
        2,
        0.10,
        30,
        90,
        1.6,
    )
    sg = w["scattergun"]
    assert (sg.damage, sg.shots, sg.spread, sg.period, sg.mag, sg.reserve, sg.reload) == (2, 6, 0.35, 0.70, 6, 24, 2.0)
    assert (ground.SHOT_SPEED, ground.SHOT_LIFE, ground.GRENADE_DAMAGE, ground.GRENADE_RADIUS) == (700, 0.9, 12, 90)


def fire_all(arsenal, rng, seconds):
    shots = []
    for _ in range(round(seconds * 60)):
        arsenal.update(1 / 60)
        shots += arsenal.trigger((0, 0), (100, 0), rng)
    return shots


def test_rifle_magazine_and_reload():
    a = Arsenal()
    a.give("rifle")
    a.select(2)
    rng = random.Random(0)
    shots = fire_all(a, rng, 3.05)  # 30 rounds take 3 s; then the reload starts on its own
    assert len(shots) == 30 and a.mag["rifle"] == 0 and a.reloading > 0
    fire_all(a, rng, 1.6)
    assert a.mag["rifle"] > 0 and a.mag["rifle"] + a.reserve["rifle"] <= 90


def test_scattergun_pellets_and_spread():
    a = Arsenal()
    a.give("scattergun")
    a.select(3)
    shots = a.trigger((0, 0), (100, 0), random.Random(1))
    assert len(shots) == 6 and a.mag["scattergun"] == 5
    angles = [math.atan2(s.vy, s.vx) for s in shots]
    assert max(abs(x) for x in angles) <= 0.35 / 2 + 1e-9
    assert all(math.hypot(s.vx, s.vy) == pytest.approx(700) and s.friendly for s in shots)


def test_sidearm_never_runs_dry():
    a = Arsenal()
    assert len(fire_all(a, random.Random(0), 10)) == 40


def test_select_only_owned():
    a = Arsenal()
    a.select(3)
    assert a.current == "sidearm"
    a.give("scattergun")
    a.select(3)
    assert a.current == "scattergun"


def test_grenade_stops_at_wall():
    gmap = walled_map()
    a = Arsenal()
    origin = (8 * 32, 5 * 32)
    g = a.throw(gmap, origin, (13 * 32, 5 * 32))
    assert g is not None and a.grenades == ground.START_GRENADES - 1
    assert g.tx < 10 * 32 and gmap.line_of_sight(origin, (g.tx, g.ty))
    far = a.throw(gmap, (2 * 32, 15 * 32), (29 * 32, 15 * 32))
    assert math.dist((2 * 32, 15 * 32), (far.tx, far.ty)) <= ground.GRENADE_RANGE + 1e-6
    assert a.throw(gmap, origin, origin) is None  # out of grenades


def test_pickup_gives_weapon_then_ammo():
    a = Arsenal()
    rng = random.Random(0)
    first, second = a.open_crate(rng), a.open_crate(rng)
    assert {"rifle", "scattergun"} <= set(a.owned) and first != second
    before = a.reserve["rifle"] + a.reserve["scattergun"]
    a.open_crate(rng)
    assert a.reserve["rifle"] + a.reserve["scattergun"] > before
    assert a.grenades == ground.MAX_GRENADES  # 2 + one per crate, capped at 4
