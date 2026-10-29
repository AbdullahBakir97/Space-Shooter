"""Every radio log heard so far, in story order."""

from __future__ import annotations

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import ASH, BONE, STEEL, STEEL_DIM
from space_shooter.scenes.base import Scene
from space_shooter.ui import dim_overlay, draw_text

VISIBLE_ROWS = 10


class ArchiveScene(Scene):
    transparent = True

    def __init__(self, game) -> None:
        super().__init__(game)
        self.entries = game.logs.unlocked()
        self.index = 0

    def handle_action(self, action: str) -> None:
        if action == "back":
            self.game.scenes.pop()
        elif not self.entries:
            if action in ("confirm", "fire"):
                self.game.scenes.pop()
        elif action in ("up", "down"):
            step = -1 if action == "up" else 1
            self.index = (self.index + step) % len(self.entries)
            self.game.audio.play("menu_move")
        elif action in ("confirm", "fire"):
            from space_shooter.scenes.log_panel import LogPanel

            self.game.scenes.push(LogPanel(self.game, self.entries[self.index]))

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 215)
        draw_text(surface, "LOG ARCHIVE", 48, (WIDTH // 2, 80), BONE)
        if not self.entries:
            draw_text(surface, "The channel has been silent.", 26, (WIDTH // 2, HEIGHT // 2), ASH)
            return
        first = max(0, min(self.index - VISIBLE_ROWS // 2, len(self.entries) - VISIBLE_ROWS))
        for row, entry in enumerate(self.entries[first : first + VISIBLE_ROWS]):
            i = first + row
            colour = BONE if i == self.index else STEEL_DIM
            draw_text(surface, f"{i + 1:02d}", 22, (110, 150 + row * 34), STEEL, "midleft")
            draw_text(surface, entry.lines[0], 24, (160, 150 + row * 34), colour, "midleft")
        draw_text(surface, "UP / DOWN choose   ENTER replay   ESC back", 20, (WIDTH // 2, HEIGHT - 40), ASH)
