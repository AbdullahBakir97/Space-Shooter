"""The main game loop scene: encounters, combat, salvage and feedback."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter.config import (
    DIFFICULTIES,
    HEIGHT,
    LOW_HEALTH_THRESHOLD,
    PLAYER_COLLISION_DAMAGE,
    SHAKE_BOSS_DEATH,
    SHAKE_EXPLOSION,
    SHAKE_HIT,
    WIDTH,
)
from space_shooter.effects import Explosion, Flash, FloatingText, Particle, ScreenShake, burst
from space_shooter.encounters import WARDEN_INDEX, EncounterDirector, Spawn, loop_hull_multiplier
from space_shooter.entities.bullets import EnemyBullet, SlugBullet
from space_shooter.entities.enemies import ENEMY_CLASSES, Enemy
from space_shooter.entities.hazards import AshCloud, Debris, Hulk
from space_shooter.entities.parts import Drop, PartRig
from space_shooter.entities.player import Player
from space_shooter.hud import draw_hud
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL
from space_shooter.salvage import DROP_BASE, PART_TYPES, PATCH_HULL, SLOT_OFFSETS, SLOTS, part_from_code, roll_drop
from space_shooter.scenes.base import Scene
from space_shooter.ui import draw_text

SPAWN_MARGIN = 48
GAME_OVER_DELAY = 1.6
KNOCK_LIFETIME = 6.0
KNOCK_PICKUP_DELAY = 0.8
TRACTOR_RANGE = 180.0
TRACTOR_SPEED = 220.0
BANNER_TIME = 2.5
BLACKOUT_TIME = 4.0
FLARE_WARNING = 1.5
FLARE_TIME = 2.0
FLARE_PLAYER_DAMAGE = 30
FLARE_ENEMY_HITS = 2
ASH_PERIOD = 5.0
DEBRIS_PERIOD = 1.2


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
        self.hazards: pygame.sprite.Group = pygame.sprite.Group()
        self.effects: pygame.sprite.Group = pygame.sprite.Group()
        self.particles: pygame.sprite.Group = pygame.sprite.Group()
        self.texts: pygame.sprite.Group = pygame.sprite.Group()
        self.director = EncounterDirector(self.rng)
        self.loop = game.save.loop
        self.hull_mult = loop_hull_multiplier(self.loop)
        self.banner_text: str | None = None
        self.banner_timer = 0.0
        self.blackout_timer = 0.0
        self.flare_warning = 0.0
        self.flare_timer = 0.0
        self.hazard_timer = 0.0
        self.first_drop_pending = False
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

    def aim_point(self) -> tuple[float, float]:
        """Where enemies aim: the first armour plate if one is bolted on, else the hull."""
        for slot in SLOTS:
            part = self.player.loadout.slots[slot]
            if part is not None and part.kind == "armour":
                ox, oy = SLOT_OFFSETS[slot]
                return (self.player.x + ox, self.player.y + oy)
        return self.player_pos

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
        self.hazards.update(dt, self)
        self.banner_timer = max(0.0, self.banner_timer - dt)
        self.blackout_timer = max(0.0, self.blackout_timer - dt)

        if self.game_over_timer is not None:
            self.game_over_timer -= dt
            self.enemies.update(dt, self)
            self.enemy_bullets.update(dt)
            if self.game_over_timer <= 0:
                from space_shooter.scenes.gameover import GameOverScene

                self.game.scenes.push(GameOverScene(self.game, self.score, self.director.index + 1))
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
        for event, value in self.director.drain_events():
            self._on_director_event(event, value)
        self.game.starfield.boost = 2.0 if self.director.state == "drift" else 1.0
        self._update_hazards(dt)
        self._update_flare(dt)

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

    # -- encounters ----------------------------------------------------------
    def _on_director_event(self, event: str, value) -> None:
        if event == "encounter_start":
            enc = self.director.encounter
            self.banner_text = enc.name
            self.banner_timer = BANNER_TIME
            self.hazard_timer = 0.0
            if "hulks" in enc.hazards:
                for i, (fx, y) in enumerate(((0.2, 170), (0.45, 260), (0.7, 190), (0.85, 330))):
                    self.hazards.add(Hulk((fx * WIDTH, y), seed=i))
        elif event == "moment":
            self.trigger_moment(value)
        elif event == "retreat":
            for enemy in self.enemies:
                enemy.retreat()
        elif event == "encounter_end":
            for hazard in list(self.hazards):
                if not isinstance(hazard, Hulk):
                    hazard.kill()
            self.blackout_timer = 0.0

    def trigger_moment(self, name: str) -> None:
        """Play an encounter's named moment (also the entry point for tests)."""
        if name == "first_drop":
            self.first_drop_pending = True
        elif name == "blackout":
            self.blackout_timer = BLACKOUT_TIME
        elif name == "hulk_breach":
            hulks = [h for h in self.hazards if isinstance(h, Hulk)]
            if hulks:
                hulk = min(hulks, key=lambda h: (h.x - self.player.x) ** 2 + (h.y - self.player.y) ** 2)
                self._break_hulk(hulk, rare=True)
        elif name == "flare":
            self.flare_warning = FLARE_WARNING

    def _update_hazards(self, dt: float) -> None:
        if self.director.state not in ("active", "clearing"):
            return
        hazards = self.director.encounter.hazards
        self.hazard_timer += dt
        if "ash" in hazards and self.hazard_timer >= ASH_PERIOD:
            self.hazard_timer -= ASH_PERIOD
            self.hazards.add(AshCloud((self.rng.uniform(80, WIDTH - 80), -70), seed=self.rng.randrange(4)))
        if "debris" in hazards and self.hazard_timer >= DEBRIS_PERIOD:
            self.hazard_timer -= DEBRIS_PERIOD
            vel = (self.rng.uniform(-30, 30), self.rng.uniform(160, 260))
            self.hazards.add(Debris((self.rng.uniform(20, WIDTH - 20), -20), vel, seed=self.rng.randrange(6)))

    def _shadowed(self, x: float, y: float) -> bool:
        return any(isinstance(h, Hulk) and h.shadows(x, y) for h in self.hazards)

    def _update_flare(self, dt: float) -> None:
        if self.flare_warning > 0:
            self.flare_warning -= dt
            if self.flare_warning <= 0:
                self.flare_warning = 0.0
                self.flare_timer = FLARE_TIME
                self.flash.trigger(EMBER, 160)
                self.shake.add(SHAKE_HIT)
                if self.player.alive_in_world and not self._shadowed(self.player.x, self.player.y):
                    self.player.invuln_timer = 0.0
                    self._player_damaged(self.player.take_damage(FLARE_PLAYER_DAMAGE, self.rng))
                for enemy in list(self.enemies):
                    if not self._shadowed(enemy.x, enemy.y) and enemy.hit(FLARE_ENEMY_HITS):
                        self._kill_enemy(enemy)
        elif self.flare_timer > 0:
            self.flare_timer = max(0.0, self.flare_timer - dt)

    def _spawn(self, spawn: Spawn) -> None:
        x = SPAWN_MARGIN + spawn.x_frac * (WIDTH - 2 * SPAWN_MARGIN)
        kwargs = dict(
            hp_mult=self.difficulty.enemy_hp * self.hull_mult,
            speed_mult=self.difficulty.enemy_speed,
            fire_mult=self.difficulty.enemy_fire_rate,
        )
        if spawn.kind == "warden":  # placeholder until the Warden itself lands
            enemy = ENEMY_CLASSES["boss"](x, wave=5, **kwargs)
            self.boss = enemy
        else:
            enemy = ENEMY_CLASSES[spawn.kind](x, **kwargs)
        self.enemies.add(enemy)

    def _break_hulk(self, hulk: Hulk, rare: bool) -> None:
        hulk.kill()
        self.effects.add(Explosion(hulk.rect.center, scale=6))
        burst(self.particles, hulk.rect.center, 14, (RUST, ASH, EMBER), 200, 0.8, 4, self.rng)
        self.shake.add(SHAKE_EXPLOSION)
        self.game.audio.play("explosion")
        code = self.rng.choice(list(PART_TYPES)) + ("*" if rare else "")
        self.drops.add(Drop(code, hulk.rect.center))

    # -- combat --------------------------------------------------------------
    def _collisions(self) -> None:
        for hazard, bullets in pygame.sprite.groupcollide(self.hazards, self.player_bullets, False, True).items():
            if isinstance(hazard, Hulk):
                if hazard.hit(sum(b.damage for b in bullets)):
                    self._break_hulk(hazard, rare=hazard.rare_drop)
            elif isinstance(hazard, Debris):
                hazard.kill()
                burst(self.particles, hazard.rect.center, 5, (RUST, ASH), 120, 0.3, 3, self.rng)
        blockers = [h for h in self.hazards if h.blocks_bullets]
        if blockers:
            pygame.sprite.groupcollide(self.enemy_bullets, pygame.sprite.Group(blockers), True, False)

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

        for hazard in pygame.sprite.spritecollide(self.player, self.hazards, False):
            if isinstance(hazard, Debris) and pygame.sprite.collide_circle(self.player, hazard):
                hazard.kill()
                self._player_damaged(self.player.take_damage(hazard.hurts_player, self.rng))

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
        if self.first_drop_pending and self.director.index == 0:
            self.first_drop_pending = False
            force = True
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
        for hazard in self.hazards:
            if isinstance(hazard, Hulk):
                canvas.blit(hazard.image, hazard.rect)
        self.drops.draw(canvas)
        self.enemies.draw(canvas)
        if self.blackout_timer > 0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.set_alpha(217)  # 85 % dark; bullets and ember drawn after stay visible
            canvas.blit(veil, (0, 0))
        self.player_bullets.draw(canvas)
        self.enemy_bullets.draw(canvas)
        for hazard in self.hazards:
            if not isinstance(hazard, Hulk):
                canvas.blit(hazard.image, hazard.rect)
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
        if self.banner_timer > 0 and self.banner_text:
            fade = min(1.0, self.banner_timer / 0.8)
            colour = tuple(int(c * fade) for c in BONE)
            draw_text(canvas, self.banner_text, 54, (WIDTH // 2, HEIGHT // 2 - 40), colour)
            if self.director.index == WARDEN_INDEX:
                draw_text(canvas, "SOMETHING LARGE IS WAKING", 26, (WIDTH // 2, HEIGHT // 2 + 10), EMBER)
        if self.flare_warning > 0 and int(self.time * 6) % 2:
            draw_text(canvas, "STAR FLARE - GET BEHIND A HULK", 30, (WIDTH // 2, 110), EMBER)
