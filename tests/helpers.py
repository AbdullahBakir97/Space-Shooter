"""Shared helpers for driving scenes headlessly."""

from __future__ import annotations

from space_shooter.encounters import DRIFT_TIME
from space_shooter.story import LogDirector


def run_frames(game, n: int, dt: float = 1 / 60) -> None:
    for _ in range(n):
        game.scenes.top.update(dt)
        game.scenes.draw(game.screen)


def press(game, action: str) -> None:
    game.scenes.top.handle_action(action)


def select(game, label: str) -> None:
    """Pick a menu item by label on the top scene and confirm it."""
    menu = game.scenes.top.menu
    menu.index = [item.label for item in menu.items].index(label)
    press(game, "confirm")


def silence_radio(game) -> None:
    game.logs = LogDirector([], game.save.read_logs)


def start_run(game, encounter: int = 0, seed: int = 1, keep_logs: bool = False):
    """Start a gameplay scene at ``encounter`` and run through its drift."""
    from space_shooter.scenes.gameplay import GameplayScene

    if not keep_logs:
        silence_radio(game)
    scene = GameplayScene(game, seed=seed)
    scene.director.index = encounter
    game.scenes.clear_to(scene)
    run_frames(game, int(60 * DRIFT_TIME) + 2)
    return scene
