import pygame
import pytest

from space_shooter.game import Game
from space_shooter.save import load_save
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.hangar import HangarScene
from space_shooter.scenes.map import MapScene
from space_shooter.scenes.shipyard import ShipyardScene
from space_shooter.settings_store import Settings
from tests.helpers import press, select, silence_radio


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    silence_radio(g)
    yield g
    pygame.quit()


def open_map(game):
    game.scenes.clear_to(HangarScene(game))
    game.scenes.push(MapScene(game))
    return game.scenes.top


def key(game, k):
    game.scenes.top.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=""))


def test_map_starts_on_home_and_moves_by_direction(game):
    m = open_map(game)
    assert m.selected == "home"
    m.move("right")
    assert m.selected == "o2"
    m.move("left")
    assert m.selected == "home"
    m.move("up")
    assert m.selected in ("o1", "o2")


def test_map_builds_only_valid_routes(game):
    m = open_map(game)
    for node in ("o1", "o3"):
        m.selected = node
        m.toggle()
    assert m.route == ["o1", "o3"]
    m.selected = "m5"
    m.toggle()
    assert m.route == ["o1", "o3"]  # not adjacent: refused
    m.selected = "home"
    m.toggle()
    assert m.route == ["o1", "o3"]
    m.selected = "o1"
    m.toggle()
    assert m.route == []  # removing a stop drops everything after it


def test_map_launch_starts_route(game):
    m = open_map(game)
    m.launch()
    assert game.scenes.top is m  # nothing planned yet
    m.selected = "o1"
    m.toggle()
    key(game, pygame.K_l)
    top = game.scenes.top
    assert isinstance(top, GameplayScene) and top.route == ["o1"]


def test_map_fortify_spends_salvage(game):
    state = game.campaign()
    state.salvage = 1000
    game.store_campaign(state)
    open_map(game)
    key(game, pygame.K_f)  # home is selected
    assert "home" in game.campaign().fortified and game.campaign().salvage == 0
    assert "home" in load_save().campaign["fortified"]


def test_map_mouse_selects_node(game):
    m = open_map(game)
    x, y = game.system.nodes["m2"].pos
    m.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x + 5, y - 4), button=1))
    assert m.selected == "m2"


def test_map_draws_every_state(game):
    state = game.campaign()
    state.owner.update({"o1": "player", "o3": "swarm"})
    state.hive_age["o5"] = 3
    state.fortified.add("o1")
    game.store_campaign(state)
    m = open_map(game)
    m.selected = "o1"
    for _ in range(3):
        m.update(1 / 60)
        game.scenes.draw(game.screen)
    press(game, "back")
    assert isinstance(game.scenes.top, HangarScene)


def test_shipyard_requisitions(game):
    state = game.campaign()
    state.salvage = 1700
    game.store_campaign(state)
    game.scenes.clear_to(HangarScene(game))
    game.scenes.push(ShipyardScene(game))
    select(game, "AUTO-TURRET")
    select(game, "SALVAGE CLAW")
    select(game, "SLUG CANNON")  # two at most
    assert game.campaign().requisition == ["turret", "claw"] and game.campaign().salvage == 100
    game.scenes.draw(game.screen)


def test_hangar_launch_opens_map(game):
    game.save.read_logs.append("a1_open")
    game.scenes.clear_to(HangarScene(game))
    labels = [i.label for i in game.scenes.top.menu.items]
    assert labels == ["LAUNCH", "SHIPYARD", "LOG ARCHIVE", "RECORDS", "SETTINGS", "QUIT"]
    select(game, "LAUNCH")
    assert isinstance(game.scenes.top, MapScene)


def test_arrows_reach_every_location(game):
    m = open_map(game)
    seen, todo = {"home"}, ["home"]
    while todo:
        node = todo.pop()
        for direction in ("up", "down", "left", "right"):
            m.selected = node
            m.move(direction)
            if m.selected not in seen:
                seen.add(m.selected)
                todo.append(m.selected)
    assert seen == set(game.system.nodes)
