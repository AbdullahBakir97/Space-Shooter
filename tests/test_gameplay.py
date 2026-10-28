"""Headless integration tests that drive the real scenes."""

import pygame
import pytest

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.entities.enemies import Drone
from space_shooter.game import Game
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
    scene.player.invuln_timer = 0
    bullets = scene.player.try_fire()
    scene.player_bullets.add(bullets)
    run_frames(game, 30)
    assert scene.score > 0
    assert scene.kills >= 1


def test_bomb_clears_regular_enemies(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    for x in (100, 300, 500):
        d = Drone(float(x))
        d.y = 200
        scene.enemies.add(d)
    bombs = scene.player.bombs
    scene.use_bomb()
    assert scene.player.bombs == bombs - 1
    assert len(scene.enemies) == 0 and scene.kills == 3


def test_game_over_flow_records_high_score(game):
    scene = GameplayScene(game, seed=3)
    game.scenes.push(scene)
    scene.score = 12345
    scene.player.lives = 1
    scene.player.invuln_timer = 0
    scene.player.take_damage(999)
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
            top.player.invuln_timer = 0
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
