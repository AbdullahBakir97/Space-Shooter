"""Landing on planets and fighting on foot, through the real scenes."""

import pygame
import pytest

from space_shooter import flight, ground
from space_shooter.game import Game
from space_shooter.ground import GroundInputs
from space_shooter.scenes.flight import FlightScene
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.ground import GroundScene
from space_shooter.scenes.loop_end import LoopEndScene
from space_shooter.settings_store import Settings
from tests.helpers import press, run_frames, silence_radio


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    silence_radio(g)
    yield g
    pygame.quit()


def take_off_ready(game, monkeypatch, node="m1"):
    """Fly into a planet and return the ground scene that opens."""
    monkeypatch.setattr(game, "move_vector", lambda: (0.0, 0.0))
    scene = FlightScene(game, seed=1)
    scene.patrols = []
    game.scenes.clear_to(scene)
    x, y = flight.world_pos(game.system.nodes[node])
    scene.tug.x, scene.tug.y = x + 5, y
    run_frames(game, 1)
    return scene, game.scenes.top


def finish_mission(g):
    for n in g.world.nests:
        g.world.damage_nest(n, 1e6)
    g.world.score = 300


def test_flying_into_planet_lands(game, monkeypatch):
    _flight, g = take_off_ready(game, monkeypatch)
    assert isinstance(g, GroundScene) and g.node_id == "m1" and g.world.mission == "nests"
    assert g.world.pilot.pos == g.world.map.pad


def test_mission_complete_claims_and_takeoff_returns(game, monkeypatch):
    fl, g = take_off_ready(game, monkeypatch)
    finish_mission(g)
    run_frames(game, 1)
    assert g.world.complete and game.campaign().owner["m1"] == "player"
    assert fl.run.carried == 300 and fl.run.reached == 2
    g.world.survivors[0].state = "follow"
    press(game, "confirm")
    assert game.scenes.top is fl and g.fight_over
    assert fl.run.carried == 300 + ground.SQUAD_BONUS
    run_frames(game, 2)
    assert game.scenes.top is fl and fl.run.state.owner["m1"] == "player"
    x, y = flight.world_pos(game.system.nodes["m1"])
    assert ((fl.tug.x - x) ** 2 + (fl.tug.y - y) ** 2) ** 0.5 > flight.MARKER_RADIUS


def test_takeoff_needs_pad_and_completion(game, monkeypatch):
    _fl, g = take_off_ready(game, monkeypatch)
    press(game, "confirm")
    assert game.scenes.top is g  # the mission is not done
    finish_mission(g)
    run_frames(game, 1)
    g.world.pilot.x += 400
    press(game, "confirm")
    assert game.scenes.top is g  # not at the tug


def test_ground_death_ends_loop(game, monkeypatch):
    fl, g = take_off_ready(game, monkeypatch)
    g.world.score = 200
    g.world.damage_pilot(1000)
    run_frames(game, 90)
    assert isinstance(game.scenes.top, LoopEndScene)
    assert fl.run.result.salvage == 200 and game.campaign().salvage == 100 and game.campaign().turn == 1


def test_death_on_completion_frame(game, monkeypatch):  # review focus 1
    fl, g = take_off_ready(game, monkeypatch)
    finish_mission(g)
    g.world.damage_pilot(1000)
    run_frames(game, 90)
    assert isinstance(game.scenes.top, LoopEndScene)
    assert fl.run.result.report.claimed == ["m1"] and game.save.loop == 2 and len(game.save.records) == 1
    assert fl.run.result.salvage == 300


def test_held_planet_does_not_land(game, monkeypatch):  # review focus 4
    state = game.campaign()
    state.owner["m1"] = "player"
    game.store_campaign(state)
    fl, top = take_off_ready(game, monkeypatch)
    run_frames(game, 5)
    assert game.scenes.top is fl and not any(isinstance(s, (GroundScene, GameplayScene)) for s in game.scenes.stack)


