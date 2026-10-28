"""A radio log shown in a cracked cockpit panel with typewriter text."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import ASH, BONE, EMBER, STEEL, STEEL_DIM, VOID
from space_shooter.scenes.base import Scene
from space_shooter.story import LogEntry
from space_shooter.ui import draw_text

CHARS_PER_SECOND = 40
SPEAKER_LABELS = {
    "pilot": "TUG NINE",
    "fleet": "FLEET BEACON",
    "warden": "THE WARDEN",
    "unknown": "UNKNOWN SOURCE",
}


class LogPanel(Scene):
    transparent = True

    def __init__(self, game, entry: LogEntry, on_close: Callable[[], None] | None = None) -> None:
        super().__init__(game)
        self.entry = entry
        self.on_close = on_close
        self.full_text = "\n".join(entry.lines)
        self.progress = 0.0
        self.time = 0.0

    @property
    def shown(self) -> int:
        return min(len(self.full_text), int(self.progress))

    @property
    def done(self) -> bool:
        return self.shown >= len(self.full_text)

    def on_enter(self) -> None:
        self.game.audio.play("static")

    def handle_action(self, action: str) -> None:
        if action not in ("confirm", "fire", "back"):
            return
        if not self.done:
            self.progress = len(self.full_text)
            return
        self.game.scenes.pop()
        if self.on_close is not None:
            self.on_close()

    def update(self, dt: float) -> None:
        self.time += dt
        self.progress += CHARS_PER_SECOND * dt

    def draw(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(60, HEIGHT - 210, WIDTH - 120, 160)
        back = pygame.Surface(panel.size, pygame.SRCALPHA)
        back.fill((*VOID, 225))
        surface.blit(back, panel)
        pygame.draw.rect(surface, STEEL_DIM, panel, 2)
        # a crack across the top-right corner of the frame
        crack = [(panel.right - 90, panel.top), (panel.right - 70, panel.top + 14), (panel.right - 58, panel.top + 9)]
        pygame.draw.lines(surface, STEEL, False, crack, 1)
        speaker_colour = EMBER if self.entry.speaker == "warden" else STEEL
        draw_text(
            surface,
            SPEAKER_LABELS[self.entry.speaker],
            20,
            (panel.left + 18, panel.top + 16),
            speaker_colour,
            "midleft",
        )
        text = self.full_text[: self.shown]
        for i, line in enumerate(text.split("\n")):
            draw_text(surface, line, 26, (panel.left + 18, panel.top + 50 + i * 30), BONE, "midleft")
        if self.done and int(self.time * 2) % 2:
            draw_text(surface, "ENTER", 16, (panel.right - 14, panel.bottom - 14), ASH, "bottomright", shadow=False)
