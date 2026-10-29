import math
import random

import pygame
import pytest

from space_shooter.config import HEIGHT, WIDTH
from space_shooter.entities.enemies import ENEMY_CLASSES
from space_shooter.entities.warden import Warden
from space_shooter.procgen import warden_sprites

pytestmark = pytest.mark.usefixtures("display")


class FakeWorld:
    def __init__(self, echoes=()):
        self.player_pos = (WIDTH / 2, HEIGHT - 60)
        self.echoes = list(echoes)
        self.rng = random.Random(1)
        self.shots = []
        self.rings = []
        self.phase_drops = []
        self.enemies = []

    def echo_positions(self):
        return list(self.echoes)

    def aim_point(self):
        return self.player_pos

    def fire_enemy_bullet(self, pos, vel, big=False):
        self.shots.append((pos, vel, big))

    def spawn_debris_ring(self, center, count):
        self.rings.append((center, count))

    def warden_phase_drop(self, center):
        self.phase_drops.append(center)


def run(w, world, seconds):
    for _ in range(int(seconds * 60)):
        w.update(1 / 60, world)


def test_registered_as_warden_kind():
    assert ENEMY_CLASSES["warden"] is Warden and "boss" not in ENEMY_CLASSES


def test_hp_scales_with_difficulty():
    assert Warden(400.0).max_hp == 600 and Warden(400.0, hp_mult=1.4).max_hp == 840


def test_phases():
    w = Warden(400.0)
    assert w.phase == 1
    w.hit(205)
    assert w.phase == 2
    w.hit(198)
    assert w.phase == 3


def test_sweep_fires_rotating_fans():
    world = FakeWorld()
    w = Warden(400.0)
    w.y = w.target_y
    run(w, world, 2.0)
    assert len(world.shots) == 14  # two fans of seven
    first = math.atan2(world.shots[3][1][1], world.shots[3][1][0])
    second = math.atan2(world.shots[10][1][1], world.shots[10][1][0])
    assert second - first == pytest.approx(0.35, abs=1e-6)


def test_hunt_targets_densest_echo_cluster():
    world = FakeWorld(echoes=[(100, 400), (110, 410), (700, 400)])
    w = Warden(400.0)
    w.hp = int(w.max_hp * 0.5)
    w.y = w.target_y
    run(w, world, 1.2)
    assert world.shots and all(vx < 0 for _, (vx, vy), _ in world.shots[:5])


def test_hunt_falls_back_to_aim_point_without_echoes():
    world = FakeWorld()
    world.player_pos = (700, 600)
    w = Warden(100.0)
    w.hp = int(w.max_hp * 0.5)
    w.y = w.target_y
    run(w, world, 1.2)
    assert world.shots and all(vx > 0 for _, (vx, vy), _ in world.shots[:5])


def test_collapse_spawns_rings_and_exposes_eye():
    world = FakeWorld()
    w = Warden(400.0)
    w.hp = 30
    w.y = w.target_y
    run(w, world, 3.1)
    assert world.rings and world.rings[0][1] == 12
    assert w.eye_exposed


def test_eye_exposed_doubles_damage():
    w = Warden(400.0)
    w.hp = 40
    w.force_exposed(True)
    w.hit(5)
    assert w.hp == 30
    w.force_exposed(False)
    w.hit(5)
    assert w.hp == 25


def test_stays_on_screen():
    w = Warden(400.0)
    pygame.sprite.Group(w)
    w.retreat()
    run(w, FakeWorld(), 20)
    assert w.alive() and 0 < w.rect.centery < 320
    assert w.rect.left >= 0 and w.rect.right <= WIDTH


def test_warden_sprite_symmetric():
    body, eye = warden_sprites(1)
    assert body.get_size() == (48, 32) and eye.get_size() == body.get_size()
    for y in range(body.get_height()):
        for x in range(body.get_width() // 2):
            assert body.get_at((x, y)) == body.get_at((body.get_width() - 1 - x, y))


def test_warden_numbers():
    from space_shooter.entities import warden

    assert (warden.SWEEP_PERIOD, warden.HUNT_PERIOD, warden.RING_PERIOD, warden.COLLAPSE_SHOT_PERIOD) == (
        0.75,
        0.95,
        2.6,
        1.1,
    )


def test_warden_phase_changes_drop_scarred_parts():
    world = FakeWorld()
    w = Warden(400.0)
    w.y = w.target_y
    run(w, world, 0.5)
    assert world.phase_drops == []
    w.hp = int(w.max_hp * 0.5)
    run(w, world, 0.2)
    assert len(world.phase_drops) == 1
    w.hp = int(w.max_hp * 0.2)
    run(w, world, 0.2)
    run(w, world, 0.2)
    assert len(world.phase_drops) == 2
