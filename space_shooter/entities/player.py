"""The player's ship."""

from __future__ import annotations

import math

import pygame

from space_shooter import assets
from space_shooter.config import (
    BULLET_SPEED,
    CYAN,
    HEIGHT,
    PLAYER_BULLET_DAMAGE,
    PLAYER_HIT_INVULN_TIME,
    PLAYER_INVULN_TIME,
    PLAYER_MAX_BOMBS,
    PLAYER_MAX_HEALTH,
    PLAYER_RESPAWN_DELAY,
    PLAYER_SPEED,
    PLAYER_START_BOMBS,
    PLAYER_START_LIVES,
    SHIELD_DURATION,
    WEAPON_COOLDOWN,
    WEAPON_MAX_LEVEL,
    WIDTH,
)
from space_shooter.entities.bullets import PlayerBullet

PLAY_TOP = 60  # keep the ship below the HUD strip


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
        self.lives = PLAYER_START_LIVES
        self.bombs = PLAYER_START_BOMBS
        self.weapon_level = 1
        self.shield_timer = 0.0
        self.invuln_timer = PLAYER_INVULN_TIME
        self.respawn_timer = 0.0  # >0 while dead and waiting to respawn
        self.fire_cooldown = 0.0
        self.anim_time = 0.0
        self.tilt = 0.0  # -1..1 for a banking effect

    # -- state ---------------------------------------------------------------
    @property
    def alive_in_world(self) -> bool:
        return self.respawn_timer <= 0 and self.lives > 0

    @property
    def shielded(self) -> bool:
        return self.shield_timer > 0

    @property
    def invulnerable(self) -> bool:
        return self.invuln_timer > 0 or self.shielded

    @property
    def game_over(self) -> bool:
        return self.lives <= 0 and self.respawn_timer <= 0

    # -- updates -------------------------------------------------------------
    def update(self, dt: float, move: tuple[float, float] = (0.0, 0.0)) -> None:
        self.anim_time += dt
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)

        if self.respawn_timer > 0:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0 and self.lives > 0:
                self._respawn()
            return

        mx, my = move
        length = math.hypot(mx, my)
        if length > 1:
            mx, my = mx / length, my / length
        self.x += mx * PLAYER_SPEED * dt
        self.y += my * PLAYER_SPEED * dt
        half_w, half_h = self.rect.width / 2, self.rect.height / 2
        self.x = min(WIDTH - half_w, max(half_w, self.x))
        self.y = min(HEIGHT - half_h, max(PLAY_TOP + half_h, self.y))
        self.rect.center = (round(self.x), round(self.y))
        self.tilt += (mx - self.tilt) * min(1.0, 10 * dt)

        frame = int(self.anim_time * 12) % 2 + 1 if length > 0.1 else int(self.anim_time * 6) % 3
        self.image = self.frames[frame]

    def try_fire(self) -> list[PlayerBullet]:
        """Return new bullets if the weapon is ready, else an empty list."""
        if self.fire_cooldown > 0 or not self.alive_in_world:
            return []
        self.fire_cooldown = WEAPON_COOLDOWN[self.weapon_level]
        return self._make_bullets()

    def _make_bullets(self) -> list[PlayerBullet]:
        cx, top = self.x, self.rect.top + 6
        dmg = PLAYER_BULLET_DAMAGE
        level = self.weapon_level
        if level == 1:
            return [PlayerBullet((cx, top), (0, -BULLET_SPEED), dmg)]
        if level == 2:
            return [
                PlayerBullet((cx - 10, top), (0, -BULLET_SPEED), dmg),
                PlayerBullet((cx + 10, top), (0, -BULLET_SPEED), dmg),
            ]
        spread = [-0.22, 0.0, 0.22] if level == 3 else [-0.3, -0.1, 0.1, 0.3]
        bullets = []
        for angle in spread:
            vx = math.sin(angle) * BULLET_SPEED
            vy = -math.cos(angle) * BULLET_SPEED
            bullets.append(PlayerBullet((cx + angle * 40, top), (vx, vy), dmg))
        return bullets

    # -- damage & pickups ----------------------------------------------------
    def take_damage(self, amount: int) -> str:
        """Apply damage; return 'ignored', 'shielded', 'hit' or 'died'."""
        if not self.alive_in_world:
            return "ignored"
        if self.shielded:
            return "shielded"
        if self.invuln_timer > 0:
            return "ignored"
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.lives -= 1
            self.respawn_timer = PLAYER_RESPAWN_DELAY
            self.weapon_level = max(1, self.weapon_level - 1)
            return "died"
        self.invuln_timer = PLAYER_HIT_INVULN_TIME
        return "hit"

    def _respawn(self) -> None:
        self.health = PLAYER_MAX_HEALTH
        self.x, self.y = WIDTH / 2, HEIGHT - 24 - self.rect.height / 2
        self.rect.center = (round(self.x), round(self.y))
        self.invuln_timer = PLAYER_INVULN_TIME

    def heal(self, amount: int) -> None:
        self.health = min(PLAYER_MAX_HEALTH, self.health + amount)

    def upgrade_weapon(self) -> bool:
        """Raise the weapon level; return False if already maxed."""
        if self.weapon_level >= WEAPON_MAX_LEVEL:
            return False
        self.weapon_level += 1
        return True

    def add_bomb(self) -> bool:
        if self.bombs >= PLAYER_MAX_BOMBS:
            return False
        self.bombs += 1
        return True

    def use_bomb(self) -> bool:
        if self.bombs <= 0 or not self.alive_in_world:
            return False
        self.bombs -= 1
        return True

    def activate_shield(self) -> None:
        self.shield_timer = SHIELD_DURATION

    # -- drawing -------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if not self.alive_in_world:
            return
        # blink while invulnerable (but not while shielded)
        if self.invuln_timer > 0 and not self.shielded and int(self.anim_time * 16) % 2 == 0:
            return
        surface.blit(self.image, self.rect)
        if self.shielded:
            pulse = 2 + int(2 * abs(math.sin(self.anim_time * 6)))
            radius = self.rect.width // 2 + 10 + pulse
            fade = min(1.0, self.shield_timer / 1.5)  # flicker out at the end
            if fade >= 1.0 or int(self.anim_time * 10) % 2 == 0:
                pygame.draw.circle(surface, CYAN, self.rect.center, radius, 2)
