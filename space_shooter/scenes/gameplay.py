"""The main game loop scene: encounters, combat, salvage and feedback."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter.config import (
    BOSS_EVERY,
    DIFFICULTIES,
    HEIGHT,
    LOW_HEALTH_THRESHOLD,
    PLAYER_COLLISION_DAMAGE,
    SHAKE_BOSS_DEATH,
    SHAKE_EXPLOSION,
    SHAKE_HIT,
    WAVE_INTERMISSION,
    WAVE_START_DELAY,
    WIDTH,
)
from space_shooter.effects import Explosion, Flash, FloatingText, Particle, ScreenShake, burst
from space_shooter.entities.bullets import EnemyBullet, SlugBullet
from space_shooter.entities.enemies import ENEMY_CLASSES, Enemy
from space_shooter.entities.parts import Drop, PartRig
from space_shooter.entities.player import Player
from space_shooter.hud import draw_hud
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL
from space_shooter.salvage import DROP_BASE, PART_TYPES, PATCH_HULL, part_from_code, roll_drop
from space_shooter.scenes.base import Scene
from space_shooter.ui import draw_text
from space_shooter.waves import Spawn, build_wave, is_boss_wave

SPAWN_MARGIN = 48
GAME_OVER_DELAY = 1.6
KNOCK_LIFETIME = 6.0
KNOCK_PICKUP_DELAY = 0.8
TRACTOR_RANGE = 180.0
TRACTOR_SPEED = 220.0


class WaveDirector:
    """Feeds spawn plans into the scene one wave at a time."""

    def __init__(self, spawn_rate: float, rng: random.Random) -> None:
        self.spawn_rate = spawn_rate
        self.rng = rng
        self.wave = 0
        self.plan: list[Spawn] = []
        self.index = 0
        self.elapsed = 0.0
        self.state = "intermission"  # intermission -> announce -> spawning -> clearing
        self.timer = WAVE_START_DELAY
        self.banner_time = 0.0

    @property
    def boss_wave(self) -> bool:
        return is_boss_wave(self.wave)

    def start_next(self) -> None:
        self.wave += 1
        self.plan = build_wave(self.wave, self.spawn_rate, self.rng)
        self.index = 0
        self.elapsed = 0.0
        self.state = "announce"
        self.banner_time = 1.6

    def update(self, dt: float, enemies_alive: int) -> list[Spawn]:
        """Advance; return the spawns due this frame."""
        due: list[Spawn] = []
        if self.state == "intermission":
            self.timer -= dt
            if self.timer <= 0:
                self.start_next()
        elif self.state == "announce":
            self.banner_time -= dt
            if self.banner_time <= 0:
                self.state = "spawning"
        elif self.state == "spawning":
            self.elapsed += dt
            while self.index < len(self.plan) and self.plan[self.index].at <= self.elapsed:
                due.append(self.plan[self.index])
                self.index += 1
            if self.index >= len(self.plan):
                self.state = "clearing"
        elif self.state == "clearing":
            if enemies_alive == 0:
                self.state = "intermission"
                self.timer = WAVE_INTERMISSION
        return due


class GameplayScene(Scene):
    def __init__(self, game, seed: int | None = None) -> None:
        super().__init__(game)
        self.rng = random.Random(seed)
        self.difficulty = DIFFICULTIES[game.settings.difficulty]
        self.player = Player()
        self.rig = PartRig()
        self.enemies: pygame.sprite.Group = pygame.sprite.Group()
        self.player_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.enemy_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.drops: pygame.sprite.Group = pygame.sprite.Group()
        self.effects: pygame.sprite.Group = pygame.sprite.Group()
        self.particles: pygame.sprite.Group = pygame.sprite.Group()
        self.texts: pygame.sprite.Group = pygame.sprite.Group()
        self.director = WaveDirector(self.difficulty.spawn_rate, self.rng)
        self.shake = ScreenShake(game.settings.screen_shake)
        self.flash = Flash()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.score = 0  # salvage value, shown only at loop end
        self.time = 0.0
        self.boss: Enemy | None = None
        self.game_over_timer: float | None = None
        self.kills = 0
        self.exhaust_timer = 0.0

    # -- world interface used by enemies ------------------------------------
    @property
    def player_pos(self) -> tuple[float, float]:
        return (self.player.x, self.player.y)

    def fire_enemy_bullet(self, pos, vel, big: bool = False) -> None:
        self.enemy_bullets.add(EnemyBullet(pos, vel, big=big))
        self.game.audio.play("enemy_shoot")

    # -- lifecycle -----------------------------------------------------------
    def on_enter(self) -> None:
        self.game.starfield.boost = 1.0

    def on_exit(self) -> None:
        self.game.audio.stop_all_loops()

    def handle_action(self, action: str) -> None:
        if self.game_over_timer is not None:
            return
        if action in ("pause", "back"):
            from space_shooter.scenes.pause import PauseScene

            self.game.scenes.push(PauseScene(self.game))

    # -- update --------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.shake.enabled = self.game.settings.screen_shake
        self.game.starfield.update(dt)
        self.shake.update(dt)
        self.flash.update(dt)
        self.effects.update(dt)
        self.particles.update(dt)
        self.texts.update(dt)
        self.drops.update(dt)

        if self.game_over_timer is not None:
            self.game_over_timer -= dt
            self.enemies.update(dt, self)
            self.enemy_bullets.update(dt)
            if self.game_over_timer <= 0:
                from space_shooter.scenes.gameover import GameOverScene

                self.game.scenes.push(GameOverScene(self.game, self.score, self.director.wave))
                self.game_over_timer = float("inf")
            return

        self.player.update(dt, self.game.move_vector())
        if self.game.fire_held():
            bullets = self.player.try_fire()
            if bullets:
                self.player_bullets.add(bullets)
                self.game.audio.play("shoot")
        if self.player.alive_in_world:
            self.player_bullets.add(self.rig.update(dt, self.player.loadout, self.player_pos, self.enemies, 1.0))
            self._tractor(dt)
        self._exhaust(dt)

        for spawn in self.director.update(dt, len(self.enemies)):
            self._spawn(spawn)
        self.game.starfield.boost = 3.0 if self.director.state in ("intermission", "announce") else 1.0
        if self.director.state == "announce" and self.director.boss_wave:
            self.game.audio.loop("boss_warning")
        else:
            self.game.audio.stop("boss_warning")

        self.enemies.update(dt, self)
        self.player_bullets.update(dt)
        self.enemy_bullets.update(dt)
        if self.boss is not None and not self.boss.alive():
            self.boss = None

        self._collisions()

        if self.player.alive_in_world and self.player.health <= LOW_HEALTH_THRESHOLD:
            self.game.audio.loop("low_health")
        else:
            self.game.audio.stop("low_health")

        if self.player.dead and self.game_over_timer is None:
            self.game_over_timer = GAME_OVER_DELAY
            self.game.audio.stop_all_loops()

    def _exhaust(self, dt: float) -> None:
        if not self.player.alive_in_world:
            return
        self.exhaust_timer += dt
        while self.exhaust_timer > 0.03:
            self.exhaust_timer -= 0.03
            x = self.player.x + self.rng.uniform(-5, 5)
            colour = self.rng.choice([STEEL, ASH, EMBER])
            self.particles.add(Particle((x, self.player.rect.bottom - 6), (0, 140), colour, 0.25, 3))

    def _tractor(self, dt: float) -> None:
        strength = self.player.loadout.effect("tractor")
        if strength <= 0:
            return
        px, py = self.player_pos
        for drop in self.drops:
            dx, dy = px - drop.x, py - drop.y
            dist = math.hypot(dx, dy)
            if 0 < dist <= TRACTOR_RANGE or drop.lifetime is not None:
                step = min(dist, TRACTOR_SPEED * strength * dt)
                drop.x += dx / (dist or 1) * step
                drop.y += dy / (dist or 1) * step

    def _spawn(self, spawn: Spawn) -> None:
        x = SPAWN_MARGIN + spawn.x_frac * (WIDTH - 2 * SPAWN_MARGIN)
        wave_speed = 1.0 + min(0.6, 0.03 * self.director.wave)
        kwargs = dict(
            hp_mult=self.difficulty.enemy_hp * (1 + 0.05 * (self.director.wave // 3)),
            speed_mult=self.difficulty.enemy_speed * wave_speed,
            fire_mult=self.difficulty.enemy_fire_rate,
        )
        if spawn.kind == "boss":
            enemy = ENEMY_CLASSES["boss"](x, wave=self.director.wave, **kwargs)
            self.boss = enemy
        else:
            enemy = ENEMY_CLASSES[spawn.kind](x, **kwargs)
        self.enemies.add(enemy)

    # -- combat --------------------------------------------------------------
    def _collisions(self) -> None:
        hits = pygame.sprite.groupcollide(self.enemies, self.player_bullets, False, False)
        for enemy, bullets in hits.items():
            damage = 0
            for b in bullets:
                if isinstance(b, SlugBullet):
                    if id(enemy) in b.hit_ids:
                        continue
                    b.hit_ids.add(id(enemy))
                    if len(b.hit_ids) > b.pierce:
                        b.kill()
                else:
                    b.kill()
                damage += b.damage
                self.particles.add(Particle(b.rect.midtop, (0, -60), STEEL, 0.15, 3))
            if damage and enemy.hit(damage):
                self._kill_enemy(enemy)

        if not self.player.alive_in_world:
            return

        for enemy in pygame.sprite.spritecollide(self.player, self.enemies, False, pygame.sprite.collide_circle):
            result = self.player.take_damage(PLAYER_COLLISION_DAMAGE, self.rng)
            if result == "ignored":
                continue
            if not enemy.is_boss:
                self._kill_enemy(enemy, award=False)
            self._player_damaged(result)

        for bullet in pygame.sprite.spritecollide(self.player, self.enemy_bullets, False, pygame.sprite.collide_circle):
            result = self.player.take_damage(bullet.damage, self.rng)
            if result == "ignored":
                continue
            bullet.kill()
            self._player_damaged(result)

        for drop in pygame.sprite.spritecollide(self.player, self.drops, False, pygame.sprite.collide_circle):
            if drop.collectable:
                drop.kill()
                self._collect(drop)

    def _player_damaged(self, result: str) -> None:
        center = self.player.rect.center
        if result == "armour":
            self.game.audio.play("player_hit")
            burst(self.particles, center, 6, (STEEL, ASH), 160, 0.3, 3, self.rng)
        elif result == "knocked":
            outcome = self.player.last_outcome
            self.game.audio.play("player_hit")
            if outcome is not None and outcome.part is not None:
                side = -1 if (outcome.slot or "").endswith("_l") else 1
                vel = (side * self.rng.uniform(80, 140), self.rng.uniform(-40, 20))
                self.drops.add(
                    Drop(outcome.part.code, center, vel=vel, lifetime=KNOCK_LIFETIME, pickup_delay=KNOCK_PICKUP_DELAY)
                )
            self.shake.add(SHAKE_HIT * 0.6)
        elif result == "hit":
            self.game.audio.play("player_hit")
            self.shake.add(SHAKE_HIT)
            self.flash.trigger(RUST, 70)
            burst(self.particles, center, 10, (EMBER, RUST, ASH), 200, 0.4, 3, self.rng)
        elif result == "died":
            self.game.audio.play("player_death")
            self.shake.add(SHAKE_HIT * 2)
            self.flash.trigger(BONE, 140)
            self.effects.add(Explosion(center, scale=6, frame_time=0.08))
            burst(self.particles, center, 40, (EMBER, RUST, ASH), 320, 0.9, 4, self.rng)

    def _kill_enemy(self, enemy: Enemy, award: bool = True) -> None:
        enemy.kill()
        self.kills += 1
        center = enemy.rect.center
        if enemy.is_boss:
            self.boss = None
            self.effects.add(Explosion(center, scale=14, frame_time=0.1))
            burst(self.particles, center, 70, (EMBER, RUST, ASH), 420, 1.4, 6, self.rng)
            self.shake.add(SHAKE_BOSS_DEATH)
            self.flash.trigger(BONE, 200)
            self.game.audio.play("boss_death")
            self._drop(center, force=True, rare=True)
        else:
            self.effects.add(Explosion(center))
            burst(self.particles, center, 10, (EMBER, RUST, ASH), rng=self.rng)
            self.shake.add(SHAKE_EXPLOSION)
            self.game.audio.play("explosion")
            self._drop(center)
        if award:
            self.score += int(enemy.score * self.difficulty.score_mult)

    def _drop(self, center, force: bool = False, rare: bool = False) -> None:
        loadout = self.player.loadout
        chance = 1.0 if force else loadout.drop_chance(DROP_BASE)
        code = roll_drop(self.rng, chance, loadout.patch_share())
        if code is None:
            return
        if force and code == "patch":
            code = self.rng.choice(list(PART_TYPES))
        if rare and code != "patch":
            code += "*"
        self.drops.add(Drop(code, center))

    def _collect(self, drop: Drop) -> None:
        p = self.player
        self.game.audio.play("powerup")
        if drop.code == "patch":
            p.heal(PATCH_HULL)
            self.texts.add(FloatingText("HULL PATCHED", (p.x, p.rect.top - 10), BONE, 20, 1.0))
            return
        part = part_from_code(drop.code)
        if part is None:
            return
        contact = (drop.x - p.x, drop.y - p.y)
        _slot, ejected = p.loadout.attach(part, contact)
        if ejected is not None:
            vel = (self.rng.uniform(-120, 120), 40)
            self.drops.add(
                Drop(ejected.code, p.rect.center, vel=vel, lifetime=KNOCK_LIFETIME, pickup_delay=KNOCK_PICKUP_DELAY)
            )
        label = PART_TYPES[part.kind].label + (" (SCARRED)" if part.rare else "")
        self.texts.add(FloatingText(label, (p.x, p.rect.top - 10), STEEL, 20, 1.0))

    # -- drawing -------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        canvas = self.canvas
        self.game.starfield.draw(canvas)
        self.drops.draw(canvas)
        self.enemies.draw(canvas)
        self.player_bullets.draw(canvas)
        self.enemy_bullets.draw(canvas)
        self.particles.draw(canvas)
        self.player.draw(canvas)
        self.effects.draw(canvas)
        self.texts.draw(canvas)
        self._draw_banners(canvas)
        self.flash.draw(canvas)
        draw_hud(canvas, self)
        surface.fill((0, 0, 0))
        surface.blit(canvas, self.shake.offset)

    def _draw_banners(self, canvas: pygame.Surface) -> None:
        d = self.director
        if d.state == "announce":
            if d.boss_wave:
                if int(self.time * 4) % 2:
                    draw_text(canvas, "WARNING", 72, (WIDTH // 2, HEIGHT // 2 - 30), EMBER)
                draw_text(canvas, "SOMETHING LARGE IS WAKING", 32, (WIDTH // 2, HEIGHT // 2 + 30), BONE)
            else:
                draw_text(canvas, f"WAVE {d.wave}", 72, (WIDTH // 2, HEIGHT // 2 - 20), BONE)
                if (d.wave + 1) % BOSS_EVERY == 0:
                    draw_text(canvas, "SOMETHING IS COMING", 28, (WIDTH // 2, HEIGHT // 2 + 40), EMBER)
