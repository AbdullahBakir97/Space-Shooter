import math

import pytest

from space_shooter import ground
from space_shooter.ground import Enemy, GroundInputs, GroundMap, GroundWorld, Survivor

DT = 1 / 60


def field(w=40, h=24, **points):
    gmap = GroundMap.empty(w, h)
    for name, value in points.items():
        setattr(gmap, name, value)
    return gmap


def world_on(gmap, mission="hold", **kw):
    return GroundWorld("test", mission=mission, gmap=gmap, **kw)


def run(world, seconds, inputs=None, each=None):
    events = []
    for _ in range(round(seconds * 60)):
        events += world.step(DT, each() if each else (inputs or GroundInputs()))
    return events


def at(tx, ty):
    return ((tx + 0.5) * 32, (ty + 0.5) * 32)


def test_pilot_moves_and_rolls_invulnerable():
    w = world_on(field())
    x0 = w.pilot.x
    run(w, 1.0, GroundInputs(move=(1, 0)))
    assert w.pilot.x - x0 == pytest.approx(ground.PILOT_SPEED, rel=0.03)
    events = w.step(DT, GroundInputs(move=(1, 0), roll=True))
    assert w.rolling and w.invulnerable
    w.enemies.append(Enemy("crawler", w.pilot.x + 5, w.pilot.y, hp_mult=1.0))
    run(w, 0.2, GroundInputs(move=(1, 0)))
    assert w.pilot.hp == ground.PILOT_HEALTH and not any(e[0] == "pilot_hit" for e in events)
    run(w, 0.3)
    assert not w.rolling
    w.step(DT, GroundInputs(roll=True))
    assert not w.rolling  # still cooling down


def wall_world():
    """A wall across the middle with a gap at the bottom; the pilot on the right, a crawler on the left."""
    gmap = field(30, 20)
    for row in range(0, 10):
        gmap.tiles[row][15] = ground.ROCK
    gmap.pad = at(25, 5)
    return world_on(gmap)


def test_crawler_paths_around_wall():
    w = wall_world()
    crawler = Enemy("crawler", *at(5, 5), hp_mult=100.0)
    w.enemies.append(crawler)
    w.invulnerable_for_tests = True
    run(w, 9.0)
    assert math.dist(crawler.pos, w.pilot.pos) < 40  # found the gap and reached the pilot


def test_crawler_contact_damage_cooldown():
    w = world_on(field())
    w.enemies.append(Enemy("crawler", w.pilot.x + 4, w.pilot.y, hp_mult=100.0))
    run(w, 1.0)
    hits = (ground.PILOT_HEALTH - w.pilot.hp) / ground.CRAWLER_DAMAGE
    assert hits == pytest.approx(round(1.0 / ground.CRAWLER_COOLDOWN), abs=1)


def test_spitter_keeps_range_and_needs_sight():
    w = world_on(field(60, 20))
    w.pilot.x, w.pilot.y = at(5, 10)
    spitter = Enemy("spitter", *at(9, 10), hp_mult=100.0)
    w.enemies.append(spitter)
    events = run(w, 6.0)
    d = math.dist(spitter.pos, w.pilot.pos)
    assert ground.SPIT_RANGE - 60 <= d <= ground.SPIT_RANGE + 60
    assert any(e[0] == "pilot_hit" for e in events)
    blind = wall_world()
    blind.pilot.x, blind.pilot.y = at(25, 5)
    blind.enemies.append(Enemy("spitter", *at(5, 5), hp_mult=100.0))
    early = run(blind, 1.0)
    assert not any(e[0] == "pilot_hit" for e in early)  # no clear shot through rock


def test_nest_spawns_up_to_cap_only_near():
    gmap = field(80, 20, nests=[at(70, 10)])
    w = world_on(gmap, mission="nests")
    w.pilot.x, w.pilot.y = at(2, 10)  # 2176 px away: asleep
    run(w, 12.0)
    assert not w.enemies
    w.pilot.x, w.pilot.y = at(52, 10)
    w.invulnerable_for_tests = True
    run(w, 5 * 8 + 1, GroundInputs())
    crawlers = [e for e in w.enemies if e.kind == "crawler"]
    assert len(crawlers) == ground.NEST_CAP


