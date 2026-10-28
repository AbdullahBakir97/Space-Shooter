"""Projectiles for both sides."""

from __future__ import annotations

from functools import cache

import pygame

from space_shooter import assets
from space_shooter.config import CYAN, HEIGHT, ORANGE, RED, WHITE, WIDTH, YELLOW

MARGIN = 40


@assets.register_cache
@cache
def _player_bullet_image(width: int, height: int) -> pygame.Surface:
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(surf, CYAN, (0, 0, width, height), border_radius=width // 2)
    pygame.draw.rect(surf, WHITE, (width // 4, 2, max(1, width // 2), height - 4), border_radius=1)
    return surf


@assets.register_cache
@cache
def _enemy_bullet_image(radius: int, colour: tuple[int, int, int]) -> pygame.Surface:
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, colour, (radius, radius), radius)
    pygame.draw.circle(surf, YELLOW, (radius, radius), max(1, radius // 2))
    return surf


class Bullet(pygame.sprite.Sprite):
    """Straight-line projectile; subclasses only pick an image."""

    def __init__(self, pos: tuple[float, float], vel: tuple[float, float], image: pygame.Surface, damage: int) -> None:
        super().__init__()
        self.x, self.y = float(pos[0]), float(pos[1])
        self.vx, self.vy = vel
        self.damage = damage
        self.image = image
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def update(self, dt: float, world=None) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rect.center = (round(self.x), round(self.y))
        if (
            self.rect.bottom < -MARGIN
            or self.rect.top > HEIGHT + MARGIN
            or self.rect.right < -MARGIN
            or self.rect.left > WIDTH + MARGIN
        ):
            self.kill()


class PlayerBullet(Bullet):
    def __init__(self, pos, vel, damage: int) -> None:
        super().__init__(pos, vel, _player_bullet_image(6, 18), damage)


class EnemyBullet(Bullet):
    def __init__(self, pos, vel, damage: int = 20, big: bool = False) -> None:
        image = _enemy_bullet_image(9 if big else 6, ORANGE if big else RED)
        super().__init__(pos, vel, image, damage)


@assets.register_cache
@cache
def _slug_image() -> pygame.Surface:
    surf = pygame.Surface((10, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (140, 62, 40), (0, 0, 10, 14))
    pygame.draw.ellipse(surf, (255, 122, 40), (3, 2, 4, 8))
    return surf


class SlugBullet(Bullet):
    """Slow heavy round: deals 3 hits and passes through one enemy."""

    def __init__(self, pos, vel, damage: int = 3, pierce: int = 1) -> None:
        super().__init__(pos, vel, _slug_image(), damage)
        self.pierce = pierce
        self.hit_ids: set[int] = set()
