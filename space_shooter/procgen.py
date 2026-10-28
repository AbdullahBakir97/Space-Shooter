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


@assets.register_cache
@cache
def hulk_sprite(seed: int, scale: int = SPRITE_SCALE) -> pygame.Surface:
    """A dead ship's broken hull: a jagged slab in steel_dim and rust."""
    import random

    rng = random.Random(seed)
    w, h = 16, 8
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        top = rng.randint(0, 2)
        bottom = h - rng.randint(0, 2)
        for y in range(top, bottom):
            colour = RUST if rng.random() < 0.18 else (STEEL if y == top else STEEL_DIM)
            surf.set_at((x, y), (*colour, 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def ash_cloud_sprite(seed: int) -> pygame.Surface:
    import random

    rng = random.Random(seed)
    surf = pygame.Surface((200, 130), pygame.SRCALPHA)
    puffs = [(100, 65, 48)] + [(rng.randint(45, 155), rng.randint(40, 90), rng.randint(18, 40)) for _ in range(24)]
    for x, y, r in puffs:
        puff = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(puff, (*ASH, 60), (r, r), r)
        surf.blit(puff, (x - r, y - r))  # blit blends, so overlapping puffs build density
    return surf


@assets.register_cache
@cache
def debris_sprite(seed: int, scale: int = 3) -> pygame.Surface:
    import random

    rng = random.Random(seed)
    surf = pygame.Surface((5, 5), pygame.SRCALPHA)
    for x in range(5):
        for y in range(5):
            if (x - 2) ** 2 + (y - 2) ** 2 <= 4 and rng.random() < 0.85:
                surf.set_at((x, y), (*(RUST if rng.random() < 0.4 else ASH), 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def warden_sprites(scale: int = SPRITE_SCALE) -> tuple[pygame.Surface, pygame.Surface]:
    """The Warden: a symmetric 48x32 machine body plus a separate ember eye layer."""
    import random

    rng = random.Random(1987)
    w, h, half = 48, 32, 24
    body = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(half):
        # silhouette: a wide crown tapering to a lower jaw, with ragged edges
        reach = 1.0 - (half - 1 - x) / half  # 0 at the outer edge, 1 at the centre
        top = int(10 - 8 * reach) + rng.randint(0, 1)
        bottom = int(14 + 16 * reach) - rng.randint(0, 2)
        for y in range(max(0, top), min(h, bottom)):
            roll = rng.random()
            if y in (top, top + 1):
                colour = STEEL
            elif roll < 0.12:
                colour = RUST
            elif roll < 0.2:
                colour = ASH
            else:
                colour = STEEL_DIM
            body.set_at((x, y), (*colour, 255))
            body.set_at((w - 1 - x, y), (*colour, 255))
    # the socket the eye sits in
    pygame.draw.circle(body, (6, 7, 12, 255), (half, 18), 5)
    eye = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(eye, (*EMBER, 255), (half, 18), 4)
    pygame.draw.circle(eye, (*BONE, 255), (half, 18), 1)
    if scale != 1:
        body = pygame.transform.scale_by(body, scale)
        eye = pygame.transform.scale_by(eye, scale)
    return body, eye
