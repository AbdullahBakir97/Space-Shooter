"""The Warden: the machine that keeps the loop sealed. Act 1's boss."""

from __future__ import annotations

import math

import pygame

from space_shooter import procgen
from space_shooter.config import ENEMY_BULLET_SPEED, WARDEN_BASE_HP, WIDTH
from space_shooter.echoes import densest_cluster
from space_shooter.entities.enemies import Enemy

SWEEP_PERIOD = 0.9
SWEEP_SHOTS = 7
SWEEP_STEP = 0.35
SWEEP_SPREAD = 0.18
HUNT_PERIOD = 1.1
HUNT_SHOTS = 5
HUNT_SPREAD = 0.06
RING_PERIOD = 3.0
RING_SIZE = 12
EXPOSE_TIME = 1.5
COLLAPSE_SHOT_PERIOD = 1.4
FIRST_SHOT = 0.9


class Warden(Enemy):
    kind = "warden"

    def __init__(self, x: float, hp_mult: float = 1.0, speed_mult: float = 1.0, fire_mult: float = 1.0) -> None:
        self.body, self.eye = procgen.warden_sprites()
        super().__init__(x, hp_mult, speed_mult, fire_mult)
        self.is_boss = True
        mask = pygame.mask.from_surface(self.body)
        self.flash_frames = [mask.to_surface(setcolor=(210, 205, 196, 255), unsetcolor=(0, 0, 0, 0))]
        self.max_hp = self.hp = round(WARDEN_BASE_HP * hp_mult)
        self.radius = int(self.rect.width * 0.38)
        self.rect.midbottom = (x, -20)
        self.y = float(self.rect.centery)
        self.target_y = 150.0
        self.dir = 1.0
        self.fire_timer = FIRST_SHOT
        self.ring_timer = RING_PERIOD
        self.exposed_timer = 0.0
        self.sweep_angle = math.pi / 2
        self.hunt_echoes = True
        self.arrived = False

    def _load_frames(self) -> list[pygame.Surface]:
        return [self.body]

    # -- state ---------------------------------------------------------------
    @property
    def phase(self) -> int:
        frac = self.hp / self.max_hp
        return 1 if frac > 0.66 else 2 if frac > 0.33 else 3

    @property
    def eye_exposed(self) -> bool:
        return self.exposed_timer > 0

    def force_exposed(self, value: bool) -> None:
        """Test seam: open or close the eye window directly."""
        self.exposed_timer = EXPOSE_TIME if value else 0.0

    def hit(self, damage: int) -> bool:
        return super().hit(damage * 2 if self.eye_exposed else damage)

    def retreat(self) -> None:
        """The Warden never leaves."""

    # -- behaviour -----------------------------------------------------------
    def move(self, dt: float, world) -> None:
        self.exposed_timer = max(0.0, self.exposed_timer - dt)
        if not self.arrived:
            self.y = min(self.target_y, self.y + self.speed * 0.6 * dt)
            self.arrived = self.y >= self.target_y
            if not self.arrived:
                return
        phase = self.phase
        self.x += self.dir * self.speed * (0.45 + 0.25 * phase) * dt
        self.y = self.target_y + math.sin(self.age * 1.5) * 25
        half = self.rect.width / 2 + 4
        if self.x < half or self.x > WIDTH - half:
            self.dir *= -1
            self.x = min(WIDTH - half, max(half, self.x))
        self.fire_timer -= dt * self.fire_mult
        if self.fire_timer <= 0:
            if phase == 1:
                self.fire_timer += SWEEP_PERIOD
                self._sweep(world)
            elif phase == 2:
                self.fire_timer += HUNT_PERIOD
                self._hunt(world)
            else:
                self.fire_timer += COLLAPSE_SHOT_PERIOD
                self._volley(world, world.aim_point(), 1)
        if phase == 3:
            self.ring_timer -= dt
            if self.ring_timer <= 0:
                self.ring_timer += RING_PERIOD
                world.spawn_debris_ring((self.x, self.y), RING_SIZE)
                self.exposed_timer = EXPOSE_TIME

    @property
    def muzzle(self) -> tuple[float, float]:
        return (self.x, self.rect.bottom - 20)

    def _sweep(self, world) -> None:
        for i in range(SWEEP_SHOTS):
            angle = self.sweep_angle + (i - (SWEEP_SHOTS - 1) / 2) * SWEEP_SPREAD
            vel = (math.cos(angle) * ENEMY_BULLET_SPEED, math.sin(angle) * ENEMY_BULLET_SPEED)
            world.fire_enemy_bullet(self.muzzle, vel)
        self.sweep_angle += SWEEP_STEP

    def _hunt(self, world) -> None:
        """Alternate volleys: the densest knot of echoes, then the player's aim point."""
        if self.hunt_echoes:
            target = densest_cluster(world.echo_positions(), 90.0, fallback=world.aim_point())
        else:
            target = world.aim_point()
        self.hunt_echoes = not self.hunt_echoes
        self._volley(world, target, HUNT_SHOTS)

    def _volley(self, world, target: tuple[float, float], shots: int) -> None:
        ox, oy = self.muzzle
        base = math.atan2(target[1] - oy, target[0] - ox)
        speed = ENEMY_BULLET_SPEED * 1.15
        for i in range(shots):
            angle = base + (i - (shots - 1) / 2) * HUNT_SPREAD
            world.fire_enemy_bullet((ox, oy), (math.cos(angle) * speed, math.sin(angle) * speed), big=shots == 1)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        frame = self.image.copy()
        eye = self.eye.copy()
        glow = 255 if self.eye_exposed else 110 + int(60 * math.sin(self.age * 3))
        eye.set_alpha(glow)
        frame.blit(eye, (0, 0))
        self.image = frame
