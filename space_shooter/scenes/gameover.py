from __future__ import annotations

import string

import pygame

from space_shooter.config import CYAN, DIM, GREY, HEIGHT, RED, WHITE, WIDTH, YELLOW
from space_shooter.scenes.base import Scene
from space_shooter.scenes.highscores import draw_table
from space_shooter.ui import dim_overlay, draw_text

ALPHABET = string.ascii_uppercase + " "


class GameOverScene(Scene):
    """Shows results, takes arcade-style initials if the score charts."""

    transparent = True

    def __init__(self, game, score: int, wave: int) -> None:
        super().__init__(game)
        self.score = score
        self.wave = wave
        self.time = 0.0
        self.rank = game.highscores.rank_of(score)
        self.entering = self.rank is not None
        self.letters = [0, 0, 0]
        self.cursor = 0
        self.final_rank: int | None = None

    def on_enter(self) -> None:
        self.game.audio.stop_all_loops()
        self.game.audio.play("high_score" if self.entering else "game_over")

    # -- input ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.entering or event.type != pygame.KEYDOWN:
            return
        if event.unicode and event.unicode.upper() in ALPHABET and event.unicode != " ":
            self.letters[self.cursor] = ALPHABET.index(event.unicode.upper())
            self.cursor = min(2, self.cursor + 1)
            self.game.audio.play("menu_move")
        elif event.key == pygame.K_BACKSPACE:
            self.cursor = max(0, self.cursor - 1)
            self.letters[self.cursor] = 0

    def handle_action(self, action: str) -> None:
        if self.time < 0.6:  # ignore mashed buttons right after dying
            return
        if self.entering:
            if action == "up":
                self.letters[self.cursor] = (self.letters[self.cursor] + 1) % len(ALPHABET)
            elif action == "down":
                self.letters[self.cursor] = (self.letters[self.cursor] - 1) % len(ALPHABET)
            elif action == "left":
                self.cursor = max(0, self.cursor - 1)
            elif action == "right":
                self.cursor = min(2, self.cursor + 1)
            elif action == "confirm":  # not "fire": Z/Space are typeable letters here
                if self.cursor < 2:
                    self.cursor += 1
                else:
                    self.commit()
            else:
                return
            self.game.audio.play("menu_move")
            return
        if action in ("confirm", "fire"):
            self.game.audio.play("menu_select")
            self.restart()
        elif action == "back":
            self.to_menu()

    def commit(self) -> None:
        name = "".join(ALPHABET[i] for i in self.letters).strip() or "AAA"
        self.final_rank = self.game.highscores.add(name, self.score, self.wave, self.game.settings.difficulty)
        self.game.highscores.save()
        self.entering = False
        self.game.audio.play("menu_select")

    def restart(self) -> None:
        from space_shooter.scenes.gameplay import GameplayScene

        self.game.scenes.clear_to(GameplayScene(self.game))

    def to_menu(self) -> None:
        from space_shooter.scenes.menu import MenuScene

        self.game.scenes.clear_to(MenuScene(self.game))

    # -- drawing -------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 170)
        draw_text(surface, "GAME OVER", 64, (WIDTH // 2, 90), RED)
        draw_text(surface, f"SCORE {self.score:,}    WAVE {self.wave}", 30, (WIDTH // 2, 145), WHITE)
        if self.entering:
            draw_text(surface, f"NEW HIGH SCORE  -  RANK #{self.rank}", 30, (WIDTH // 2, 200), YELLOW)
            draw_text(surface, "ENTER YOUR INITIALS", 24, (WIDTH // 2, 240), GREY)
            for i, idx in enumerate(self.letters):
                x = WIDTH // 2 + (i - 1) * 60
                colour = CYAN if i == self.cursor else WHITE
                draw_text(surface, ALPHABET[idx], 64, (x, 300), colour)
                if i == self.cursor and int(self.time * 3) % 2:
                    pygame.draw.rect(surface, CYAN, (x - 20, 330, 40, 4))
            draw_text(surface, "UP/DOWN change   LEFT/RIGHT move   ENTER confirm", 20, (WIDTH // 2, HEIGHT - 44), DIM)
        else:
            draw_table(surface, self.game.highscores, 200, highlight_rank=self.final_rank)
            draw_text(surface, "ENTER play again    ESC menu", 22, (WIDTH // 2, HEIGHT - 44), DIM)
