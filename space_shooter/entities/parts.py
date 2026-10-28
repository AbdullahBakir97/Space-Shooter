"""Salvage in the world: drifting drops, part behaviours and part drawing."""

from __future__ import annotations

import math

import pygame

from space_shooter import procgen
from space_shooter.config import BULLET_SPEED, HEIGHT, PLAYER_BULLET_DAMAGE
from space_shooter.entities.bullets import Bullet, PlayerBullet, SlugBullet
from space_shooter.salvage import SLOT_OFFSETS, Loadout

SLUG_SPEED = 520.0
SLUG_DAMAGE = 3
SLUG_DAMAGE_RARE = 5
TURRET_RANGE = 260.0
TURRET_PERIOD = 0.5
TURRET_PERIOD_RARE = 0.33
BLINK_TIME = 2.0


def scaled(damage: int, mult: float) -> int:
    """Damage after a multiplier, rounded up, never below 1."""
    return max(1, math.ceil(damage * mult - 1e-9))


def gun_volley(x: float, top: float, loadout: Loadout, damage_mult: float = 1.0) -> list[Bullet]:
    """One trigger pull: the fixed main gun plus every slug cannon on the hull."""
    bullets: list[Bullet] = [PlayerBullet((x, top + 6), (0, -BULLET_SPEED), scaled(PLAYER_BULLET_DAMAGE, damage_mult))]
    for slot, part in loadout.parts():
        if part.kind == "slug":
            side = -1 if slot.endswith("_l") else 1
            damage = scaled(SLUG_DAMAGE_RARE if part.rare else SLUG_DAMAGE, damage_mult)
            bullets.append(SlugBullet((x + side * 14, top), (0, -SLUG_SPEED), damage))
    return bullets


class Drop(pygame.sprite.Sprite):
    """A part code (``"turret"``, ``"slug*"``) or ``"patch"`` drifting in space."""

    def __init__(
        self, code: str, pos, vel=(0.0, 90.0), lifetime: float | None = None, pickup_delay: float = 0.0
    ) -> None:
        super().__init__()
        self.code = code
        self.pickup_delay = pickup_delay
        if code == "patch":
            self.base_image = procgen.patch_sprite()
        else:
            self.base_image = procgen.part_sprite(code.rstrip("*"), code.endswith("*"))
        self.image = self.base_image
        self.x, self.y = float(pos[0]), float(pos[1])
        self.vx, self.vy = vel
        self.lifetime = lifetime
        self.age = 0.0
        self.angle = 0.0
        self.spin = 90.0 if lifetime is not None else 25.0
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        self.radius = 16

    @property
    def collectable(self) -> bool:
        return self.age >= self.pickup_delay

    @property
    def blinking(self) -> bool:
        return self.lifetime is not None and self.lifetime - self.age <= BLINK_TIME

    def update(self, dt: float, world=None) -> None:
        self.age += dt
        if self.lifetime is not None and self.age >= self.lifetime:
            self.kill()
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0.0, 1.0 - 0.6 * dt)  # knocked-off parts slow as they tumble
        self.angle = (self.angle + self.spin * dt) % 360
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        if self.blinking and int(self.age * 8) % 2:
            self.image = self.image.copy()
            self.image.set_alpha(70)
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        if self.rect.top > HEIGHT + 20:
            self.kill()


class PartRig:
    """Runs autonomous part behaviour (turrets) for one ship."""

    def __init__(self) -> None:
        self.cooldowns: dict[str, float] = {}

    def update(self, dt: float, loadout: Loadout, origin, enemies, damage_mult: float) -> list[Bullet]:
        shots: list[Bullet] = []
        ox, oy = origin
        for slot, part in loadout.parts():
            if part.kind != "turret":
                continue
            cd = self.cooldowns.get(slot, 0.0) - dt
            if cd > 0:
                self.cooldowns[slot] = cd
                continue
            sx, sy = ox + SLOT_OFFSETS[slot][0], oy + SLOT_OFFSETS[slot][1]
            target = None
            best = TURRET_RANGE**2
            for e in enemies:
                d2 = (e.x - sx) ** 2 + (e.y - sy) ** 2
                if d2 <= best:
                    target, best = e, d2
            if target is None:
                self.cooldowns[slot] = 0.0
                continue
            angle = math.atan2(target.y - sy, target.x - sx)
            speed = BULLET_SPEED * 0.8
            damage = scaled(PLAYER_BULLET_DAMAGE, damage_mult)
            shots.append(PlayerBullet((sx, sy), (math.cos(angle) * speed, math.sin(angle) * speed), damage))
            self.cooldowns[slot] = TURRET_PERIOD_RARE if part.rare else TURRET_PERIOD
        return shots


def draw_loadout(surface: pygame.Surface, loadout: Loadout, center, alpha: int = 255) -> None:
    cx, cy = center
    for slot, part in loadout.parts():
        img = procgen.part_sprite(part.kind, part.rare)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        dx, dy = SLOT_OFFSETS[slot]
        surface.blit(img, img.get_rect(center=(cx + dx, cy + dy)))
