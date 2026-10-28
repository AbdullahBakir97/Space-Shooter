"""Collectible drops."""

from __future__ import annotations

import math
import random
from functools import cache

import pygame

from space_shooter import assets
from space_shooter.config import CYAN, GREEN, HEIGHT, ORANGE, POWERUP_SPEED, POWERUP_WEIGHTS, WHITE, YELLOW

KINDS = {
    # kind: (letter, colour)
    "weapon": ("W", ORANGE),
    "health": ("+", GREEN),
    "shield": ("S", CYAN),
    "bomb": ("B", (255, 110, 110)),
    "score": ("$", YELLOW),
}


def random_kind(rng: random.Random | None = None) -> str:
    rng = rng or random
    kinds = list(POWERUP_WEIGHTS)
    return rng.choices(kinds, [POWERUP_WEIGHTS[k] for k in kinds])[0]


@assets.register_cache
@cache
def _badge(kind: str) -> pygame.Surface:
    letter, colour = KINDS[kind]
    size = 34
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*colour, 90), (size // 2, size // 2), size // 2)
    pygame.draw.circle(surf, colour, (size // 2, size // 2), size // 2 - 3, 3)
    text = assets.font(26).render(letter, True, WHITE)
    surf.blit(text, text.get_rect(center=(size // 2, size // 2 + 1)))
    return surf


class PowerUp(pygame.sprite.Sprite):
    def __init__(self, kind: str, pos: tuple[float, float]) -> None:
        super().__init__()
        self.kind = kind
        self.base_image = _badge(kind)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=pos)
        self.x, self.y = float(pos[0]), float(pos[1])
        self.age = 0.0
        self.radius = 17

    def update(self, dt: float, world=None) -> None:
        self.age += dt
        self.y += POWERUP_SPEED * dt
        self.x += math.sin(self.age * 3) * 30 * dt
        self.rect.center = (round(self.x), round(self.y))
        # gentle pulse
        pulse = 1.0 + 0.08 * math.sin(self.age * 8)
        size = int(self.base_image.get_width() * pulse)
        self.image = pygame.transform.smoothscale(self.base_image, (size, size))
        self.rect = self.image.get_rect(center=self.rect.center)
        if self.rect.top > HEIGHT:
            self.kill()
