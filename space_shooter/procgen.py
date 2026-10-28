"""Procedurally generated art (and later, audio)."""

from __future__ import annotations

from functools import cache

import pygame

from space_shooter import assets
from space_shooter.config import SPRITE_SCALE
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM

# 6x6 pixel masks per part kind: "#" body, "+" highlight, "o" accent.
_PART_SHAPES: dict[str, tuple[str, ...]] = {
    "turret": ("..++..", ".#oo#.", "######", "#.##.#", ".####.", "..##.."),
    "slug": ("..++..", "..##..", ".####.", ".#oo#.", "######", "##..##"),
    "tractor": (".####.", "#....#", "#.oo.#", "#.oo.#", "#....#", ".####."),
    "armour": ("######", "#++++#", "#+##+#", "#+##+#", "#++++#", "######"),
    "thruster": (".####.", ".#++#.", "######", ".#oo#.", ".o..o.", "o....o"),
    "claw": ("#....#", "##..##", ".#oo#.", ".####.", "..##..", "..++.."),
}
_PART_COLOURS = {"#": STEEL_DIM, "+": STEEL, "o": RUST}


@assets.register_cache
@cache
def part_sprite(kind: str, rare: bool = False, scale: int = SPRITE_SCALE) -> pygame.Surface:
    rows = _PART_SHAPES.get(kind, _PART_SHAPES["armour"])
    surf = pygame.Surface((6, 6), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in _PART_COLOURS:
                colour = EMBER if (rare and ch == "o") else _PART_COLOURS[ch]
                surf.set_at((x, y), (*colour, 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def patch_sprite(scale: int = SPRITE_SCALE) -> pygame.Surface:
    rows = ("..##..", ".#++#.", "##++##", "##++##", ".#++#.", "..##..")
    surf = pygame.Surface((6, 6), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x, y), (*(BONE if ch == "+" else ASH), 255))
    return pygame.transform.scale_by(surf, scale)
