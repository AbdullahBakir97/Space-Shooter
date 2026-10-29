"""The star system flown through the real scenes."""

import math

import pygame
import pytest

from space_shooter import flight
from space_shooter.flight import Patrol
from space_shooter.game import Game
from space_shooter.scenes.chart import ChartScene
from space_shooter.scenes.flight import FlightScene
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.hangar import HangarScene
from space_shooter.scenes.loop_end import LoopEndScene
from space_shooter.settings_store import Settings
from tests.helpers import press, run_frames, select, silence_radio
from tests.test_campaign_play import clear_current


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    silence_radio(g)
    yield g
    pygame.quit()


def launch(game, monkeypatch, move=(0.0, 0.0)):
    monkeypatch.setattr(game, "move_vector", lambda: move)
    scene = FlightScene(game, seed=1)
    scene.patrols = []  # tests add the patrols they need
    game.scenes.clear_to(scene)
    return scene


def place(scene, node_id, dx=0.0, dy=0.0):
    x, y = flight.world_pos(scene.system.nodes[node_id])
    scene.tug.x, scene.tug.y = x + dx, y + dy
    scene.tug.vx = scene.tug.vy = 0.0


def test_launch_undocks_into_flight(game):
    game.save.read_logs.append("a1_open")
    game.scenes.clear_to(HangarScene(game))
    select(game, "LAUNCH")
    scene = game.scenes.top
    assert isinstance(scene, FlightScene)
    hx, hy = flight.world_pos(game.system.nodes["home"])
    assert flight.DOCK_RADIUS < math.dist((scene.tug.x, scene.tug.y), (hx, hy)) < 2 * flight.DOCK_RADIUS
    run_frames(game, 10)


def test_flying_into_location_starts_fight(game, monkeypatch):
    scene = launch(game, monkeypatch)
    place(scene, "o1", dx=10)
    run_frames(game, 1)
    top = game.scenes.top
    assert isinstance(top, GameplayScene) and top.node_id == "o1" and top.run is scene.run
    assert top.director.encounter.name == "COLD WAKE FIELD"


def test_return_after_win_outside_marker(game, monkeypatch):
    scene = launch(game, monkeypatch)
    place(scene, "o1", dx=10)
    run_frames(game, 1)
    clear_current(game, game.scenes.top)
    assert game.scenes.top is scene
    run_frames(game, 5)
    assert game.scenes.top is scene  # no second fight at ground already won
    o1 = flight.world_pos(game.system.nodes["o1"])
    assert math.dist(scene.tug_pos, o1) > flight.MARKER_RADIUS
    assert scene.run.state.owner["o1"] == "player"


def test_sealed_gate_refused(game, monkeypatch):
    scene = launch(game, monkeypatch)
    place(scene, "c1")
    run_frames(game, 3)
    assert game.scenes.top is scene and scene.prompt == "SEALED"


def test_dock_ends_loop(game, monkeypatch):
    scene = launch(game, monkeypatch)
    scene.run.carried = 300
    place(scene, "home", dy=-30)
    run_frames(game, 1)
    assert scene.prompt.endswith("DOCK")
    press(game, "confirm")
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.title == "DOCKED"
    assert game.campaign().salvage == 300 and game.campaign().turn == 1 and game.save.loop == 2


def test_confirm_far_from_home_does_nothing(game, monkeypatch):
    scene = launch(game, monkeypatch)
    place(scene, "o3", dy=200)
    press(game, "confirm")
    assert game.scenes.top is scene and scene.run.result is None


def test_patrol_catch_starts_ambush_and_win_removes_patrol(game, monkeypatch):
    scene = launch(game, monkeypatch)
    place(scene, "o3", dx=120)
    patrol = Patrol("o3", "o1", 0.0, mode="chase", x=scene.tug.x + 5, y=scene.tug.y)
    patrol.seen_x, patrol.seen_y = scene.tug_pos
    scene.patrols = [patrol]
    run_frames(game, 1)
    fight = game.scenes.top
    assert isinstance(fight, GameplayScene) and fight.node_id is None and fight.director.encounter.name == "AMBUSH"
    clear_current(game, fight)
    run_frames(game, 1)
    assert game.scenes.top is scene and scene.patrols == []
    assert scene.run.state.owner["o3"] == "neutral"  # an ambush claims nothing


def test_one_fight_per_frame(game, monkeypatch):  # review focus 2
    scene = launch(game, monkeypatch)
    place(scene, "o1", dx=10)
    patrol = Patrol("o1", "o3", 0.0, mode="chase", x=scene.tug.x, y=scene.tug.y)
    patrol.seen_x, patrol.seen_y = scene.tug_pos
    scene.patrols = [patrol]
    run_frames(game, 1)
    fights = [s for s in game.scenes.stack if isinstance(s, GameplayScene)]
    assert len(fights) == 1 and fights[0].node_id == "o1" and scene.patrols == [patrol]


