"""Salvage in the world: drifting drops, part behaviours and part drawing."""

from __future__ import annotations

import math

import pygame

from space_shooter import procgen
from space_shooter.config import BULLET_SPEED, HEIGHT, PLAYER_BULLET_DAMAGE
from space_shooter.entities.bullets import Bullet, HeavySlug, PlayerBullet, SlugBullet
from space_shooter.salvage import SLOT_OFFSETS, Loadout

SLUG_SPEED = 520.0
SLUG_DAMAGE = 3
SLUG_DAMAGE_RARE = 5
HEAVY_DAMAGE = 4
HEAVY_DAMAGE_RARE = 6
TURRET_RANGE = 900.0
BURST_GAP = 0.08
BLINK_TIME = 2.0


def scaled(damage: int, mult: float) -> int:
    """Damage after a multiplier, rounded up, never below 1."""
    return max(1, math.ceil(damage * mult - 1e-9))


def gun_volley(x: float, top: float, loadout: Loadout, damage_mult: float = 1.0, heavy: bool = False) -> list[Bullet]:
    """One trigger pull: the fixed main gun plus every slug cannon on the hull.

    ``heavy`` swaps each slug round for a HeavySlug that pierces its whole line.
    """
    main = PlayerBullet((x, top + 6), (0, -BULLET_SPEED), scaled(PLAYER_BULLET_DAMAGE, damage_mult))
    bullets: list[Bullet] = [main]
    for slot, part in loadout.parts():
        if part.kind == "slug":
            side = -1 if slot.endswith("_l") else 1
            pos, vel = (x + side * 14, top), (0, -SLUG_SPEED)
            if heavy:
                damage = scaled(HEAVY_DAMAGE_RARE if part.rare else HEAVY_DAMAGE, damage_mult)
                bullets.append(HeavySlug(pos, vel, damage))
            else:
                damage = scaled(SLUG_DAMAGE_RARE if part.rare else SLUG_DAMAGE, damage_mult)
                bullets.append(SlugBullet(pos, vel, damage))
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
    """Autonomous turret behaviour for one ship: targeting, swivel, bursts, twin sync."""

    def __init__(self) -> None:
        self.cooldowns: dict[str, float] = {}
        self.aim: dict[str, float] = {}
        self.queued: dict[str, float] = {}  # scarred turrets: time until the burst's second round

    def _fire(self, slot: str, origin, target, damage: int) -> PlayerBullet:
        sx, sy = origin[0] + SLOT_OFFSETS[slot][0], origin[1] + SLOT_OFFSETS[slot][1]
        angle = math.atan2(target.y - sy, target.x - sx)
        self.aim[slot] = angle
        speed = BULLET_SPEED * 0.8
        return PlayerBullet((sx, sy), (math.cos(angle) * speed, math.sin(angle) * speed), damage)

    def update(self, dt: float, loadout: Loadout, origin, enemies, damage_mult: float) -> list[Bullet]:
        turrets = [(slot, part) for slot, part in loadout.parts() if part.kind == "turret"]
        if not turrets:
            return []
        ox, oy = origin
        candidates = [e for e in enemies if (e.x - ox) ** 2 + (e.y - oy) ** 2 <= TURRET_RANGE**2]
        target = min(candidates, key=lambda e: (e.x - ox) ** 2 + (e.y - oy) ** 2, default=None)
        damage = scaled(PLAYER_BULLET_DAMAGE, damage_mult)
        period = loadout.turret_period()
        twin = loadout.paired("turret")
        keys = {"twin" if twin else slot for slot, _ in turrets}
        for key in keys:  # each cooldown group ticks once per update
            self.cooldowns[key] = max(0.0, self.cooldowns.get(key, 0.0) - dt)
        shots: list[Bullet] = []
        fired: set[str] = set()
        for slot, part in turrets:
            if slot in self.queued:  # the second round of a scarred burst
                self.queued[slot] -= dt
                if self.queued[slot] <= 0:
                    del self.queued[slot]
                    if target is not None:
                        shots.append(self._fire(slot, origin, target, damage))
            key = "twin" if twin else slot
            if target is None or self.cooldowns[key] > 0:
                continue
            shots.append(self._fire(slot, origin, target, damage))
            fired.add(key)
            if part.rare:
                self.queued[slot] = BURST_GAP
        for key in fired:
            self.cooldowns[key] = period
        return shots


def draw_loadout(
    surface: pygame.Surface, loadout: Loadout, center, alpha: int = 255, aim: dict[str, float] | None = None
) -> None:
    """Draw fitted parts; turrets swivel to ``aim`` (radians, 0 = right, -pi/2 = up)."""
    cx, cy = center
    for slot, part in loadout.parts():
        img = procgen.part_sprite(part.kind, part.rare)
        if part.kind == "turret" and aim and slot in aim:
            img = pygame.transform.rotate(img, -math.degrees(aim[slot]) - 90)
        cracks = loadout.armour_hits() - part.armour_left if part.kind == "armour" else 0
        if cracks > 0:
            img = img.copy()
            w, h = img.get_size()
            pygame.draw.line(img, (20, 16, 14), (2, 3), (w - 6, h - 2), 2)
            if cracks > 1:
                pygame.draw.line(img, (20, 16, 14), (w - 3, 2), (4, h - 5), 2)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        dx, dy = SLOT_OFFSETS[slot]
        surface.blit(img, img.get_rect(center=(cx + dx, cy + dy)))
