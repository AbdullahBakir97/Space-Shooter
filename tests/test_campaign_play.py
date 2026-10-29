"""War loops played through the real combat scene, one fight at a time."""

import random

import pygame
import pytest

from space_shooter import campaign
from space_shooter.campaign import new_campaign
from space_shooter.game import Game
from space_shooter.save import load_save
from space_shooter.scenes.base import Scene
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.loop_end import LoopEndScene
from space_shooter.scenes.run import CampaignRun
from space_shooter.settings_store import Settings
from tests.helpers import press, run_frames, silence_radio


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    silence_radio(g)
    yield g
    pygame.quit()


class Holder(Scene):
    """Stands in for the flight scene underneath a fight."""

    def __init__(self, game, run) -> None:
        super().__init__(game)
        self.run = run


def start(game, seed=1):
    run = CampaignRun(game, seed=seed)
    game.scenes.clear_to(Holder(game, run))
    return run


def fight(game, run, node_id):
    enc = campaign.encounter_for(game.system, run.state, node_id)
    scene = GameplayScene(game, seed=1, run=run, node_id=node_id, encounter=enc)
    game.scenes.push(scene)
    return scene


def clear_current(game, scene):
    """Skip the fight: empty the field and let the director close the encounter."""
    d = scene.director
    while d.state == "drift":
        run_frames(game, 30)
    run_frames(game, 2)
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


def test_fight_win_claims_and_returns(game):
    run = start(game)
    scene = fight(game, run, "o1")
    assert scene.director.encounter.name == "COLD WAKE FIELD"
    run.player.health = 70
    scene.score = 120
    clear_current(game, scene)
    assert isinstance(game.scenes.top, Holder)
    assert run.player.health == 70 and run.carried == 120 and run.reached == 0
    assert game.campaign().owner["o1"] == "player" and load_save().campaign["owner"]["o1"] == "player"
    assert run.result is None and game.campaign().turn == 0  # the loop goes on


def test_fight_death_banks_half_keeps_claims(game):
    run = start(game)
    scene = fight(game, run, "o1")
    scene.score = 120
    clear_current(game, scene)
    scene = fight(game, run, "o3")
    scene.score = 80
    run_frames(game, 120)
    die(game, scene)
    run_frames(game, 120)
    assert isinstance(game.scenes.top, LoopEndScene)
    state = game.campaign()
    assert state.owner["o1"] == "player" and state.turn == 1
    assert run.result.report.claimed == ["o1"] and run.result.report.salvage_gained == 100 + 100
    assert run.result.salvage == 200 and game.save.loop == 2


def test_requisition_fitted_once(game):
    state = game.campaign()
    state.salvage = 2000
    state.requisition = ["turret", "armour"]
    game.store_campaign(state)
    run = start(game)
    lo = run.player.loadout
    assert lo.count("turret") == 1 and lo.count("armour") == 1
    assert game.campaign().requisition == [] and load_save().campaign["requisition"] == []


def test_repeat_type_not_recorded_twice(game):  # review focus 3
    run = start(game)
    scene = fight(game, run, "o1")
    clear_current(game, scene)
    recorded = len(run.recorder.samples)
    assert recorded > 0 and {s[0] for s in run.recorder.samples} == {0}
    scene = fight(game, run, "o2")  # another Cold Wake fight
    clear_current(game, scene)
    assert len(run.recorder.samples) == recorded and not scene.recording


def test_echoes_fly_by_encounter_type(game):
    from tests.test_gameplay import seeded_trace

    game.save.echoes = [seeded_trace(5).to_data()]
    run = start(game)
    scene = fight(game, run, "o1")
    assert scene.echo_key == 0
    scene = GameplayScene(game, run=run, node_id="m1", encounter=campaign.encounter_for(game.system, run.state, "m1"))
    assert scene.echo_key == 2  # KESS plays as the Graveyard


def test_window_close_mid_fight_closes_once(game):  # review focus 4
    run = start(game)
    fight(game, run, "o1")
    run_frames(game, 120)
    game.close_open_loop()
    game.close_open_loop()
    assert game.campaign().turn == 1 and game.save.loop == 2 and len(game.save.records) == 1