def test_hull_twist_and_hive_pace():
    gmap = field(nests=[at(20, 10)])
    w = world_on(gmap, mission="nests", hull=1.5, pace=0.8)
    assert w.nests[0].body.hp == pytest.approx(ground.NEST_HP * 1.5)
    assert w.nests[0].period == pytest.approx(ground.NEST_PERIOD * 0.8)
    w.spawn("crawler", *at(10, 10))
    assert w.enemies[-1].body.hp == pytest.approx(ground.CRAWLER_HP * 1.5)


def test_bullets_kill_and_score():
    w = world_on(field())
    target = Enemy("crawler", w.pilot.x + 150, w.pilot.y, hp_mult=1.0)
    target.frozen = True
    w.enemies.append(target)
    events = run(w, 1.5, GroundInputs(fire=True, aim=target.pos))
    assert ("kill", "crawler") in events and target not in w.enemies and w.score == ground.CRAWLER_SCORE


def test_grenade_damages_enemies_only():
    w = world_on(field())
    w.survivors.append(Survivor(w.pilot.x + 140, w.pilot.y, state="follow"))
    foe = Enemy("crawler", w.pilot.x + 150, w.pilot.y, hp_mult=1.5)
    foe.frozen = True
    w.enemies.append(foe)
    w.step(DT, GroundInputs(grenade=True, aim=(w.pilot.x + 150, w.pilot.y)))
    events = run(w, ground.GRENADE_FUSE + 0.1)
    assert ("explosion", (pytest.approx(w.pilot.x + 150, abs=2), pytest.approx(w.pilot.y, abs=2))) in events or any(
        e[0] == "explosion" for e in events
    )
    assert foe not in w.enemies
    assert w.survivors[0].body.hp == ground.SURVIVOR_HP and w.pilot.hp == ground.PILOT_HEALTH


def test_survivor_joins_and_follows():
    gmap = field(survivors=[at(12, 12)])
    w = world_on(gmap)
    s = w.survivors[0]
    assert s.state == "waiting"
    w.pilot.x, w.pilot.y = s.x - 40, s.y
    events = w.step(DT, GroundInputs())
    assert ("joined", 0) in events and s.state == "follow"
    run(w, 4.0, GroundInputs(move=(-1, 0)))
    run(w, 2.0)
    assert ground.FOLLOW_NEAR - 10 <= math.dist(s.pos, w.pilot.pos) <= ground.FOLLOW_FAR + 10


def test_hold_and_move_orders():
    w = world_on(field())
    s = Survivor(w.pilot.x + 60, w.pilot.y, state="follow")
    w.survivors.append(s)
    w.step(DT, GroundInputs(order="hold"))
    spot = s.pos
    run(w, 2.0, GroundInputs(move=(1, 0)))
    assert s.state == "hold" and math.dist(spot, s.pos) < 1
    goal = at(30, 5)
    w.step(DT, GroundInputs(order=("move", *goal)))
    run(w, 8.0)
    assert s.state == "hold" and math.dist(s.pos, goal) < 40
    w.step(DT, GroundInputs(order="follow"))
    assert s.state == "follow"


def test_survivor_shoots_visible_enemy():
    w = world_on(field())
    w.pilot.x, w.pilot.y = at(2, 2)
    s = Survivor(*at(10, 10), state="hold")
    w.survivors.append(s)
    foe = Enemy("spitter", *at(18, 10), hp_mult=1.0)
    foe.frozen = True
    w.enemies.append(foe)
    events = run(w, 4.0)
    assert ("kill", "spitter") in events


def test_dead_survivor_drops_ammo():
    w = world_on(field())
    s = Survivor(w.pilot.x + 200, w.pilot.y, state="hold")
    w.survivors.append(s)
    w.give_weapon("rifle")
    before = w.arsenal.reserve["rifle"]
    s.body.hp = 1
    w.damage_survivor(s, 5)
    assert not s.alive and w.squad_bonus() == 0
    w.pilot.x, w.pilot.y = s.pos
    events = w.step(DT, GroundInputs())
    assert w.arsenal.reserve["rifle"] == before + ground.SURVIVOR_DROP and any(e[0] == "pickup" for e in events)


