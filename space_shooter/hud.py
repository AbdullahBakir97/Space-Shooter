"""In-game overlay. Task 8 replaces this with the full cockpit readout."""

from __future__ import annotations

import pygame

from space_shooter.config import LOW_HEALTH_THRESHOLD, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.palette import ASH, EMBER, RUST, STEEL, STEEL_DIM
from space_shooter.salvage import SLOTS
from space_shooter.ui import draw_bar, draw_text


def draw_hud(surface: pygame.Surface, scene) -> None:
    player = scene.player
    strip = pygame.Surface((WIDTH, 54), pygame.SRCALPHA)
    strip.fill((0, 0, 0, 120))
    surface.blit(strip, (0, 0))

    draw_text(surface, scene.director.encounter.name, 22, (WIDTH // 2, 12), ASH, "midtop")

    bar = pygame.Rect(WIDTH - 216, 10, 200, 14)
    low = player.health <= LOW_HEALTH_THRESHOLD
    colour = EMBER if low and int(scene.time * 4) % 2 else (RUST if low else STEEL)
    draw_bar(surface, bar, player.health / PLAYER_MAX_HEALTH, colour, border=STEEL_DIM)
    draw_text(surface, "HULL", 16, (bar.left - 6, bar.centery), ASH, "midright", shadow=False)

    # hardpoints: filled steel, empty dim, scarred ember
    draw_text(surface, "SLOTS", 16, (WIDTH - 222, 38), ASH, "midright", shadow=False)
    for i, slot in enumerate(SLOTS):
        part = player.loadout.slots[slot]
        colour = STEEL_DIM if part is None else (EMBER if part.rare else STEEL)
        pygame.draw.rect(surface, colour, (WIDTH - 216 + i * 18, 32, 14, 12), border_radius=2)

    boss = scene.boss
    if boss is not None and boss.alive():
        rect = pygame.Rect(WIDTH // 2 - 200, 70, 400, 10)
        draw_bar(surface, rect, boss.hp / boss.max_hp, EMBER if boss.eye_exposed else RUST, border=STEEL_DIM)
        draw_text(surface, "THE WARDEN", 18, (WIDTH // 2, 86), ASH, "midtop")

    if scene.game.settings.show_fps:
        draw_text(surface, f"{scene.game.fps:.0f} FPS", 16, (WIDTH - 8, surface.get_height() - 4), ASH, "bottomright")