def test_warden_kill_wins_without_docking(game):  # review focus 5
    from space_shooter.entities.bullets import PlayerBullet

    state = game.campaign()
    for n in ("m1", "m2", "m3", "m4", "m5", "c1"):
        state.owner[n] = "player"
    game.store_campaign(state)
    run = start(game)
    scene = fight(game, run, "c2")
    run_frames(game, int(60 * 1.8))
    warden = scene.boss
    assert warden is not None
    warden.hp, warden.y = 1, warden.target_y
    warden.rect.center = (round(warden.x), round(warden.y))
    scene.player_bullets.add(PlayerBullet(warden.rect.center, (0, 0), 1))
    run_frames(game, 3)
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.title == "THE WARDEN IS SILENT"
    assert run.result.report.status == "won" and game.save.act1_complete
    assert run.finish(died=True) is run.result and game.save.loop == 2
    assert game.campaign().status == "active" and game.campaign().owner["c2"] == "neutral"  # fresh war next


def test_war_lost_resets_and_keeps_echoes(game):
    from tests.test_gameplay import seeded_trace

    game.save.echoes = [seeded_trace(9).to_data()]
    state = game.campaign()
    state.owner.update({n: "swarm" for n in state.owner if n != "home"})  # home is all that is left
    game.store_campaign(state)
    run = start(game)
    scene = fight(game, run, "o1")
    run_frames(game, 1)
    die(game, scene)
    assert run.result.report.status == "lost" and "war_lost" in game.save.flags
    assert [e.loop for e in game.save.echoes][:1] == [9]
    fresh = game.campaign()
    assert fresh.status == "active" and fresh.owner == new_campaign(game.system).owner


def test_dock_card_lists_report(game):
    run = start(game)
    scene = fight(game, run, "o1")
    clear_current(game, scene)
    result = run.finish(died=False)
    assert result.docked and "node_claimed" in game.save.flags
    card = LoopEndScene(game, result)
    game.scenes.push(card)
    assert card.title == "DOCKED"
    lines = card.report_lines()
    assert any("COLD WAKE FIELD" in line for line in lines) and any("salvage" in line.lower() for line in lines)
    card.draw(game.screen)


def test_loop_end_plays_due_log(game):
    from space_shooter.scenes.hangar import HangarScene
    from space_shooter.scenes.log_panel import LogPanel
    from space_shooter.story import LogDirector, load_logs

    logs = load_logs()
    game.save.read_logs[:] = [log.id for log in logs if log.id != "m_first_claim"]
    game.logs = LogDirector(logs, game.save.read_logs)
    run = start(game)
    scene = fight(game, run, "o1")
    clear_current(game, scene)
    card = LoopEndScene(game, run.finish(died=False))
    game.scenes.push(card)
    card.time = 10
    press(game, "confirm")
    top = game.scenes.top
    assert isinstance(top, LogPanel) and top.entry.id == "m_first_claim"
    assert isinstance(game.scenes.stack[0], HangarScene)


def test_ambush_reaches_nowhere(game):
    from space_shooter.encounters import AMBUSH

    run = start(game)
    scene = GameplayScene(game, seed=1, run=run, node_id=None, encounter=AMBUSH)
    game.scenes.push(scene)
    clear_current(game, scene)
    assert run.reached == -1 and run.state.owner == new_campaign(game.system).owner


def test_loop_without_fights_leaves_no_echo(game):
    from tests.test_gameplay import seeded_trace

    game.save.echoes = [seeded_trace(n).to_data() for n in range(1, 13)]
    run = start(game)
    run.time = 40.0
    run.finish(died=False)
    assert sorted(e.loop for e in game.save.echoes) == list(range(1, 13))


def test_window_close_mid_fight_keeps_fight_salvage(game):
    run = start(game)
    scene = fight(game, run, "o1")
    run_frames(game, 120)
    scene.score = 500
    game.close_open_loop()
    assert run.result.salvage == 500 and game.campaign().salvage == 250


def test_echo_loadout_follows_its_own_segment():
    from space_shooter.echoes import EchoPlayback, EchoTrace

    trace = EchoTrace(
        1,
        0,
        30.0,
        [(6, 0.0, 1.0, 1.0, False), (6, 2.0, 1.0, 1.0, False), (0, 0.0, 1.0, 1.0, False), (0, 9.0, 1.0, 1.0, False)],
        [(6, 0.0, {}), (0, 0.0, {}), (0, 5.0, {"nose": "turret"})],
    )
    playback = EchoPlayback(trace)
    assert playback.advance(6, 1.0).loadout == {}
    assert playback.advance(0, 6.0).loadout == {"nose": "turret"}
