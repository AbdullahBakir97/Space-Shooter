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
    report: object | None = None  # campaign.TurnReport when the loop was a campaign turn
    docked: bool = False  # the tug flew home and docked
    reached_name: str | None = None


class LoopEndScene(Scene):
    transparent = True

    def __init__(self, game, result: RunResult) -> None:
        super().__init__(game)
        self.result = result
        self.time = 0.0

    @property
    def title(self) -> str:
        r = self.result
        if r.victory:
            return "THE WARDEN IS SILENT"
        if r.report is not None and r.report.status == "lost":
            return "THE WAR IS LOST"
        if r.docked:
            return "DOCKED"
        return f"LOOP {r.loop}"

    def report_lines(self) -> list[str]:
        """What this turn changed on the map, in plain words."""
        report = self.result.report
        if report is None:
            return []
        names = self.game.system.nodes

        def listed(ids: list[str]) -> str:
            return ", ".join(names[n].name for n in ids)

        lines = []
        if report.claimed:
            lines.append(f"Taken: {listed(report.claimed)}")
        if report.lost:
            lines.append(f"Lost to the swarm: {listed(report.lost)}")
        if report.fortify_spent:
            lines.append(f"Fortifications held at {listed(report.fortify_spent)}")
        if report.hives:
            lines.append(f"Hives formed at {listed(report.hives)}")
        if report.home_threatened and report.status == "active":
            lines.append("The swarm is at the station's door.")
        lines.append(f"+{report.salvage_gained:,} salvage")
        return lines

    @property
    def closing_line(self) -> str:
        if self.result.victory:
            return "For the first time, the clock keeps moving."
        return CLOSING_LINES[min(self.result.reached, len(CLOSING_LINES) - 1)]

    def handle_action(self, action: str) -> None:
        if self.time < INPUT_DELAY or action not in ("confirm", "fire", "back"):
            return
        from space_shooter.scenes.hangar import HangarScene
        from space_shooter.scenes.log_panel import LogPanel
        from space_shooter.story import state_from_save

        self.game.audio.play("menu_select")
        entry = self.game.logs.next_log(state_from_save(self.game.save))  # what this loop changed, heard now
        self.game.scenes.clear_to(HangarScene(self.game))
        if entry is not None and self.game.scenes.top is not None and not isinstance(self.game.scenes.top, LogPanel):
            self.game.logs.mark_read(entry.id)
            self.game.persist()
            self.game.scenes.push(LogPanel(self.game, entry))

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 200)
        cx = WIDTH // 2
        lost = self.title == "THE WAR IS LOST"
        draw_text(surface, self.title, 64, (cx, 150), EMBER if self.result.victory or lost else BONE)
        r = self.result
        reached = r.reached_name or ENCOUNTERS[min(r.reached, len(ENCOUNTERS) - 1)].name
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
        lines = self.report_lines()
        for i, line in enumerate(lines):
            draw_text(surface, line, 22, (cx, 384 + i * 26), EMBER if line.startswith("Lost") else STEEL)
        draw_text(surface, self.closing_line, 26, (cx, 400 + len(lines) * 26), BONE)
        if self.time >= INPUT_DELAY:
            draw_text(surface, "ENTER to return to the hangar", 20, (cx, HEIGHT - 44), ASH)
