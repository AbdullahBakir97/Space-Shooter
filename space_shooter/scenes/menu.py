from __future__ import annotations

import math

import pygame

from space_shooter import __version__, assets
from space_shooter.config import CYAN, DIFFICULTIES, DIFFICULTY_ORDER, DIM, GREY, HEIGHT, WIDTH
from space_shooter.scenes.base import Scene
from space_shooter.settings_store import save_settings
from space_shooter.ui import MenuItem, MenuList, draw_text


class MenuScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.time = 0.0
        self.title = assets.load_image("title", 8)
        self.menu = MenuList(
            [
                MenuItem("PLAY", self.start),
                MenuItem("DIFFICULTY", value=self.difficulty_name, adjust=self.cycle_difficulty),
                MenuItem("HIGH SCORES", self.show_scores),
                MenuItem("SETTINGS", self.show_settings),
                MenuItem("QUIT", self.game.quit),
            ],
            on_move=lambda: self.game.audio.play("menu_move"),
            on_select=lambda: self.game.audio.play("menu_select"),
        )

    # -- menu callbacks ------------------------------------------------------
    def start(self) -> None:
        from space_shooter.scenes.gameplay import GameplayScene

        self.game.scenes.replace(GameplayScene(self.game))

    def difficulty_name(self) -> str:
        return DIFFICULTIES[self.game.settings.difficulty].name

    def cycle_difficulty(self, direction: int) -> None:
        order = DIFFICULTY_ORDER
        i = order.index(self.game.settings.difficulty)
        self.game.settings.difficulty = order[(i + direction) % len(order)]
        save_settings(self.game.settings)

    def show_scores(self) -> None:
        from space_shooter.scenes.highscores import HighScoresScene

        self.game.scenes.push(HighScoresScene(self.game))

    def show_settings(self) -> None:
        from space_shooter.scenes.settings import SettingsScene

        self.game.scenes.push(SettingsScene(self.game))

    # -- scene protocol ------------------------------------------------------
    def handle_action(self, action: str) -> None:
        if action == "back":
            self.game.quit()
        elif action == "fire" and self.menu.index == 0:
            self.menu.handle_action("confirm")
        else:
            self.menu.handle_action(action)

    def update(self, dt: float) -> None:
        self.time += dt
        self.menu.update(dt)
        self.game.starfield.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        self.game.starfield.draw(surface)
        bob = int(6 * math.sin(self.time * 2))
        rect = self.title.get_rect(center=(WIDTH // 2, 150 + bob))
        glow = assets.silhouette("title", CYAN, 8)
        glow.set_alpha(70 + int(40 * math.sin(self.time * 3)))
        surface.blit(glow, rect.move(0, 4))
        surface.blit(self.title, rect)
        self.menu.draw(surface, HEIGHT // 2 - 20)
        best = self.game.highscores.best
        if best:
            draw_text(surface, f"BEST  {best:,}", 22, (WIDTH // 2, HEIGHT // 2 - 70), GREY)
        draw_text(surface, "ARROWS / WASD move   SPACE fire   X bomb   ESC pause", 20, (WIDTH // 2, HEIGHT - 44), DIM)
        draw_text(surface, f"v{__version__}", 16, (WIDTH - 8, HEIGHT - 6), DIM, "bottomright", shadow=False)
