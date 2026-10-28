"""The main game loop scene: waves, combat, scoring and feedback."""

from __future__ import annotations

import random

import pygame

from space_shooter.combo import Combo
from space_shooter.config import (
    BOSS_EVERY,
    CYAN,
    DIFFICULTIES,
    GREEN,
    HEIGHT,
    LOW_HEALTH_THRESHOLD,
    MAGENTA,
    ORANGE,
    PLAYER_COLLISION_DAMAGE,
    POWERUP_DROP_CHANCE,
    POWERUP_HEALTH_VALUE,
    POWERUP_SCORE_VALUE,
    RED,
    SHAKE_BOMB,
    SHAKE_BOSS_DEATH,
    SHAKE_EXPLOSION,
    SHAKE_HIT,
    WAVE_INTERMISSION,
    WAVE_START_DELAY,
    WHITE,
    WIDTH,
    YELLOW,
)
from space_shooter.effects import Explosion, Flash, FloatingText, Particle, ScreenShake, burst
from space_shooter.entities.bullets import EnemyBullet
from space_shooter.entities.enemies import ENEMY_CLASSES, Enemy
from space_shooter.entities.player import Player
from space_shooter.entities.powerups import PowerUp, random_kind
from space_shooter.hud import draw_hud
from space_shooter.scenes.base import Scene
from space_shooter.ui import draw_text
from space_shooter.waves import Spawn, build_wave, is_boss_wave

