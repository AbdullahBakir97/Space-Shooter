"""The hub between loops."""

from __future__ import annotations

import math

import pygame

from space_shooter import __version__
from space_shooter.config import HEIGHT, WIDTH
from space_shooter.echoes import EchoTrace, select_roster
from space_shooter.palette import ASH, BONE, EMBER, STEEL, STEEL_DIM
from space_shooter.scenes.base import Scene
from space_shooter.ui import MenuItem, MenuList, draw_text


class HangarScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.time = 0.0
        self.notice: str | None = None
        self.menu = MenuList(
            [
                MenuItem("LAUNCH", self.launch),
                MenuItem("LOG ARCHIVE", self.show_archive),
                MenuItem("RECORDS", self.show_records),
                MenuItem("SETTINGS", self.show_settings),
                MenuItem("QUIT", self.game.quit),
            ],
            on_move=lambda: self.game.audio.play("menu_move"),
            on_select=lambda: self.game.audio.play("menu_select"),
        )

    def on_enter(self) -> None:
        self.game.audio.set_bed_level(0.12)
        if self.game.save.read_logs:
            return
        opening = self.game.logs.get("a1_open")
        if opening is None:
            return
        from space_shooter.scenes.log_panel import LogPanel

        self.game.logs.mark_read(opening.id)
        self.game.persist()
        self.game.scenes.push(LogPanel(self.game, opening, on_close=self.launch))

    # -- menu ----------------------------------------------------------------
    def launch(self) -> None:
        from space_shooter.scenes.gameplay import GameplayScene

        self.game.scenes.clear_to(GameplayScene(self.game))

    def show_archive(self) -> None:
        from space_shooter.scenes.archive import ArchiveScene

        self.game.scenes.push(ArchiveScene(self.game))

    def show_records(self) -> None:
        from space_shooter.scenes.records import RecordsScene

        self.game.scenes.push(RecordsScene(self.game))

    def show_settings(self) -> None:
        from space_shooter.scenes.settings import SettingsScene

        self.game.scenes.push(SettingsScene(self.game))

    def roster_names(self) -> list[str]:
        traces = [EchoTrace.from_data(d) for d in self.game.save.echoes]
        return [f"ECHO {t.loop}" for t in select_roster(traces)]

    # -- scene protocol ------------------------------------------------------
    def handle_action(self, action: str) -> None:
        if action == "back":
            self.game.quit()
        else:
            self.menu.handle_action(action)

    def update(self, dt: float) -> None:
        self.time += dt
        self.menu.update(dt)
        self.game.starfield.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self.game.save.notice:
            self.notice, self.game.save.notice = self.game.save.notice, None
        self.game.starfield.draw(surface)
        cx = WIDTH // 2
        bob = int(3 * math.sin(self.time))
        draw_text(surface, "LOOP OF ASH", 84, (cx, 140 + bob), BONE)
        draw_text(surface, "ACT ONE  -  THE WARDEN", 22, (cx, 192 + bob), EMBER)
        draw_text(surface, f"LOOP {self.game.save.loop}", 26, (24, 24), BONE, "topleft")
        names = self.roster_names()
        draw_text(surface, "ECHOES", 18, (WIDTH - 24, 24), ASH, "topright")
        for i, name in enumerate(names or ["none yet"]):
            draw_text(surface, name, 20, (WIDTH - 24, 48 + i * 22), STEEL if names else STEEL_DIM, "topright")
        self.menu.draw(surface, HEIGHT // 2 + 10, spacing=44, size=36)
        if self.game.save.read_logs:
            last = self.game.logs.get(self.game.save.read_logs[-1])
            if last is not None:
                draw_text(surface, last.lines[0], 22, (cx, HEIGHT - 70), ASH)
        if self.notice:
            draw_text(surface, self.notice, 20, (cx, HEIGHT - 40), EMBER)
        draw_text(surface, f"v{__version__}", 16, (WIDTH - 8, HEIGHT - 6), STEEL_DIM, "bottomright", shadow=False)
