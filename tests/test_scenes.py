"""Hangar, loop-end card, archive, records and the loop lifecycle."""

import random

import pygame
import pytest

from space_shooter.game import Game
from space_shooter.save import load_save
from space_shooter.scenes.archive import ArchiveScene
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.hangar import HangarScene
from space_shooter.scenes.log_panel import LogPanel
from space_shooter.scenes.loop_end import LoopEndScene, RunResult
from space_shooter.scenes.pause import PauseScene
from space_shooter.scenes.records import RecordsScene
from space_shooter.scenes.settings import SettingsScene
from space_shooter.settings_store import Settings, load_settings
from tests.helpers import press, run_frames, select, silence_radio, start_run


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    yield g
    pygame.quit()


def test_first_launch_shows_opening_log_then_launches(game):
    game.scenes.push(HangarScene(game))
    assert isinstance(game.scenes.top, LogPanel) and game.scenes.top.entry.id == "a1_open"
    press(game, "confirm")
    press(game, "confirm")
    assert isinstance(game.scenes.top, GameplayScene)


def test_returning_player_sees_hangar_menu(game):
    game.save.read_logs.append("a1_open")
    game.scenes.push(HangarScene(game))
    assert isinstance(game.scenes.top, HangarScene)
    assert [i.label for i in game.scenes.top.menu.items] == ["LAUNCH", "LOG ARCHIVE", "RECORDS", "SETTINGS", "QUIT"]
    select(game, "LAUNCH")
    assert isinstance(game.scenes.top, GameplayScene)


def test_death_shows_card_then_hangar_with_next_loop(game):
    scene = start_run(game)
    scene.player.take_damage(999, random.Random(0))
    run_frames(game, 30)
    assert not isinstance(game.scenes.top, LoopEndScene)  # slow-motion beat first
    run_frames(game, 90)
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.result.loop == 1 and not card.result.victory
    press(game, "confirm")
    assert game.scenes.top is card  # ignores input for the first 0.8 s
    run_frames(game, 60)
    press(game, "confirm")
    assert isinstance(game.scenes.top, HangarScene) and game.save.loop == 2


def test_death_adds_record(game):
    scene = start_run(game, encounter=2)
    scene.score = 1234
    scene.player.take_damage(999, random.Random(0))
    run_frames(game, 2)
    rec = game.save.records[0]
    assert (rec.loop, rec.reached, rec.salvage) == (1, 2, 1234)


def test_abandon_counts_as_loop_end(game):
    scene = start_run(game)
    run_frames(game, 60 * 6)
    scene.handle_action("pause")
    assert isinstance(game.scenes.top, PauseScene)
    assert [i.label for i in game.scenes.top.menu.items] == ["RESUME", "SETTINGS", "ABANDON LOOP"]
    select(game, "ABANDON LOOP")
    assert isinstance(game.scenes.top, LoopEndScene)
    assert game.save.loop == 2 and len(game.save.records) == 1


def test_quit_mid_run_saves_loop(game):  # Review Focus 1
    start_run(game)
    run_frames(game, 60 * 6)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game.step(1 / 60)
    assert not game.running
    saved = load_save()
    assert saved.loop == 2 and saved.echoes


def test_quit_from_hangar_does_not_advance_loop(game):
    silence_radio(game)
    game.scenes.push(HangarScene(game))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game.step(1 / 60)
    assert load_save().loop == 1


def test_hangar_shows_notice_once(game):
    game.save.read_logs.append("a1_open")
    game.save.notice = "Progress could not be saved."
    h = HangarScene(game)
    game.scenes.push(h)
    h.draw(game.screen)
    assert game.save.notice is None and h.notice == "Progress could not be saved."


def test_hangar_lists_echo_roster(game):
    from tests.test_gameplay import seeded_trace

    game.save.read_logs.append("a1_open")
    game.save.echoes = [seeded_trace(n, reached=n % 3).to_data() for n in range(1, 8)]
    h = HangarScene(game)
    game.scenes.push(h)
    assert h.roster_names() == ["ECHO 5", "ECHO 2", "ECHO 7", "ECHO 4", "ECHO 1"]
    h.draw(game.screen)


