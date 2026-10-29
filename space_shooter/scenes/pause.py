from __future__ import annotations

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import STEEL_DIM
from space_shooter.scenes.base import Scene
from space_shooter.ui import MenuItem, MenuList, dim_overlay, draw_text


class PauseScene(Scene):
    transparent = True

    def __init__(self, game) -> None:
        super().__init__(game)
        self.menu = MenuList(
            [
                MenuItem("RESUME", self.resume),
                MenuItem("SETTINGS", self.settings),
                MenuItem("ABANDON LOOP", self.abandon),
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

    def settings(self) -> None:
        from space_shooter.scenes.settings import SettingsScene

        self.game.scenes.push(SettingsScene(self.game))

    def abandon(self) -> None:
        """Give up this loop: it closes exactly like a death."""
        from space_shooter.scenes.gameplay import GameplayScene
        from space_shooter.scenes.loop_end import LoopEndScene

        self.game.scenes.pop()
        gameplay = self.game.scenes.top
        if isinstance(gameplay, GameplayScene):
            self.game.scenes.push(LoopEndScene(self.game, gameplay.end_loop(victory=False)))

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
        draw_text(surface, "ESC to resume", 20, (WIDTH // 2, HEIGHT - 44), STEEL_DIM)
