"""The cockpit readout drawn over the playfield."""

from __future__ import annotations

import math

import pygame

from space_shooter import assets, procgen
from space_shooter.config import HEIGHT, LOW_HEALTH_THRESHOLD, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM, VOID
from space_shooter.salvage import SLOT_OFFSETS, SLOTS, Part
from space_shooter.ui import draw_bar, draw_text

HULL_CELLS = 10
SCHEMATIC_SCALE = 0.6
SCHEMATIC_CENTRE = (58, HEIGHT - 62)


def slot_colour(part: Part | None) -> tuple[int, int, int]:
    if part is None:
        return STEEL_DIM
    return EMBER if part.rare else STEEL


def _hull_colour(scene) -> tuple[int, int, int]:
    if scene.player.health > LOW_HEALTH_THRESHOLD:
        return STEEL
    return EMBER if int(scene.time * 4) % 2 else RUST


def _draw_schematic(surface: pygame.Surface, scene) -> None:
    """A small damaged diagram of the tug with its six hardpoints lit."""
    cx, cy = SCHEMATIC_CENTRE
    panel = pygame.Surface((236, 104), pygame.SRCALPHA)
    panel.fill((*VOID, 170))
    surface.blit(panel, (12, HEIGHT - 116))
    pygame.draw.rect(surface, STEEL_DIM, (12, HEIGHT - 116, 236, 104), 1)
    outline = assets.silhouette("player0", STEEL_DIM, 3)
    surface.blit(outline, outline.get_rect(center=(cx, cy)))
    for slot in SLOTS:
        ox, oy = SLOT_OFFSETS[slot]
        pos = (int(cx + ox * SCHEMATIC_SCALE * 1.4), int(cy + oy * SCHEMATIC_SCALE * 1.4))
        pygame.draw.rect(surface, slot_colour(scene.player.loadout.slots[slot]), (pos[0] - 4, pos[1] - 4, 8, 8))
    # hull as ten cells
    filled = math.ceil(HULL_CELLS * scene.player.health / PLAYER_MAX_HEALTH)
    colour = _hull_colour(scene)
    draw_text(surface, "HULL", 16, (112, HEIGHT - 100), ASH, "topleft", shadow=False)
    for i in range(HULL_CELLS):
        rect = (112 + i * 13, HEIGHT - 82, 10, 16)
        pygame.draw.rect(surface, colour if i < filled else STEEL_DIM, rect, 0 if i < filled else 1)
    draw_text(
        surface, f"{len(scene.player.loadout.parts())}/6 PARTS", 16, (112, HEIGHT - 56), ASH, "topleft", shadow=False
    )


def _draw_roster(surface: pygame.Surface, scene) -> None:
    alive = {e.loop for e in scene.echoes if e.alive()}
    icon = assets.silhouette("player0", STEEL, 2)
    lost_icon = assets.silhouette("player0", STEEL_DIM, 2)
    x = WIDTH - 20
    for loop in reversed(scene.roster):
        x -= icon.get_width() + 6
        surface.blit(icon if loop in alive else lost_icon, (x, 16))
        if loop not in alive:
            pygame.draw.line(surface, RUST, (x, 16), (x + icon.get_width(), 16 + icon.get_height()), 2)
    if scene.roster:
        draw_text(surface, "ECHOES", 14, (WIDTH - 20, 52), ASH, "topright", shadow=False)


def draw_hud(surface: pygame.Surface, scene) -> None:
    draw_text(surface, f"LOOP {scene.loop}", 24, (20, 16), BONE, "topleft")
    draw_text(surface, scene.director.encounter.name, 18, (20, 40), ASH, "topleft")
    _draw_roster(surface, scene)
    _draw_schematic(surface, scene)

    boss = scene.boss
    if boss is not None and boss.alive():
        rect = pygame.Rect(WIDTH // 2 - 200, 20, 400, 8)
        exposed = getattr(boss, "eye_exposed", False)
        draw_bar(surface, rect, boss.hp / boss.max_hp, EMBER if exposed else RUST, border=STEEL_DIM)
        draw_text(surface, "THE WARDEN", 16, (WIDTH // 2, 32), ASH, "midtop", shadow=False)

    if scene.warning_text and int(scene.time * 5) % 2:
        draw_text(surface, scene.warning_text, 28, (WIDTH // 2, 110), EMBER)

    if scene.game.settings.show_fps:
        draw_text(surface, f"{scene.game.fps:.0f} FPS", 16, (WIDTH - 8, HEIGHT - 4), ASH, "bottomright")
    surface.blit(procgen.cockpit_overlay((WIDTH, HEIGHT)), (0, 0))