def test_nests_mission():
    gmap = field(nests=[at(20, 10), at(30, 10)])
    w = world_on(gmap, mission="nests")
    assert "0/2" in w.objective_text()
    w.damage_nest(w.nests[0], 1e6)
    assert not w.complete and "1/2" in w.objective_text()
    w.damage_nest(w.nests[1], 1e6)
    events = w.step(DT, GroundInputs())
    assert w.complete and ("complete", "nests") in events and "RETURN" in w.objective_text()
    assert not any(e[0] == "complete" for e in w.step(DT, GroundInputs()))  # only once


def test_hold_mission_needs_presence_and_waves_come():
    gmap = field(60, 30, beacon=at(30, 15))
    w = world_on(gmap, mission="hold")
    w.invulnerable_for_tests = True
    run(w, 5.0)
    assert w.hold_time == 0 and not w.enemies
    w.pilot.x, w.pilot.y = gmap.beacon
    run(w, 13.0)
    assert w.hold_time == pytest.approx(13.0, abs=0.1) and len(w.enemies) >= 4
    run(w, ground.HOLD_TIME - 13.0 + 0.2)
    assert w.complete


def test_carry_mission():
    gmap = field(60, 20, core=at(40, 10))
    w = world_on(gmap, mission="carry")
    w.pilot.x, w.pilot.y = gmap.core
    w.step(DT, GroundInputs())
    assert w.carrying and not w.complete
    x0 = w.pilot.x
    run(w, 1.0, GroundInputs(move=(-1, 0)))
    assert x0 - w.pilot.x == pytest.approx(ground.PILOT_SPEED * ground.CARRY_SLOW, rel=0.05)
    w.pilot.x, w.pilot.y = gmap.pad
    events = w.step(DT, GroundInputs())
    assert w.complete and ("complete", "carry") in events and w.at_pad()


def test_pilot_death_event():
    w = world_on(field())
    w.damage_pilot(ground.PILOT_HEALTH + 5)
    events = w.step(DT, GroundInputs())
    assert w.dead and ("pilot_dead", None) in events
    assert w.step(DT, GroundInputs(move=(1, 0))) == []


@pytest.mark.parametrize("offset", [0.0, 0.5, 3.0, 9.0])
def test_crawler_unsticks_from_corner(offset):
    gmap = field(40, 24)
    gmap.tiles[9][12] = ground.ROCK
    gmap.pad = (512, 325 + offset)
    w = world_on(gmap)
    w.invulnerable_for_tests = True
    crawler = Enemy("crawler", 362, 325, hp_mult=100.0)
    w.enemies.append(crawler)
    run(w, 5.0)
    assert math.dist(crawler.pos, w.pilot.pos) < 40


@pytest.mark.parametrize("dt", [1 / 60, 1 / 30, 1 / 20])
def test_shots_never_tunnel(dt):
    gmap = field(30, 20)
    for row in range(20):
        gmap.tiles[row][10] = ground.ROCK
    gmap.pad = at(5, 10)
    w = world_on(gmap)
    target = Enemy("crawler", *at(8, 10), hp_mult=1000.0)
    target.frozen = True
    w.enemies.append(target)
    beyond = []
    for _ in range(round(5 / dt)):
        w.step(dt, GroundInputs(fire=True, aim=at(20, 10)))
        beyond += [s for s in w.shots if s.x > 10 * 32]
    hits = (target.body.max_hp - target.body.hp) / ground.WEAPONS["sidearm"].damage
    assert not beyond and hits >= 19  # every round in 5 s hit the crawler first


def test_move_order_onto_rock_settles():
    gmap = field()
    gmap.tiles[10][20] = ground.ROCK
    w = world_on(gmap)
    s = Survivor(w.pilot.x + 50, w.pilot.y, state="follow")
    w.survivors.append(s)
    w.step(DT, GroundInputs(order=("move", *at(20, 10))))
    run(w, 10.0)
    assert s.state == "hold" and not gmap.blocked(*s.pos)
