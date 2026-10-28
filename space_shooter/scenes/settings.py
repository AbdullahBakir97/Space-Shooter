from __future__ import annotations

import pygame

from space_shooter.config import DIFFICULTIES, DIFFICULTY_ORDER, DIM, HEIGHT, WIDTH
from space_shooter.scenes.base import Scene
from space_shooter.settings_store import save_settings
from space_shooter.ui import MenuItem, MenuList, draw_text


class SettingsScene(Scene):
    transparent = True

    def __init__(self, game) -> None:
        super().__init__(game)
        s = self.game.settings
        self.menu = MenuList(
            [
                MenuItem("SFX VOLUME", value=lambda: f"{int(round(s.sfx_volume * 10))}/10", adjust=self.adjust_volume),
                MenuItem(
                    "SCREEN SHAKE",
                    value=lambda: "ON" if s.screen_shake else "OFF",
                    adjust=lambda d: self.toggle("screen_shake"),
                ),
                MenuItem(
                    "FULLSCREEN",
                    value=lambda: "ON" if s.fullscreen else "OFF",
                    adjust=lambda d: self.toggle("fullscreen"),
                ),
                MenuItem(
                    "SHOW FPS", value=lambda: "ON" if s.show_fps else "OFF", adjust=lambda d: self.toggle("show_fps")
                ),
                MenuItem(
                    "REDUCED FLASHING",
                    value=lambda: "ON" if s.reduced_flashing else "OFF",
                    adjust=lambda d: self.toggle("reduced_flashing"),
                ),
                MenuItem(
                    "DIFFICULTY", value=lambda: DIFFICULTIES[s.difficulty].name.upper(), adjust=self.cycle_difficulty
                ),
                MenuItem("BACK", self.back),
            ],
            on_move=lambda: self.game.audio.play("menu_move"),
            on_select=lambda: self.game.audio.play("menu_select"),
        )

    def adjust_volume(self, direction: int) -> None:
        s = self.game.settings
        s.sfx_volume = min(1.0, max(0.0, round(s.sfx_volume + 0.1 * direction, 1)))
        self.game.audio.set_volume(s.sfx_volume)
        self.game.audio.play("shoot")

    def cycle_difficulty(self, direction: int) -> None:
        s = self.game.settings
        i = DIFFICULTY_ORDER.index(s.difficulty)
        s.difficulty = DIFFICULTY_ORDER[(i + direction) % len(DIFFICULTY_ORDER)]

    def toggle(self, field: str) -> None:
        s = self.game.settings
        setattr(s, field, not getattr(s, field))
        if field == "fullscreen":
            self.game.apply_display_mode()

    def back(self) -> None:
        save_settings(self.game.settings)
        self.game.scenes.pop()

    def handle_action(self, action: str) -> None:
        if action == "back":
            self.back()
        else:
            self.menu.handle_action(action)

    def update(self, dt: float) -> None:
        self.menu.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        from space_shooter.ui import dim_overlay

        dim_overlay(surface, 200)
        draw_text(surface, "SETTINGS", 56, (WIDTH // 2, 90))
        self.menu.draw(surface, 170, spacing=46, size=32)
        draw_text(surface, "LEFT / RIGHT to change   ESC to go back", 20, (WIDTH // 2, HEIGHT - 44), DIM)
