from __future__ import annotations

import pygame

from space_shooter.config import DIM, HEIGHT, WIDTH
from space_shooter.scenes.base import Scene
from space_shooter.ui import MenuItem, MenuList, dim_overlay, draw_text


class PauseScene(Scene):
    transparent = True

    def __init__(self, game) -> None:
        super().__init__(game)
        self.menu = MenuList(
            [
                MenuItem("RESUME", self.resume),
                MenuItem("RESTART", self.restart),
                MenuItem("SETTINGS", self.settings),
                MenuItem("QUIT TO MENU", self.to_menu),
            ],
            on_move=lambda: self.game.audio.play("menu_move"),
            on_select=lambda: self.game.audio.play("menu_select"),
        )

    def on_enter(self) -> None:
        self.game.audio.play("pause_in")
        self.game.audio.stop_all_loops()

    def resume(self) -> None:
        self.game.audio.play("pause_out")
        self.game.scenes.pop()

    def restart(self) -> None:
        from space_shooter.scenes.gameplay import GameplayScene

        self.game.scenes.clear_to(GameplayScene(self.game))

    def settings(self) -> None:
        from space_shooter.scenes.settings import SettingsScene

        self.game.scenes.push(SettingsScene(self.game))

    def to_menu(self) -> None:
        from space_shooter.scenes.menu import MenuScene

        self.game.scenes.clear_to(MenuScene(self.game))

    def handle_action(self, action: str) -> None:
        if action in ("back", "pause"):
            self.resume()
        else:
            self.menu.handle_action(action)

    def update(self, dt: float) -> None:
        self.menu.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 160)
        draw_text(surface, "PAUSED", 64, (WIDTH // 2, HEIGHT // 2 - 130))
        self.menu.draw(surface, HEIGHT // 2 - 30)
        draw_text(surface, "ESC to resume", 20, (WIDTH // 2, HEIGHT - 44), DIM)
