"""Dim parallax stars, the dying star, and drifting ash."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import ASH, EMBER, RUST, VOID

LAYERS = (
    # (count, speed px/s, size, colour)
    (60, 18.0, 1, (52, 58, 78)),
    (26, 42.0, 2, (100, 110, 136)),
)
STAR_PERIOD = 6.0
STAR_PULSE = 4.0


class DyingStar:
    """An ember disc half above the top edge, breathing slowly."""

    def __init__(self) -> None:
        self.x = WIDTH * 0.72
        self.y = -150.0
        self.base_radius = 210.0
        self.time = 0.0
        self.radius = self.base_radius
        self.glow = pygame.Surface((WIDTH, 260), pygame.SRCALPHA)

    def update(self, dt: float) -> None:
        self.time += dt
        self.radius = self.base_radius + STAR_PULSE * math.sin(math.tau * self.time / STAR_PERIOD)

    def draw(self, surface: pygame.Surface) -> None:
        self.glow.fill((0, 0, 0, 0))
        r = int(self.radius)
        for i, alpha in enumerate((14, 22, 34)):
            pygame.draw.circle(self.glow, (*RUST, alpha), (int(self.x), int(self.y)), r + 60 - i * 20)
        pygame.draw.circle(self.glow, (*EMBER, 210), (int(self.x), int(self.y)), r)
        pygame.draw.circle(self.glow, (255, 170, 90, 120), (int(self.x), int(self.y)), r - 18)
        surface.blit(self.glow, (0, 0))


class AshField:
    """Slow flecks of ash drifting behind the action."""

    def __init__(self, rng: random.Random, count: int = 60) -> None:
        self.rng = rng
        self.flecks = [self._fleck(rng.uniform(0, HEIGHT)) for _ in range(count)]

    def _fleck(self, y: float) -> list[float]:
        r = self.rng
        return [r.uniform(0, WIDTH), y, r.uniform(15, 35), r.uniform(0, math.tau), r.choice((1, 2)), r.uniform(40, 120)]

    def update(self, dt: float, boost: float) -> None:
        for f in self.flecks:
            f[1] += f[2] * boost * dt
            f[3] += dt
            f[0] += math.sin(f[3]) * 8 * dt
            if f[1] > HEIGHT:
                f[:] = self._fleck(-4)

    def draw(self, surface: pygame.Surface) -> None:
        for x, y, _speed, _phase, size, alpha in self.flecks:
            dot = pygame.Surface((size, size), pygame.SRCALPHA)
            dot.fill((*ASH, int(alpha)))
            surface.blit(dot, (x, y))


class Starfield:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.layers: list[tuple[float, int, tuple[int, int, int], list[list[float]]]] = []
        for count, speed, size, colour in LAYERS:
            stars = [[self.rng.uniform(0, WIDTH), self.rng.uniform(0, HEIGHT)] for _ in range(count)]
            self.layers.append((speed, size, colour, stars))
        self.boost = 1.0  # >1 during drifts
        self.star = DyingStar()
        self.ash = AshField(self.rng)

    def update(self, dt: float) -> None:
        for speed, _size, _colour, stars in self.layers:
            v = speed * self.boost * dt
            for star in stars:
                star[1] += v
                if star[1] > HEIGHT:
                    star[0] = self.rng.uniform(0, WIDTH)
                    star[1] -= HEIGHT + 4
        self.star.update(dt)
        self.ash.update(dt, self.boost)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(VOID)
        for speed, size, colour, stars in self.layers:
            stretch = max(1, int(self.boost * speed / 40))
            for x, y in stars:
                if stretch > 1:
                    pygame.draw.line(surface, colour, (x, y), (x, y - stretch), size)
                else:
                    pygame.draw.rect(surface, colour, (int(x), int(y), size, size))
        self.star.draw(surface)
        self.ash.draw(surface)