def test_ash_death_in_flight_ends_loop(game, monkeypatch):  # review focus 1
    scene = launch(game, monkeypatch)
    scene.run.carried = 101
    scene.run.player.health = 1
    scene.tug.x, scene.tug.y = 40, 40  # deep open space, far from any lane
    run_frames(game, int(60 * 4.1))
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and scene.run.result.report.salvage_gained == 50
    assert scene.run.player.health == 0
    assert not any(isinstance(s, GameplayScene) for s in game.scenes.stack)


def test_repair_once_per_station(game, monkeypatch):
    state = game.campaign()
    state.owner["m2"] = "player"
    game.store_campaign(state)
    scene = launch(game, monkeypatch)
    scene.run.player.health = 50
    place(scene, "m2")
    run_frames(game, 1)
    assert scene.run.player.health == 50 + flight.REPAIR
    run_frames(game, 30)
    place(scene, "m2", dx=5)
    run_frames(game, 1)
    assert scene.run.player.health == 50 + flight.REPAIR


def test_tab_opens_chart_and_back_returns(game, monkeypatch):
    scene = launch(game, monkeypatch)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode=""))
    chart = game.scenes.top
    assert isinstance(chart, ChartScene) and chart.flight is scene
    game.scenes.draw(game.screen)
    press(game, "back")
    assert game.scenes.top is scene


def test_abandon_in_flight_ends_loop_as_death(game, monkeypatch):
    scene = launch(game, monkeypatch)
    scene.run.carried = 100
    press(game, "back")
    pause = game.scenes.top
    pause.abandon()
    assert isinstance(game.scenes.top, LoopEndScene) and game.campaign().salvage == 50


def test_window_close_in_flight_closes_loop(game, monkeypatch):
    launch(game, monkeypatch)
    game.close_open_loop()
    game.close_open_loop()
    assert game.campaign().turn == 1 and game.save.loop == 2


def test_flight_draws_every_state(game, monkeypatch):
    state = game.campaign()
    state.owner.update({"o1": "player", "o3": "swarm", "m3": "swarm"})
    state.hive_age["o5"] = 3
    state.fortified.add("o1")
    game.store_campaign(state)
    scene = launch(game, monkeypatch, move=(1.0, -1.0))
    scene.patrols = flight.spawn_patrols(scene.system, scene.lanes, scene.run.state, (0, 0), scene.run.rng)
    scene.run.player.health = 12
    for _ in range(3):
        run_frames(game, 20)
    place(scene, "m1", dx=60)
    run_frames(game, 2)
    assert scene.patrols


def test_headless_campaign_autopilot(game, monkeypatch):
    """Five loops through the real screens: undock, fly to a fight, win it, then dock or die."""
    from space_shooter import campaign
    from tests.test_campaign_play import die

    game.save.read_logs.append("a1_open")
    game.scenes.clear_to(HangarScene(game))
    start = dict(game.campaign().owner)
    target = {"pos": (0.0, 0.0)}

    def steer():
        scene = game.scenes.stack[0]
        if not isinstance(scene, FlightScene):
            return (0.0, 0.0)
        dx, dy = target["pos"][0] - scene.tug.x, target["pos"][1] - scene.tug.y
        dist = math.hypot(dx, dy) or 1.0
        return (dx / dist, dy / dist)

    monkeypatch.setattr(game, "move_vector", steer)
    for turn in range(5):
        select(game, "LAUNCH")
        scene = game.scenes.top
        assert isinstance(scene, FlightScene)
        state = scene.run.state
        goal = min(
            (n for n in game.system.nodes if campaign.can_engage(game.system, state, n)),
            key=lambda n: (math.dist(flight.world_pos(game.system.nodes[n]), scene.tug_pos), n),
        )
        target["pos"] = flight.world_pos(game.system.nodes[goal])
        for _ in range(60 * 30):
            top = game.scenes.top
            if isinstance(top, GameplayScene):
                if top.node_id == goal and turn % 2:
                    die(game, top)
                    break
                clear_current(game, top)
                if top.node_id == goal:
                    target["pos"] = flight.world_pos(game.system.nodes["home"])
            elif isinstance(top, LoopEndScene):
                break
            elif top is scene and math.dist(scene.tug_pos, target["pos"]) < flight.DOCK_RADIUS / 2:
                if state.owner[goal] == "player":
                    press(game, "confirm")  # docked at home
                    break
            run_frames(game, 1)
        for _ in range(20):  # the death beat plays before the card
            if isinstance(game.scenes.top, LoopEndScene):
                break
            run_frames(game, 30)
        card = game.scenes.top
        assert isinstance(card, LoopEndScene), f"turn {turn}: {card}"
        card.time = 10
        while not isinstance(game.scenes.top, HangarScene):
            press(game, "confirm")
    state = game.campaign()
    assert state.turn == 5 and state.owner != start
    assert sum(1 for o in state.owner.values() if o == "player") >= 2
