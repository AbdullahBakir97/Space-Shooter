from __future__ import annotations

import pygame

from space_shooter.config import CYAN, DIM, GREY, HEIGHT, WHITE, WIDTH, YELLOW
from space_shooter.scenes.base import Scene
from space_shooter.ui import dim_overlay, draw_text


def draw_table(surface: pygame.Surface, table, top: int, highlight_rank: int | None = None) -> None:
    if not table.entries:
        draw_text(surface, "NO SCORES YET - GO MAKE SOME", 28, (WIDTH // 2, top + 40), GREY)
        return
    cx = WIDTH // 2
    draw_text(surface, "RANK", 20, (cx - 210, top), DIM, "midleft")
    draw_text(surface, "NAME", 20, (cx - 120, top), DIM, "midleft")
    draw_text(surface, "WAVE", 20, (cx + 10, top), DIM, "midleft")
    draw_text(surface, "SCORE", 20, (cx + 210, top), DIM, "midright")
    for i, e in enumerate(table.entries):
        y = top + 32 + i * 30
        colour = YELLOW if highlight_rank == i + 1 else (WHITE if i == 0 else GREY)
        draw_text(surface, f"{i + 1:>2}.", 26, (cx - 210, y), colour, "midleft")
        draw_text(surface, e.name, 26, (cx - 120, y), colour, "midleft")
        draw_text(surface, f"{e.wave}", 26, (cx + 10, y), colour, "midleft")
        draw_text(surface, f"{e.score:,}", 26, (cx + 210, y), colour, "midright")
        draw_text(surface, e.difficulty[:1].upper(), 18, (cx + 100, y), CYAN, "midleft")


class HighScoresScene(Scene):
    transparent = True

    def handle_action(self, action: str) -> None:
        if action in ("back", "confirm", "fire"):
            self.game.audio.play("menu_select")
            self.game.scenes.pop()

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 200)
        draw_text(surface, "HIGH SCORES", 56, (WIDTH // 2, 100))
        draw_table(surface, self.game.highscores, 170)
        draw_text(surface, "ENTER / ESC to go back", 20, (WIDTH // 2, HEIGHT - 44), DIM)
