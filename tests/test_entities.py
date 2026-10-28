import random

import pygame
import pytest

from space_shooter.config import HEIGHT, PLAYER_MAX_HEALTH, WEAPON_MAX_LEVEL, WIDTH
from space_shooter.entities.enemies import ENEMY_CLASSES, Boss, Diver, Gunner
from space_shooter.entities.player import PLAY_TOP, Player
from space_shooter.entities.powerups import random_kind


class FakeWorld:
    def __init__(self):
        self.player_pos = (WIDTH / 2, HEIGHT - 60)
        self.rng = random.Random(1)
        self.shots = []

    def fire_enemy_bullet(self, pos, vel, big=False):
        self.shots.append((pos, vel, big))


@pytest.mark.usefixtures("display")
class TestPlayer:
    def test_stays_inside_playfield(self):
        p = Player()
        for _ in range(300):
            p.update(1 / 60, (-1, -1))
        assert p.rect.left >= 0 and p.rect.top >= PLAY_TOP
        for _ in range(300):
            p.update(1 / 60, (1, 1))
        assert p.rect.right <= WIDTH and p.rect.bottom <= HEIGHT

    def test_diagonal_is_normalised(self):
        a, b = Player(), Player()
        a.update(0.5, (1, 0))
        b.update(0.5, (1, 1))
        assert abs((b.x - WIDTH / 2) - (a.x - WIDTH / 2) / 2**0.5) < 1e-6

    def test_fire_respects_cooldown_and_level(self):
        p = Player()
        p.invuln_timer = 0
        assert len(p.try_fire()) == 1
        assert p.try_fire() == []
        p.update(1.0)
        for _ in range(3):
            p.upgrade_weapon()
        assert p.weapon_level == WEAPON_MAX_LEVEL
        assert not p.upgrade_weapon()
        assert len(p.try_fire()) == 4

    def test_damage_lives_and_respawn(self):
        p = Player()
        p.invuln_timer = 0
        assert p.take_damage(30) == "hit"
        assert p.take_damage(30) == "ignored"  # brief invulnerability after a hit
        p.invuln_timer = 0
        p.weapon_level = 3
        assert p.take_damage(999) == "died"
        assert p.lives == 2 and p.weapon_level == 2 and not p.alive_in_world
        assert p.try_fire() == []
        p.update(5.0)
        assert p.alive_in_world and p.health == PLAYER_MAX_HEALTH and p.invulnerable

    def test_shield_blocks_damage(self):
        p = Player()
        p.activate_shield()
        assert p.take_damage(50) == "shielded"
        assert p.health == PLAYER_MAX_HEALTH

    def test_game_over_after_last_life(self):
        p = Player()
        p.lives = 1
        p.invuln_timer = 0
        p.take_damage(999)
        p.update(5.0)
        assert p.game_over


@pytest.mark.usefixtures("display")
class TestEnemies:
    @pytest.mark.parametrize("kind", ["drone", "zigzag", "diver", "gunner"])
    def test_regular_enemies_eventually_leave(self, kind):
        world = FakeWorld()
        e = ENEMY_CLASSES[kind](400.0)
        pygame.sprite.Group(e)
        for _ in range(60 * 20):
            e.update(1 / 60, world)
            if not e.alive():
                break
        assert not e.alive()

    def test_diver_dives_toward_player(self):
        world = FakeWorld()
        world.player_pos = (100, 500)
        d = Diver(700.0)
        for _ in range(60 * 3):
            d.update(1 / 60, world)
        assert d.state == "dive" and d.dive_vx < 0 and d.dive_vy > 0

    def test_gunner_shoots(self):
        world = FakeWorld()
        g = Gunner(300.0)
        for _ in range(60 * 5):
            g.update(1 / 60, world)
        assert world.shots

    def test_boss_scales_and_stays_on_screen(self):
        world = FakeWorld()
        b5, b10 = Boss(400.0, wave=5), Boss(400.0, wave=10)
        pygame.sprite.Group(b5)
        assert b10.max_hp > b5.max_hp and b10.score > b5.score
        for _ in range(60 * 10):
            b5.update(1 / 60, world)
        assert b5.alive() and 0 < b5.rect.centery < HEIGHT / 2
        assert world.shots
        assert b5.phase == 1
        b5.hit(b5.max_hp // 2)
        assert b5.phase == 2

    def test_hit_and_flash(self):
        e = ENEMY_CLASSES["zigzag"](200.0, hp_mult=1.0)
        assert not e.hit(1)
        assert e.flash > 0
        assert e.hit(5)


def test_random_kind_only_known():
    rng = random.Random(0)
    assert {random_kind(rng) for _ in range(200)} <= {"weapon", "health", "shield", "bomb", "score"}
