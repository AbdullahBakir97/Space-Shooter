"""Enemy behaviours. Each ``update`` receives the world (the gameplay scene)
which exposes ``player_pos``, ``fire_enemy_bullet`` and ``rng``.
"""

from __future__ import annotations

import math

import pygame

from space_shooter import assets, procgen
from space_shooter.config import (
    ENEMY_BASE_SPEED,
    ENEMY_BULLET_SPEED,
    ENEMY_HP,
    ENEMY_SCORE,
    HEIGHT,
    SPRITE_SCALE,
    WIDTH,
)
from space_shooter.palette import BONE

FLASH_TIME = 0.08


class Enemy(pygame.sprite.Sprite):
    kind = "drone"
    scale = SPRITE_SCALE

    def __init__(self, x: float, hp_mult: float = 1.0, speed_mult: float = 1.0, fire_mult: float = 1.0) -> None:
        super().__init__()
        self.frames = self._load_frames()
        self.flash_frames = [assets.silhouette(n, BONE, self.scale) for n in assets.SPRITE_NAMES["enemy"]]
        self.image = self.frames[0]
        self.rect = self.image.get_rect(midbottom=(x, -10))
        self.x, self.y = float(x), float(self.rect.centery)
        self.radius = int(self.rect.width * 0.4)
        self.max_hp = self.hp = max(1, round(ENEMY_HP.get(self.kind, 1) * hp_mult))
        self.speed = ENEMY_BASE_SPEED * speed_mult
        self.fire_mult = fire_mult
        self.score = ENEMY_SCORE[self.kind]
        self.age = 0.0
        self.flash = 0.0
        self.is_boss = False
        self.retreating = False

    def _load_frames(self) -> list[pygame.Surface]:
        return [procgen.scarred_variant(n, self.kind, self.scale) for n in assets.SPRITE_NAMES["enemy"]]

    # -- damage --------------------------------------------------------------
    def hit(self, damage: int) -> bool:
        """Apply damage; return True if the enemy died."""
        self.hp -= damage
        self.flash = FLASH_TIME
        return self.hp <= 0

    def retreat(self) -> None:
        """Leave the field upward (time cap reached)."""
        if not self.is_boss:
            self.retreating = True

    # -- movement ------------------------------------------------------------
    def update(self, dt: float, world) -> None:
        self.age += dt
        self.flash = max(0.0, self.flash - dt)
        if self.retreating:
            self.y -= self.speed * 1.5 * dt
            if self.y < -80:
                self.kill()
        else:
            self.move(dt, world)
        self.rect.center = (round(self.x), round(self.y))
        frame = int(self.age * 8) % len(self.frames)
        self.image = self.flash_frames[frame] if self.flash > 0 else self.frames[frame]
        if self.rect.top > HEIGHT + 20:
            self.kill()

    def move(self, dt: float, world) -> None:
        self.y += self.speed * dt
        self.x += math.sin(self.age * 2.0) * 20 * dt


class Drone(Enemy):
    kind = "drone"


class Zigzag(Enemy):
    kind = "zigzag"

    def __init__(self, x: float, **kw) -> None:
        super().__init__(x, **kw)
        self.origin_x = x
        self.amplitude = min(x - 30, WIDTH - 30 - x, 140)

    def move(self, dt: float, world) -> None:
        self.y += self.speed * 0.8 * dt
        self.x = self.origin_x + math.sin(self.age * 3.0) * self.amplitude


class Diver(Enemy):
    """Hovers near the top, then dives straight at where the player is."""

    kind = "diver"
    HOVER_Y = 110
    HOVER_TIME = 0.9

    def __init__(self, x: float, **kw) -> None:
        super().__init__(x, **kw)
        self.state = "enter"
        self.hover = 0.0
        self.dive_vx = 0.0
        self.dive_vy = 0.0

    def move(self, dt: float, world) -> None:
        if self.state == "enter":
            self.y += self.speed * 1.4 * dt
            if self.y >= self.HOVER_Y:
                self.state = "hover"
        elif self.state == "hover":
            self.hover += dt
            self.x += math.sin(self.age * 10) * 60 * dt
            if self.hover >= self.HOVER_TIME:
                px, py = world.player_pos
                dx, dy = px - self.x, py - self.y
                dist = math.hypot(dx, dy) or 1.0
                dive_speed = self.speed * 3.2
                self.dive_vx, self.dive_vy = dx / dist * dive_speed, max(dy / dist, 0.35) * dive_speed
                self.state = "dive"
        else:
            self.x += self.dive_vx * dt
            self.y += self.dive_vy * dt


class Gunner(Enemy):
    """Parks at a firing line, strafes, and shoots aimed shots."""

    kind = "gunner"

    def __init__(self, x: float, **kw) -> None:
        super().__init__(x, **kw)
        self.line_y = 130 + (hash(int(x)) % 60)
        self.dir = 1.0 if x < WIDTH / 2 else -1.0
        self.fire_timer = 1.2
        self.linger = 7.0

    def move(self, dt: float, world) -> None:
        if self.y < self.line_y:
            self.y += self.speed * dt
            return
        self.linger -= dt
        if self.linger <= 0:  # eventually leaves so a wave can't stall
            self.y += self.speed * 1.5 * dt
            return
        self.x += self.dir * self.speed * 0.6 * dt
        if self.x < 40 or self.x > WIDTH - 40:
            self.dir *= -1
            self.x = min(WIDTH - 40, max(40, self.x))
        self.fire_timer -= dt * self.fire_mult
        if self.fire_timer <= 0:
            self.fire_timer = world.rng.uniform(1.4, 2.2)
            px, py = world.aim_point()
            dx, dy = px - self.x, py - self.y
            dist = math.hypot(dx, dy) or 1.0
            vel = (dx / dist * ENEMY_BULLET_SPEED, dy / dist * ENEMY_BULLET_SPEED)
            world.fire_enemy_bullet((self.x, self.rect.bottom), vel)


ENEMY_CLASSES: dict[str, type[Enemy]] = {
    "drone": Drone,
    "zigzag": Zigzag,
    "diver": Diver,
    "gunner": Gunner,
}


def _register_warden() -> None:
    from space_shooter.entities.warden import Warden

    ENEMY_CLASSES["warden"] = Warden


_register_warden()
