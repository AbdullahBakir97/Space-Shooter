"""Loop records: how far each recorded loop reached."""

from __future__ import annotations

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.encounters import ENCOUNTERS
from space_shooter.palette import ASH, BONE, STEEL, STEEL_DIM
from space_shooter.scenes.base import Scene
from space_shooter.ui import dim_overlay, draw_text

COLUMNS = (
    ("LOOP", 110, "midleft"),
    ("REACHED", 200, "midleft"),
    ("SALVAGE", 520, "midright"),
    ("TIME", 620, "midright"),
    ("", 680, "midright"),
)


class RecordsScene(Scene):
    transparent = True

    def rows(self) -> list[tuple[str, str, str, str, str]]:
        out = []
        for r in self.game.save.records:
            minutes, seconds = divmod(int(r.time), 60)
            name = ENCOUNTERS[min(r.reached, len(ENCOUNTERS) - 1)].name
            loop = str(r.loop) if r.loop else "-"
            out.append((loop, name, f"{r.salvage:,}", f"{minutes}:{seconds:02d}", r.difficulty[:1].upper()))
        return out

    def handle_action(self, action: str) -> None:
        if action in ("back", "confirm", "fire"):
            self.game.scenes.pop()

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 215)
        draw_text(surface, "RECORDS", 48, (WIDTH // 2, 80), BONE)
        rows = self.rows()
        if not rows:
            draw_text(surface, "No loop has been recorded.", 26, (WIDTH // 2, HEIGHT // 2), ASH)
            return
        for label, x, anchor in COLUMNS:
            draw_text(surface, label, 18, (x, 140), STEEL_DIM, anchor)
        for i, row in enumerate(rows):
            y = 172 + i * 30
            colour = BONE if i == 0 else STEEL
            for (_, x, anchor), value in zip(COLUMNS, row, strict=True):
                draw_text(surface, value, 24, (x, y), colour, anchor)
        draw_text(surface, "ENTER / ESC to go back", 20, (WIDTH // 2, HEIGHT - 40), ASH)