SPAWN_MARGIN = 48
GAME_OVER_DELAY = 1.6


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
        self.enemies: pygame.sprite.Group = pygame.sprite.Group()
        self.player_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.enemy_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.powerups: pygame.sprite.Group = pygame.sprite.Group()
        self.effects: pygame.sprite.Group = pygame.sprite.Group()
        self.particles: pygame.sprite.Group = pygame.sprite.Group()
        self.texts: pygame.sprite.Group = pygame.sprite.Group()
        self.director = WaveDirector(self.difficulty.spawn_rate, self.rng)
        self.combo = Combo()
        self.shake = ScreenShake(game.settings.screen_shake)
        self.flash = Flash()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.score = 0
        self.best = game.highscores.best
        self.time = 0.0
        self.boss: Enemy | None = None
        self.game_over_timer: float | None = None
        self.kills = 0
        self.exhaust_timer = 0.0
        self.boss_warning_time = 0.0

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
        elif action == "bomb":
            self.use_bomb()

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

        if self.game_over_timer is not None:
            self.game_over_timer -= dt
            self.enemies.update(dt, self)
            self.enemy_bullets.update(dt)
            if self.game_over_timer <= 0:
                from space_shooter.scenes.gameover import GameOverScene

                self.game.scenes.push(GameOverScene(self.game, self.score, self.director.wave))
                self.game_over_timer = float("inf")
            return

        # player
        move = self.game.move_vector()
        self.player.update(dt, move)
        if self.game.fire_held():
            bullets = self.player.try_fire()
            if bullets:
                self.player_bullets.add(bullets)
                self.game.audio.play("shoot")
        self._exhaust(dt)

        # waves
        for spawn in self.director.update(dt, len(self.enemies)):
            self._spawn(spawn)
        self.game.starfield.boost = 3.0 if self.director.state in ("intermission", "announce") else 1.0
        if self.director.state == "announce" and self.director.boss_wave:
            self.game.audio.loop("boss_warning")
        else:
            self.game.audio.stop("boss_warning")

        # entities
        self.enemies.update(dt, self)
        self.player_bullets.update(dt)
        self.enemy_bullets.update(dt)
        self.powerups.update(dt)
        if self.boss is not None and not self.boss.alive():
            self.boss = None

        self._collisions()
        self.combo.update(dt)

        # low health alarm
        if self.player.alive_in_world and self.player.health <= LOW_HEALTH_THRESHOLD:
            self.game.audio.loop("low_health")
        else:
            self.game.audio.stop("low_health")

        if self.player.game_over and self.game_over_timer is None:
            self.game_over_timer = GAME_OVER_DELAY
            self.game.audio.stop_all_loops()

    def _exhaust(self, dt: float) -> None:
        if not self.player.alive_in_world:
            return
        self.exhaust_timer += dt
        while self.exhaust_timer > 0.02:
            self.exhaust_timer -= 0.02
            x = self.player.x + self.rng.uniform(-5, 5)
            y = self.player.rect.bottom - 6
            colour = self.rng.choice([CYAN, WHITE, (120, 160, 255)])
            self.particles.add(Particle((x, y), (self.rng.uniform(-20, 20), 160), colour, 0.25, 3))

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
        # player bullets vs enemies
        hits = pygame.sprite.groupcollide(self.enemies, self.player_bullets, False, True)
        for enemy, bullets in hits.items():
            damage = sum(b.damage for b in bullets)
            for b in bullets:
                self.particles.add(Particle(b.rect.midtop, (0, -60), CYAN, 0.15, 3))
            if enemy.hit(damage):
                self._kill_enemy(enemy, with_combo=True)

        if not self.player.alive_in_world:
            return

        # enemies ramming the player
        for enemy in pygame.sprite.spritecollide(self.player, self.enemies, False, pygame.sprite.collide_circle):
            result = self.player.take_damage(PLAYER_COLLISION_DAMAGE)
            if result == "ignored":
                continue
            if not enemy.is_boss:
                self._kill_enemy(enemy, with_combo=False, award=False)
            else:
                burst(self.particles, self.player.rect.center, 8, rng=self.rng)
            self._player_damaged(result)

        # enemy bullets
        for bullet in pygame.sprite.spritecollide(self.player, self.enemy_bullets, False, pygame.sprite.collide_circle):
            result = self.player.take_damage(bullet.damage)
            if result == "ignored":
                continue
            bullet.kill()
            self._player_damaged(result)

        # pickups
        for pu in pygame.sprite.spritecollide(self.player, self.powerups, True, pygame.sprite.collide_circle):
            self._collect(pu)

    def _player_damaged(self, result: str) -> None:
        if result == "shielded":
            self.game.audio.play("player_hit")
            burst(self.particles, self.player.rect.center, 6, (CYAN, WHITE), 160, 0.3, 3, self.rng)
            return
        if result == "hit":
            self.game.audio.play("player_hit")
            self.shake.add(SHAKE_HIT)
            self.flash.trigger(RED, 70)
            burst(self.particles, self.player.rect.center, 10, (ORANGE, RED, WHITE), 200, 0.4, 3, self.rng)
        elif result == "died":
            self.game.audio.play("player_death")
            self.shake.add(SHAKE_HIT * 2)
            self.flash.trigger(WHITE, 140)
            self.effects.add(Explosion(self.player.rect.center, scale=6, frame_time=0.08))
            burst(self.particles, self.player.rect.center, 40, (CYAN, WHITE, ORANGE), 320, 0.9, 4, self.rng)
            self.combo.reset()

    def _kill_enemy(self, enemy: Enemy, with_combo: bool, award: bool = True) -> None:
        enemy.kill()
        self.kills += 1
        center = enemy.rect.center
        if enemy.is_boss:
            self.boss = None
            self.effects.add(Explosion(center, scale=14, frame_time=0.1))
            burst(self.particles, center, 90, (MAGENTA, ORANGE, YELLOW, WHITE), 420, 1.4, 6, self.rng)
            self.shake.add(SHAKE_BOSS_DEATH)
            self.flash.trigger(WHITE, 200)
            self.game.audio.play("boss_death")
            self._drop(center, force=True)
            self._drop((center[0] - 50, center[1]), force=True)
        else:
            self.effects.add(Explosion(center))
            burst(self.particles, center, 12, rng=self.rng)
            self.shake.add(SHAKE_EXPLOSION)
            self.game.audio.play("explosion")
            self._drop(center)
        if award:
            mult = self.combo.register_kill() if with_combo else 1
            points = int(enemy.score * mult * self.difficulty.score_mult)
            self.score += points
            colour = YELLOW if mult > 1 else WHITE
            label = f"+{points:,}" + (f"  x{mult}" if mult > 1 else "")
            self.texts.add(FloatingText(label, center, colour, 30 if enemy.is_boss else 22))

    def _drop(self, center, force: bool = False) -> None:
        if force or self.rng.random() < POWERUP_DROP_CHANCE:
            self.powerups.add(PowerUp(random_kind(self.rng), center))

    def _collect(self, pu: PowerUp) -> None:
        p = self.player
        label, colour = "", GREEN
        if pu.kind == "weapon":
            label = "WEAPON UP" if p.upgrade_weapon() else "MAX POWER"
            colour = ORANGE
        elif pu.kind == "health":
            p.heal(POWERUP_HEALTH_VALUE)
            label = "REPAIRED"
        elif pu.kind == "shield":
            p.activate_shield()
            label, colour = "SHIELD", CYAN
        elif pu.kind == "bomb":
            label = "BOMB +1" if p.add_bomb() else "BOMBS FULL"
            colour = (255, 140, 140)
        elif pu.kind == "score":
            bonus = int(POWERUP_SCORE_VALUE * self.difficulty.score_mult)
            self.score += bonus
            label, colour = f"+{bonus:,}", YELLOW
        self.game.audio.play("powerup")
        self.texts.add(FloatingText(label, (p.x, p.rect.top - 10), colour, 24, 1.0))
        burst(self.particles, p.rect.center, 10, (colour, WHITE), 150, 0.4, 3, self.rng)

    def use_bomb(self) -> None:
        if not self.player.use_bomb():
            return
        self.game.audio.play("bomb")
        self.shake.add(SHAKE_BOMB)
        self.flash.trigger(WHITE, 220)
        self.enemy_bullets.empty()
        for enemy in list(self.enemies):
            if enemy.is_boss:
                if enemy.hit(max(1, enemy.max_hp // 4)):
                    self._kill_enemy(enemy, with_combo=False)
            else:
                self._kill_enemy(enemy, with_combo=False)
        self.texts.add(FloatingText("BOMB!", (WIDTH // 2, HEIGHT // 2), WHITE, 48, 0.8))

    # -- drawing -------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        canvas = self.canvas
        self.game.starfield.draw(canvas)
        self.powerups.draw(canvas)
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
                    draw_text(canvas, "WARNING", 72, (WIDTH // 2, HEIGHT // 2 - 30), RED)
                draw_text(canvas, "DREADNOUGHT APPROACHING", 32, (WIDTH // 2, HEIGHT // 2 + 30), MAGENTA)
            else:
                draw_text(canvas, f"WAVE {d.wave}", 72, (WIDTH // 2, HEIGHT // 2 - 20), CYAN)
                if d.wave == 1:
                    draw_text(canvas, "HOLD SPACE TO FIRE", 28, (WIDTH // 2, HEIGHT // 2 + 40), WHITE)
                elif (d.wave + 1) % BOSS_EVERY == 0:
                    draw_text(canvas, "BOSS NEXT WAVE", 28, (WIDTH // 2, HEIGHT // 2 + 40), ORANGE)
        elif d.state == "intermission" and d.wave > 0:
            draw_text(canvas, "WAVE CLEAR", 48, (WIDTH // 2, HEIGHT // 2 - 20), GREEN)
