"""Enemy behaviours. Each ``update`` receives the world (the gameplay scene)
which exposes ``player_pos``, ``fire_enemy_bullet`` and ``rng``.
"""

from __future__ import annotations

import math

import pygame

from space_shooter import assets
from space_shooter.config import (
    BOSS_BASE_HP,
    ENEMY_BASE_SPEED,
    ENEMY_BULLET_SPEED,
    ENEMY_HP,
    ENEMY_SCORE,
    HEIGHT,
    SPRITE_SCALE,
    WHITE,
    WIDTH,
)

FLASH_TIME = 0.08
HUE_SHIFT = {"zigzag": 120.0, "diver": 60.0, "gunner": 250.0, "boss": 300.0}


class Enemy(pygame.sprite.Sprite):
    kind = "drone"
    scale = SPRITE_SCALE

    def __init__(self, x: float, hp_mult: float = 1.0, speed_mult: float = 1.0, fire_mult: float = 1.0) -> None:
        super().__init__()
        self.frames = self._load_frames()
        self.flash_frames = [assets.silhouette(n, WHITE, self.scale) for n in assets.SPRITE_NAMES["enemy"]]
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

    def _load_frames(self) -> list[pygame.Surface]:
        names = assets.SPRITE_NAMES["enemy"]
        shift = HUE_SHIFT.get(self.kind)
        if shift:
            return [assets.hue_shifted(n, shift, self.scale) for n in names]
        return [assets.load_image(n, self.scale) for n in names]

    # -- damage --------------------------------------------------------------
    def hit(self, damage: int) -> bool:
        """Apply damage; return True if the enemy died."""
        self.hp -= damage
        self.flash = FLASH_TIME
        return self.hp <= 0

    # -- movement ------------------------------------------------------------
    def update(self, dt: float, world) -> None:
        self.age += dt
        self.flash = max(0.0, self.flash - dt)
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
            px, py = world.player_pos
            dx, dy = px - self.x, py - self.y
            dist = math.hypot(dx, dy) or 1.0
            vel = (dx / dist * ENEMY_BULLET_SPEED, dy / dist * ENEMY_BULLET_SPEED)
            world.fire_enemy_bullet((self.x, self.rect.bottom), vel)


class Boss(Enemy):
    """Big, tinted, multi-phase. Score and HP scale with the wave."""

    kind = "boss"
    scale = SPRITE_SCALE * 3

    def __init__(
        self, x: float, wave: int = 5, hp_mult: float = 1.0, speed_mult: float = 1.0, fire_mult: float = 1.0
    ) -> None:
        super().__init__(x, hp_mult, speed_mult, fire_mult)
        self.is_boss = True
        self.max_hp = self.hp = round(BOSS_BASE_HP * (1 + 0.5 * (wave // 5 - 1)) * hp_mult)
        self.score = ENEMY_SCORE["boss"] * (wave // 5)
        self.radius = int(self.rect.width * 0.38)
        self.rect.midbottom = (x, -40)
        self.y = float(self.rect.centery)
        self.target_y = 150
        self.fire_timer = 1.5
        self.dir = 1.0

    @property
    def phase(self) -> int:
        frac = self.hp / self.max_hp
        return 1 if frac > 0.66 else 2 if frac > 0.33 else 3

    def move(self, dt: float, world) -> None:
        if self.y < self.target_y:
            self.y += self.speed * 0.6 * dt
            return
        phase = self.phase
        self.x += self.dir * self.speed * (0.45 + 0.25 * phase) * dt
        self.y = self.target_y + math.sin(self.age * 1.5) * 25
        half = self.rect.width / 2 + 10
        if self.x < half or self.x > WIDTH - half:
            self.dir *= -1
            self.x = min(WIDTH - half, max(half, self.x))
        self.fire_timer -= dt * self.fire_mult
        if self.fire_timer <= 0:
            self.fire_timer = max(0.5, 1.6 - 0.35 * phase)
            self._fire_pattern(world, phase)

    def _fire_pattern(self, world, phase: int) -> None:
        origin = (self.x, self.rect.bottom - 10)
        px, py = world.player_pos
        dx, dy = px - origin[0], py - origin[1]
        base = math.atan2(dy, dx)
        count = 3 + 2 * phase
        spread = 0.35 + 0.15 * phase
        for i in range(count):
            angle = base + (i - (count - 1) / 2) * spread / max(1, count - 1) * 2
            speed = ENEMY_BULLET_SPEED * (1.0 + 0.1 * phase)
            world.fire_enemy_bullet(origin, (math.cos(angle) * speed, math.sin(angle) * speed), big=(phase == 3))
        if phase >= 2:  # straight-down curtain
            for off in (-60, 60):
                world.fire_enemy_bullet((origin[0] + off, origin[1]), (0, ENEMY_BULLET_SPEED * 0.9))

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        # never leaves the screen
        self.y = min(self.y, self.target_y + 25)


ENEMY_CLASSES: dict[str, type[Enemy]] = {
    "drone": Drone,
    "zigzag": Zigzag,
    "diver": Diver,
    "gunner": Gunner,
    "boss": Boss,
}
