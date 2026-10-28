"""Headless integration tests that drive the real scenes."""

import random

import pygame
import pytest

from space_shooter.config import HEIGHT, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.entities.bullets import EnemyBullet
from space_shooter.entities.enemies import Drone
from space_shooter.entities.parts import Drop
from space_shooter.game import Game
from space_shooter.salvage import PATCH_HULL, Part
from space_shooter.scenes.gameover import GameOverScene
from space_shooter.scenes.gameplay import GameplayScene
from space_shooter.scenes.menu import MenuScene
from space_shooter.scenes.pause import PauseScene
from space_shooter.settings_store import Settings


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    yield g
    pygame.quit()


def run_frames(game, n, dt=1 / 60):
    for _ in range(n):
        scene = game.scenes.top
        scene.update(dt)
        game.scenes.draw(game.screen)


def test_menu_to_gameplay_and_back(game):
    game.scenes.push(MenuScene(game))
    run_frames(game, 5)
    game.scenes.top.handle_action("confirm")  # PLAY
    assert isinstance(game.scenes.top, GameplayScene)
    game.scenes.top.handle_action("pause")
    assert isinstance(game.scenes.top, PauseScene)
    run_frames(game, 3)
    game.scenes.top.handle_action("down")
    game.scenes.top.handle_action("down")
    game.scenes.top.handle_action("down")
    game.scenes.top.handle_action("confirm")  # QUIT TO MENU
    assert isinstance(game.scenes.top, MenuScene)


def test_waves_spawn_and_bullets_score(game):
    scene = GameplayScene(game, seed=42)
    game.scenes.push(scene)
    run_frames(game, 60 * 4)  # intermission + banner + some spawns
    assert scene.director.wave == 1 and len(scene.enemies) > 0
    # park an enemy right above the player and shoot it
    enemy = Drone(scene.player.x)
    enemy.y = scene.player.y - 120
    scene.enemies.add(enemy)
    scene.player.fire_cooldown = 0
    bullets = scene.player.try_fire()
    scene.player_bullets.add(bullets)
    run_frames(game, 30)
    assert scene.score > 0
    assert scene.kills >= 1


class AlwaysKnock:
    """RNG stub: every roll succeeds and choices take the first option."""

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]

    def uniform(self, a, b):
        return a

    def choices(self, population, weights=None):
        return [population[0]]


def test_collecting_drop_attaches_part(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.drops.add(Drop("turret", (scene.player.x - 30, scene.player.y), vel=(0, 0)))
    run_frames(game, 2)
    assert scene.player.loadout.count("turret") == 1 and len(scene.drops) == 0


def test_collecting_patch_heals(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.health = 50
    scene.drops.add(Drop("patch", (scene.player.x, scene.player.y), vel=(0, 0)))
    run_frames(game, 2)
    assert scene.player.health == 50 + PATCH_HULL


def test_replaced_part_is_ejected_as_drop(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    lo = scene.player.loadout
    lo.attach(Part("slug"), (-14, -30))
    lo.attach(Part("claw"), (14, -30))
    scene.drops.add(Drop("slug*", (scene.player.x, scene.player.y - 30), vel=(0, 0)))
    run_frames(game, 1)
    codes = [d.code for d in scene.drops]
    assert codes == ["slug"] and lo.slots["fore_l"].rare


def test_knocked_part_becomes_recoverable_drop(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.loadout.attach(Part("turret"), (-30, 2))
    scene.rng = AlwaysKnock()
    scene.enemy_bullets.add(EnemyBullet((scene.player.x, scene.player.y), (0, 0)))
    run_frames(game, 1)
    knocked = [d for d in scene.drops if d.code == "turret"]
    assert scene.player.loadout.count("turret") == 0 and knocked and knocked[0].lifetime == 6.0
    assert scene.player.health == PLAYER_MAX_HEALTH


def test_tractor_pulls_drops(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    drop = Drop("armour", (scene.player.x + 150, scene.player.y), vel=(0, 0))
    scene.drops.add(drop)
    start = drop.x
    run_frames(game, 10)
    assert drop.x < start or not drop.alive()


def test_game_over_flow_records_high_score(game):
    scene = GameplayScene(game, seed=3)
    game.scenes.push(scene)
    scene.score = 12345
    scene.player.take_damage(999, random.Random(0))
    run_frames(game, 60 * 4)
    assert isinstance(game.scenes.top, GameOverScene)
    over = game.scenes.top
    assert over.entering
    run_frames(game, 60)
    for _ in range(3):
        over.handle_action("confirm")
    assert not over.entering
    assert game.highscores.best == 12345
    over.handle_action("confirm")
    assert isinstance(game.scenes.top, GameplayScene)


def test_long_headless_run_is_stable(game):
    """Simulate a couple of minutes at a high difficulty with autofire on."""
    game.settings.difficulty = "hard"
    scene = GameplayScene(game, seed=7)
    game.scenes.push(scene)
    for frame in range(60 * 120):
        top = game.scenes.top
        if isinstance(top, GameplayScene):
            top.player_bullets.add(top.player.try_fire())
            if frame % 7 == 0:
                top.player.x = (top.player.x + 40) % WIDTH
        top.update(1 / 60)
        game.scenes.draw(game.screen)
    assert 0 <= scene.player.x <= WIDTH and 0 <= scene.player.y <= HEIGHT
    assert scene.director.wave >= 2


def test_step_handles_quit_event(game):
    game.scenes.push(MenuScene(game))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game.step(1 / 60)
    assert not game.running
