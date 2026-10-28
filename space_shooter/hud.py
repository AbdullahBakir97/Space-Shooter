"""In-game overlay."""

from __future__ import annotations

import pygame

from space_shooter import assets
from space_shooter.config import (
    CYAN,
    GREEN,
    GREY,
    LOW_HEALTH_THRESHOLD,
    MAGENTA,
    ORANGE,
    PLAYER_MAX_HEALTH,
    RED,
    WEAPON_MAX_LEVEL,
    WHITE,
    WIDTH,
    YELLOW,
)
from space_shooter.ui import draw_bar, draw_text


def draw_hud(surface: pygame.Surface, scene) -> None:
    player = scene.player
    # translucent strip
    strip = pygame.Surface((WIDTH, 54), pygame.SRCALPHA)
    strip.fill((0, 0, 0, 110))
    surface.blit(strip, (0, 0))

    # score / best / wave
    draw_text(surface, f"SCORE  {scene.score:,}", 28, (16, 8), WHITE, "topleft")
    draw_text(surface, f"BEST  {max(scene.best, scene.score):,}", 20, (16, 32), GREY, "topleft")
    draw_text(surface, f"WAVE {scene.director.wave}", 28, (WIDTH // 2, 8), CYAN, "midtop")

    # health bar
    bar = pygame.Rect(WIDTH - 216, 10, 200, 14)
    frac = player.health / PLAYER_MAX_HEALTH
    colour = GREEN if player.health > LOW_HEALTH_THRESHOLD else RED
    if player.health <= LOW_HEALTH_THRESHOLD and int(scene.time * 4) % 2:
        colour = ORANGE
    draw_bar(surface, bar, frac, colour)
    draw_text(surface, "HULL", 16, (bar.left - 6, bar.centery), GREY, "midright", shadow=False)

    # lives (small ship icons), bombs, weapon pips
    icon = assets.load_image("player0", 2)
    for i in range(player.lives):
        surface.blit(icon, (WIDTH - 216 + i * 28, 30))
    draw_text(surface, f"BOMB x{player.bombs}", 18, (WIDTH - 124, 32), (255, 140, 140), "topleft")
    for i in range(WEAPON_MAX_LEVEL):  # weapon level pips
        colour = ORANGE if i < player.weapon_level else (60, 60, 70)
        pygame.draw.rect(surface, colour, (WIDTH - 46 + i * 9, 32, 7, 14), border_radius=2)

    # combo
    if scene.combo.chain >= 3:
        mult = scene.combo.multiplier
        cx = WIDTH // 2
        draw_text(surface, f"x{mult} COMBO", 24, (cx, 36), YELLOW, "midtop")
        draw_bar(surface, pygame.Rect(cx - 50, 58, 100, 5), scene.combo.fraction, YELLOW, border=(0, 0, 0, 0))

    # boss bar
    boss = scene.boss
    if boss is not None and boss.alive():
        rect = pygame.Rect(WIDTH // 2 - 200, 70, 400, 12)
        draw_bar(surface, rect, boss.hp / boss.max_hp, MAGENTA)
        draw_text(surface, "DREADNOUGHT", 18, (WIDTH // 2, 86), MAGENTA, "midtop")

    if scene.game.settings.show_fps:
        draw_text(surface, f"{scene.game.fps:.0f} FPS", 16, (WIDTH - 8, surface.get_height() - 4), GREY, "bottomright")
