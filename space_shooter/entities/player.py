"""The salvage tug."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter import assets
from space_shooter.config import (
    BULLET_SPEED,
    HEIGHT,
    PLAYER_BULLET_DAMAGE,
    PLAYER_HIT_INVULN_TIME,
    PLAYER_INVULN_TIME,
    PLAYER_MAX_HEALTH,
    PLAYER_SPEED,
    WEAPON_COOLDOWN,
    WIDTH,
)
from space_shooter.entities.bullets import Bullet, PlayerBullet, SlugBullet
from space_shooter.entities.parts import draw_loadout
from space_shooter.salvage import HitOutcome, Loadout

PLAY_TOP = 60  # keep the ship below the HUD strip
SLUG_SPEED = 520.0


class Player(pygame.sprite.Sprite):
    def __init__(self) -> None:
        super().__init__()
        self.frames = assets.load_frames("player")
        self.image = self.frames[0]
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 24))
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.radius = 16  # circle collision keeps hits fair on a 48x64 sprite
        self.health = PLAYER_MAX_HEALTH
        self.loadout = Loadout()
        self.dead = False
        self.invuln_timer = 0.0
        self.fire_cooldown = 0.0
        self.anim_time = 0.0
        self.tilt = 0.0
        self.last_outcome: HitOutcome | None = None

    @property
    def alive_in_world(self) -> bool:
        return not self.dead

    @property
    def invulnerable(self) -> bool:
        return self.invuln_timer > 0

    def update(self, dt: float, move: tuple[float, float] = (0.0, 0.0)) -> None:
        self.anim_time += dt
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        if self.dead:
            return
        mx, my = move
        length = math.hypot(mx, my)
        if length > 1:
            mx, my = mx / length, my / length
        speed = PLAYER_SPEED * self.loadout.speed_multiplier()
        self.x += mx * speed * dt
        self.y += my * speed * dt
        half_w, half_h = self.rect.width / 2, self.rect.height / 2
        self.x = min(WIDTH - half_w, max(half_w, self.x))
        self.y = min(HEIGHT - half_h, max(PLAY_TOP + half_h, self.y))
        self.rect.center = (round(self.x), round(self.y))
        self.tilt += (mx - self.tilt) * min(1.0, 10 * dt)
        frame = int(self.anim_time * 12) % 2 + 1 if length > 0.1 else int(self.anim_time * 6) % 3
        self.image = self.frames[frame]

    def try_fire(self) -> list[Bullet]:
        """Main gun plus one slug round per slug cannon, if the gun is ready."""
        if self.fire_cooldown > 0 or self.dead:
            return []
        self.fire_cooldown = WEAPON_COOLDOWN
        bullets: list[Bullet] = [PlayerBullet((self.x, self.rect.top + 6), (0, -BULLET_SPEED), PLAYER_BULLET_DAMAGE)]
        for slot, part in self.loadout.parts():
            if part.kind == "slug":
                side = -1 if slot.endswith("_l") else 1
                damage = 3 if not part.rare else 5
                bullets.append(SlugBullet((self.x + side * 14, self.rect.top), (0, -SLUG_SPEED), damage))
        return bullets

    def take_damage(self, amount: int, rng: random.Random) -> str:
        """Return 'ignored', 'armour', 'knocked', 'hit' or 'died'."""
        if self.dead or self.invuln_timer > 0:
            return "ignored"
        outcome = self.loadout.absorb_hit(rng)
        self.last_outcome = outcome
        if outcome.kind != "hull":
            self.invuln_timer = PLAYER_HIT_INVULN_TIME
            return outcome.kind
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.dead = True
            return "died"
        self.invuln_timer = PLAYER_HIT_INVULN_TIME
        return "hit"

    def heal(self, amount: int) -> None:
        self.health = min(PLAYER_MAX_HEALTH, self.health + amount)

    def draw(self, surface: pygame.Surface) -> None:
        if self.dead:
            return
        if self.invuln_timer > 0 and int(self.anim_time * 16) % 2 == 0:
            return
        surface.blit(self.image, self.rect)
        draw_loadout(surface, self.loadout, self.rect.center)


PLAYER_SPAWN_INVULN = PLAYER_INVULN_TIME
