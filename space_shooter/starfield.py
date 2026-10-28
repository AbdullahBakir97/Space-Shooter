"""Three-layer parallax starfield with a few drifting nebula blobs."""

from __future__ import annotations

import random

import pygame

from space_shooter.config import HEIGHT, SPACE, WIDTH

LAYERS = (
    # (count, speed px/s, size, colour)
    (70, 25.0, 1, (90, 95, 130)),
    (40, 60.0, 2, (150, 160, 200)),
    (18, 130.0, 3, (240, 245, 255)),
)


class Starfield:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.layers: list[tuple[float, int, tuple[int, int, int], list[list[float]]]] = []
        for count, speed, size, colour in LAYERS:
            stars = [[self.rng.uniform(0, WIDTH), self.rng.uniform(0, HEIGHT)] for _ in range(count)]
            self.layers.append((speed, size, colour, stars))
        self.boost = 1.0  # >1 during warp (wave transitions)
        self.nebulae = [self._make_nebula() for _ in range(3)]

    def _make_nebula(self) -> dict:
        radius = self.rng.randint(90, 180)
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        hue = self.rng.choice([(40, 30, 90), (20, 50, 90), (80, 25, 70)])
        for r in range(radius, 0, -6):
            alpha = int(18 * (1 - r / radius))
            pygame.draw.circle(surf, (*hue, alpha), (radius, radius), r)
        return {
            "surf": surf,
            "x": self.rng.uniform(-radius, WIDTH - radius),
            "y": self.rng.uniform(-HEIGHT, HEIGHT),
            "speed": self.rng.uniform(8, 16),
        }

    def update(self, dt: float) -> None:
        for speed, _size, _colour, stars in self.layers:
            v = speed * self.boost * dt
            for star in stars:
                star[1] += v
                if star[1] > HEIGHT:
                    star[0] = self.rng.uniform(0, WIDTH)
                    star[1] -= HEIGHT + 4
        for neb in self.nebulae:
            neb["y"] += neb["speed"] * self.boost * dt
            if neb["y"] > HEIGHT:
                neb["y"] = -neb["surf"].get_height()
                neb["x"] = self.rng.uniform(-100, WIDTH - 100)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(SPACE)
        for neb in self.nebulae:
            surface.blit(neb["surf"], (neb["x"], neb["y"]))
        for speed, size, colour, stars in self.layers:
            stretch = max(1, int(self.boost * speed / 60))  # streaks while warping
            for x, y in stars:
                if stretch > 1:
                    pygame.draw.line(surface, colour, (x, y), (x, y - stretch), size)
                else:
                    pygame.draw.rect(surface, colour, (int(x), int(y), size, size))