def test_abandon_on_ground(game, monkeypatch):  # review focus 5
    fl, g = take_off_ready(game, monkeypatch)
    g.world.score = 120
    press(game, "back")
    game.scenes.top.abandon()
    assert isinstance(game.scenes.top, LoopEndScene)
    assert fl.run.result.salvage == 120 and game.campaign().salvage == 60 and game.save.loop == 2
    game.close_open_loop()
    assert game.save.loop == 2


def test_window_close_on_ground(game, monkeypatch):
    fl, g = take_off_ready(game, monkeypatch)
    g.world.score = 80
    game.close_open_loop()
    game.close_open_loop()
    assert fl.run.result.salvage == 80 and game.campaign().turn == 1 and game.save.loop == 2


def test_ground_draws_every_state(game, monkeypatch):
    for node in ("m1", "m3", "m5"):
        fl, g = take_off_ready(game, monkeypatch, node)
        w = g.world
        w.spawn("crawler", w.pilot.x + 120, w.pilot.y)
        w.spawn("spitter", w.pilot.x + 200, w.pilot.y + 40)
        w.survivors[0].state = "follow"
        w.survivors[1].body.hp = 0
        w.give_weapon("scattergun")
        w.step(1 / 60, GroundInputs(grenade=True, fire=True, aim=(w.pilot.x + 100, w.pilot.y)))
        w.hold_time = 12.0
        w.carrying = node == "m5"
        run_frames(game, 20)
        game.scenes.draw(game.screen)
        game.close_open_loop()


def test_mouse_aim_and_keys(game, monkeypatch):
    _fl, g = take_off_ready(game, monkeypatch)
    g.world.give_weapon("rifle")
    for key in (pygame.K_2, pygame.K_r, pygame.K_g, pygame.K_q):
        g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (500, 200))
    g.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 200), rel=(1, 1), buttons=(0, 0, 0)))
    g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=3))
    assert g.pending.slot == 2 and g.pending.reload and g.pending.grenade and g.pending.order[0] == "move"
    run_frames(game, 1)
    assert g.world.arsenal.current == "rifle" and g.world.arsenal.grenades == ground.START_GRENADES - 1
    assert g.world.aim == g.to_world((500, 200))
    press(game, "dash")
    run_frames(game, 1)
    assert g.world.rolling


def test_headless_ground_autopilot(game, monkeypatch):
    """Fly to KESS, land, burn out every nest with scripted inputs, take off and dock."""
    fl, g = take_off_ready(game, monkeypatch, "m1")
    w = g.world
    w.invulnerable_for_tests = True

    def script():
        alive = [n for n in w.nests if n.alive]
        if not alive:
            return GroundInputs()
        nest = alive[0]
        if not w.map.line_of_sight(w.pilot.pos, nest.body.pos) or abs(w.pilot.x - nest.body.x) > 150:
            spot = w.map.cast(nest.body.pos, (nest.body.x - 120, nest.body.y))
            w.pilot.x, w.pilot.y = spot  # the autopilot walks; this test only needs it to arrive
        return GroundInputs(fire=True, aim=nest.body.pos)

    g.inputs_override = script
    for _ in range(60 * 90):
        if w.complete:
            break
        run_frames(game, 1)
    assert w.complete and game.campaign().owner["m1"] == "player" and w.score >= 4 * ground.NEST_SCORE
    w.pilot.x, w.pilot.y = w.map.pad
    press(game, "confirm")
    assert game.scenes.top is fl
    run_frames(game, 1)  # back in space beside KESS
    hx, hy = flight.world_pos(game.system.nodes["home"])
    fl.tug.x, fl.tug.y = hx, hy - 30
    run_frames(game, 1)
    press(game, "confirm")
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.title == "DOCKED"
    assert card.result.report.claimed == ["m1"] and game.campaign().salvage >= 4 * ground.NEST_SCORE