def test_archive_lists_read_logs(game):
    game.logs.mark_read("a1_open")
    game.scenes.push(ArchiveScene(game))
    archive = game.scenes.top
    assert [e.id for e in archive.entries] == ["a1_open"]
    press(game, "confirm")
    assert isinstance(game.scenes.top, LogPanel)


def test_records_scene_draws(game):
    from space_shooter.save import Record

    game.save.records.append(Record(3, 4, 900, 125.0, "hard"))
    game.scenes.push(RecordsScene(game))
    game.scenes.draw(game.screen)
    assert game.scenes.top.rows() == [("3", "LAST LIGHT", "900", "2:05", "H")]


def test_settings_reduced_flashing_and_difficulty(game):
    game.scenes.push(SettingsScene(game))
    labels = [i.label for i in game.scenes.top.menu.items]
    assert "REDUCED FLASHING" in labels and "DIFFICULTY" in labels
    select(game, "REDUCED FLASHING")
    select(game, "DIFFICULTY")
    select(game, "BACK")
    saved = load_settings()
    assert saved.reduced_flashing is True and saved.difficulty == "hard"


def test_loop_end_card_victory_text(game):
    result = RunResult(loop=9, reached=5, salvage=7000, time=600.0, echoes_lost=[3], victory=True)
    card = LoopEndScene(game, result)
    game.scenes.push(card)
    game.scenes.draw(game.screen)
    assert card.title == "THE WARDEN IS SILENT"
    assert LoopEndScene(game, RunResult(2, 1, 0, 30.0, [], False)).title == "LOOP 2"


def test_warden_victory_completes_act(game):
    from space_shooter.encounters import WARDEN_INDEX
    from space_shooter.entities.bullets import PlayerBullet

    for log in game.logs.logs:
        if not log.id.startswith("a1_end"):
            game.logs.mark_read(log.id)
    scene = start_run(game, encounter=WARDEN_INDEX, keep_logs=True)
    warden = scene.boss
    assert warden is not None and warden.kind == "warden" and "warden_seen" in game.save.flags
    warden.hp = 1
    warden.y = warden.target_y  # skip its entrance so the shot lands on screen
    warden.rect.center = (round(warden.x), round(warden.y))
    scene.player_bullets.add(PlayerBullet(warden.rect.center, (0, 0), 1))
    run_frames(game, 1)
    for log_id in ("a1_end_1", "a1_end_2", "a1_end_3"):
        assert isinstance(game.scenes.top, LogPanel) and game.scenes.top.entry.id == log_id
        press(game, "confirm")
        press(game, "confirm")
    card = game.scenes.top
    assert isinstance(card, LoopEndScene) and card.result.victory
    assert game.save.act1_complete and "act1_complete" in game.save.flags
    assert load_save().act1_complete and load_save().loop == 2


@pytest.mark.parametrize("reached,word", [(0, "ash"), (1, "shelf"), (2, "graveyard"), (3, "picket"), (4, "star")])
def test_closing_line_matches_where_the_loop_ended(game, reached, word):
    assert word in LoopEndScene(game, RunResult(1, reached, 0, 1.0)).closing_line.lower()


def test_hangar_decodes_echoes_once(game, monkeypatch):
    from space_shooter import echoes
    from tests.test_gameplay import seeded_trace

    game.save.read_logs.append("a1_open")
    game.save.echoes = [seeded_trace(n).to_data() for n in range(1, 6)]
    calls = []
    original = echoes.EchoTrace.from_data
    monkeypatch.setattr(echoes.EchoTrace, "from_data", classmethod(lambda cls, d: calls.append(1) or original(d)))
    h = HangarScene(game)
    game.scenes.push(h)
    for _ in range(10):
        h.draw(game.screen)
    assert len(calls) <= 5
