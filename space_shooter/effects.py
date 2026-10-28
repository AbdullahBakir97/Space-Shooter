"""Visual juice: explosions, particles, floating text and screen shake."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter import assets, procgen
from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import ASH, BONE, EMBER, RUST


class Explosion(pygame.sprite.Sprite):
    """Plays the four explode frames once, optionally scaled up."""

    def __init__(self, center: tuple[float, float], scale: int = 4, frame_time: float = 0.06) -> None:
        super().__init__()
        self.frames = procgen.explosion_frames(scale)
        self.frame_time = frame_time
        self.timer = 0.0
        self.index = 0
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=center)

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.timer >= self.frame_time:
            self.timer -= self.frame_time
            self.index += 1
            if self.index >= len(self.frames):
                self.kill()
                return
            center = self.rect.center
            self.image = self.frames[self.index]
            self.rect = self.image.get_rect(center=center)


class Particle(pygame.sprite.Sprite):
    def __init__(
        self,
        pos: tuple[float, float],
        vel: tuple[float, float],
        colour: tuple[int, int, int],
        life: float,
        size: int = 3,
        gravity: float = 0.0,
    ) -> None:
        super().__init__()
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.colour = colour
        self.life = self.max_life = life
        self.size = size
        self.gravity = gravity
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.image.fill(colour)
        self.rect = self.image.get_rect(center=pos)

    def update(self, dt: float) -> None:
        self.life -= dt
        if self.life <= 0:
            self.kill()
            return
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        frac = self.life / self.max_life
        s = max(1, int(self.size * frac))
        if s != self.image.get_width():
            self.image = pygame.Surface((s, s), pygame.SRCALPHA)
            self.image.fill(self.colour)
        self.image.set_alpha(int(255 * frac))
        self.rect = self.image.get_rect(center=(self.x, self.y))


def burst(
    group: pygame.sprite.Group,
    pos: tuple[float, float],
    count: int = 12,
    colours: tuple[tuple[int, int, int], ...] = (EMBER, RUST, ASH),
    speed: float = 220.0,
    life: float = 0.5,
    size: int = 4,
    rng: random.Random | None = None,
) -> None:
    """Spawn a radial burst of particles into ``group``."""
    rng = rng or random
    for _ in range(count):
        angle = rng.uniform(0, math.tau)
        mag = rng.uniform(0.3, 1.0) * speed
        vel = (math.cos(angle) * mag, math.sin(angle) * mag)
        group.add(Particle(pos, vel, rng.choice(colours), rng.uniform(0.5, 1.0) * life, size))


def smoke(group: pygame.sprite.Group, pos, count: int = 4, rng: random.Random | None = None) -> None:
    """Slow, long-lived ash smoke that lingers after an explosion."""
    rng = rng or random
    for _ in range(count):
        vel = (rng.uniform(-25, 25), rng.uniform(-30, 5))
        group.add(Particle(pos, vel, ASH, rng.uniform(0.9, 1.4), rng.choice((5, 6, 7))))


class FloatingText(pygame.sprite.Sprite):
    """Score popups that drift up and fade."""

    def __init__(self, text: str, pos: tuple[float, float], colour=BONE, size: int = 22, life: float = 0.8) -> None:
        super().__init__()
        self.image = assets.font(size).render(text, True, colour)
        self.rect = self.image.get_rect(center=pos)
        self.y = float(pos[1])
        self.life = self.max_life = life

    def update(self, dt: float) -> None:
        self.life -= dt
        if self.life <= 0:
            self.kill()
            return
        self.y -= 45 * dt
        self.rect.centery = int(self.y)
        self.image.set_alpha(int(255 * self.life / self.max_life))


class ScreenShake:
    """Decaying random offset applied when blitting the playfield."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.cap = 24.0
        self.strength = 0.0
        self.offset = (0, 0)

    def add(self, amount: float) -> None:
        self.strength = min(self.cap, self.strength + amount)

    def update(self, dt: float) -> None:
        if self.strength <= 0.05 or not self.enabled:
            self.strength = 0.0
            self.offset = (0, 0)
            return
        self.offset = (
            int(random.uniform(-self.strength, self.strength)),
            int(random.uniform(-self.strength, self.strength)),
        )
        self.strength *= max(0.0, 1.0 - 9.0 * dt)


class Flash:
    """Full-screen colour flash that fades out (bomb, player death)."""

    def __init__(self) -> None:
        self.alpha = 0.0
        self.colour = BONE
        self.enabled = True
        self.surf = pygame.Surface((WIDTH, HEIGHT))

    def trigger(self, colour=BONE, alpha: float = 180.0) -> None:
        if not self.enabled:
            return
        self.colour = colour
        self.alpha = max(self.alpha, alpha)

    def update(self, dt: float) -> None:
        self.alpha = max(0.0, self.alpha - 420.0 * dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self.alpha > 0:
            self.surf.fill(self.colour)
            self.surf.set_alpha(int(self.alpha))
            surface.blit(self.surf, (0, 0))
