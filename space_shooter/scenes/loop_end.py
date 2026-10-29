"""The card shown when a loop closes, by death, abandonment or victory."""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.encounters import ENCOUNTERS
from space_shooter.palette import ASH, BONE, EMBER, STEEL
from space_shooter.scenes.base import Scene
from space_shooter.ui import dim_overlay, draw_text

INPUT_DELAY = 0.8
CLOSING_LINES = (  # indexed by the encounter where the loop ended
    "The ash closes over the wreck.",
    "The shelf remembers you.",
    "The graveyard has room for one more.",
    "The picket line holds. You don't.",
    "The star breathes out. You don't breathe in.",
    "Somewhere, the clock winds back.",
)


@dataclass
class RunResult:
    loop: int
    reached: int
    salvage: int
    time: float
    echoes_lost: list[int] = field(default_factory=list)
    victory: bool = False


class LoopEndScene(Scene):
    transparent = True

    def __init__(self, game, result: RunResult) -> None:
        super().__init__(game)
        self.result = result
        self.time = 0.0

    @property
    def title(self) -> str:
        return "THE WARDEN IS SILENT" if self.result.victory else f"LOOP {self.result.loop}"

    @property
    def closing_line(self) -> str:
        if self.result.victory:
            return "For the first time, the clock keeps moving."
        return CLOSING_LINES[min(self.result.reached, len(CLOSING_LINES) - 1)]

    def handle_action(self, action: str) -> None:
        if self.time < INPUT_DELAY or action not in ("confirm", "fire", "back"):
            return
        from space_shooter.scenes.hangar import HangarScene

        self.game.audio.play("menu_select")
        self.game.scenes.clear_to(HangarScene(self.game))

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 200)
        cx = WIDTH // 2
        draw_text(surface, self.title, 64, (cx, 150), EMBER if self.result.victory else BONE)
        r = self.result
        reached = ENCOUNTERS[min(r.reached, len(ENCOUNTERS) - 1)].name
        minutes, seconds = divmod(int(r.time), 60)
        rows = [
            ("REACHED", reached),
            ("SALVAGE", f"{r.salvage:,}"),
            ("TIME", f"{minutes}:{seconds:02d}"),
            ("ECHOES LOST", ", ".join(f"ECHO {n}" for n in r.echoes_lost) or "none"),
        ]
        for i, (label, value) in enumerate(rows):
            y = 240 + i * 34
            draw_text(surface, label, 24, (cx - 20, y), ASH, "midright")
            draw_text(surface, value, 26, (cx + 20, y), STEEL, "midleft")
        draw_text(surface, self.closing_line, 26, (cx, 420), BONE)
        if self.time >= INPUT_DELAY:
            draw_text(surface, "ENTER to return to the hangar", 20, (cx, HEIGHT - 44), ASH)
