"""Environmental hazards for Act 1 encounters."""

from __future__ import annotations

import pygame

from space_shooter import procgen
from space_shooter.config import HEIGHT

DEBRIS_DAMAGE = 10


class Hazard(pygame.sprite.Sprite):
    blocks_bullets = False
    hurts_player = 0

    def __init__(self, image: pygame.Surface, pos, vel) -> None:
        super().__init__()
        self.image = image
        self.x, self.y = float(pos[0]), float(pos[1])
        self.vx, self.vy = vel
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))

    def update(self, dt: float, world=None) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rect.center = (round(self.x), round(self.y))
        if self.rect.top > HEIGHT + 40:
            self.kill()


class AshCloud(Hazard):
    """Slow drifting ash that is drawn over bullets, hiding them."""

    def __init__(self, pos, seed: int = 0) -> None:
        super().__init__(procgen.ash_cloud_sprite(seed % 4), pos, (8.0, 30.0))


class Hulk(Hazard):
    """A dead ship's hull. Blocks shots from both sides; breaks open for salvage."""

    blocks_bullets = True

    def __init__(self, pos, hp: int = 8, rare_drop: bool = False, seed: int = 0) -> None:
        super().__init__(procgen.hulk_sprite(seed % 5), pos, (0.0, 6.0))
        self.hp = hp
        self.rare_drop = rare_drop

    def hit(self, damage: int) -> bool:
        self.hp -= damage
        return self.hp <= 0

    def shadows(self, x: float, y: float) -> bool:
        """True if this hulk sits above (x, y) and covers it from the star."""
        return self.rect.left <= x <= self.rect.right and self.rect.bottom <= y


class Debris(Hazard):
    """Falling wreckage: one shot destroys it, contact dents the hull."""

    hurts_player = DEBRIS_DAMAGE

    def __init__(self, pos, vel, seed: int = 0) -> None:
        super().__init__(procgen.debris_sprite(seed % 6), pos, vel)
        self.radius = 9
