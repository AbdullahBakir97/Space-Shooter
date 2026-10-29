"""Campaign turns played through the real gameplay scene."""

import random

import pygame
import pytest

from space_shooter.campaign import new_campaign
from space_shooter.game import Game
from space_shooter.save import load_save
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.loop_end import LoopEndScene
from space_shooter.settings_store import Settings
from tests.helpers import run_frames, silence_radio


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    silence_radio(g)
    yield g
    pygame.quit()


def launch(game, route, seed=1):
    scene = GameplayScene(game, seed=seed, route=route)
    game.scenes.clear_to(scene)
    return scene


def clear_current(game, scene):
    """Skip the fight: empty the field and let the director close the encounter."""
    d = scene.director
    while d.state == "drift":
        run_frames(game, 30)
    scene.enemies.empty()
    d.cursor = len(d.plan)
    d.state = "clearing"
    run_frames(game, 2)


def die(game, scene):
    rng = random.Random(0)
    while not scene.player.dead:
        scene.player.invuln_timer = 0
        scene.player.take_damage(999, rng)
    run_frames(game, 2)


def test_route_run_claims_cleared_nodes(game):
    scene = launch(game, ["o1", "m1"])
    assert [e.name for e in scene.director.encounters] == ["COLD WAKE FIELD", "KESS"]
    clear_current(game, scene)
    run_frames(game, 60)
    die(game, scene)
    state = game.campaign()
    assert state.owner["o1"] == "player" and state.owner["m1"] != "player" and state.turn == 1
    assert scene.result.report.claimed == ["o1"]


def test_clearing_route_ends_loop(game):
    scene = launch(game, ["o1"])
    clear_current(game, scene)
    run_frames(game, 90)
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.title == "ROUTE CLEARED"
    assert game.campaign().owner["o1"] == "player" and game.save.loop == 2


def test_death_in_first_drift_claims_nothing(game):  # review focus 2
    scene = launch(game, ["o1"])
    run_frames(game, 1)
    die(game, scene)
    state = game.campaign()
    assert scene.result.report.claimed == [] and state.turn == 1
    assert sum(1 for o in state.owner.values() if o == "swarm") > 2  # the swarm still moved


def test_requisition_fitted_once(game):  # review focus 4
    state = game.campaign()
    state.salvage = 2000
    state.requisition = ["turret", "armour"]
    game.store_campaign(state)
    scene = launch(game, ["o1"])
    lo = scene.player.loadout
    assert lo.count("turret") == 1 and lo.count("armour") == 1
    assert game.campaign().requisition == [] and load_save().campaign["requisition"] == []


def test_stale_route_is_trimmed(game):  # review focus 1
    assert launch(game, ["o1", "m5"]).route == ["o1"]
    fallback = launch(game, ["o3"]).route
    assert len(fallback) == 1 and fallback[0] in ("o1", "o2")


def test_warden_kill_wins_campaign(game):
    from space_shooter.entities.bullets import PlayerBullet

    state = game.campaign()
    for n in ("m1", "m2", "m3", "m4", "m5", "c1"):
        state.owner[n] = "player"
    game.store_campaign(state)
    scene = launch(game, ["c2"])
    run_frames(game, int(60 * 6.2))
    warden = scene.boss
    assert warden is not None
    warden.hp, warden.y = 1, warden.target_y
    warden.rect.center = (round(warden.x), round(warden.y))
    scene.player_bullets.add(PlayerBullet(warden.rect.center, (0, 0), 1))
    run_frames(game, 3)
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.title == "THE WARDEN IS SILENT"
    assert scene.result.report.status == "won" and game.save.act1_complete
    assert game.campaign().status == "active" and game.campaign().owner["c2"] == "neutral"  # fresh war next


def test_war_lost_resets_and_keeps_echoes(game):
    from tests.test_gameplay import seeded_trace

    game.save.echoes = [seeded_trace(9).to_data()]
    state = game.campaign()
    state.owner.update({n: "swarm" for n in state.owner if n != "home"})  # home is all that is left
    game.store_campaign(state)
    scene = launch(game, ["o1"])
    run_frames(game, 1)
    die(game, scene)
    assert scene.result.report.status == "lost" and "war_lost" in game.save.flags
    assert [e.loop for e in game.save.echoes][:1] == [9]
    fresh = game.campaign()
    assert fresh.status == "active" and fresh.owner == new_campaign(game.system).owner


def test_loop_end_card_lists_report(game):
    scene = launch(game, ["o1"])
    clear_current(game, scene)
    run_frames(game, 90)
    card = game.scenes.top
    lines = card.report_lines()
    assert any("COLD WAKE FIELD" in line for line in lines) and any("salvage" in line.lower() for line in lines)
    card.draw(game.screen)


def test_campaign_flags_are_set(game):
    scene = launch(game, ["o1"])
    clear_current(game, scene)
    run_frames(game, 90)
    assert "node_claimed" in game.save.flags


def test_headless_campaign_autopilot(game):
    """Five turns through the real screens: plan on the map, fly, read the card, back to the hangar."""
    from space_shooter.campaign import valid_route
    from space_shooter.scenes.hangar import HangarScene
    from space_shooter.scenes.map import MapScene
    from tests.helpers import press, select

    game.save.read_logs.append("a1_open")
    game.scenes.clear_to(HangarScene(game))
    start = dict(game.campaign().owner)
    for turn in range(5):
        select(game, "LAUNCH")
        m = game.scenes.top
        assert isinstance(m, MapScene)
        m.selected = next(n for n in sorted(game.system.nodes) if valid_route(game.system, m.state, [n]))
        m.toggle()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, unicode=""))
        scene = game.scenes.top
        assert isinstance(scene, GameplayScene)
        if turn % 2 == 0:
            clear_current(game, scene)
            run_frames(game, 90)
        else:
            run_frames(game, 200)
            die(game, scene)
        for _ in range(20):  # the death beat plays before the card
            if isinstance(game.scenes.top, LoopEndScene):
                break
            run_frames(game, 30)
        assert isinstance(game.scenes.top, LoopEndScene)
        while not isinstance(game.scenes.top, HangarScene):
            press(game, "confirm")
            run_frames(game, 2)
    state = game.campaign()
    assert state.turn == 5 and state.owner != start
    assert sum(1 for o in state.owner.values() if o == "player") >= 2
