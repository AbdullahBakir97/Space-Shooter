import math
import random

import pygame
import pytest

from space_shooter.config import HEIGHT, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.dash import DASH_SPEED
from space_shooter.entities.bullets import HeavySlug, SlugBullet
from space_shooter.entities.enemies import ENEMY_CLASSES, Diver, Drone, Gunner
from space_shooter.entities.parts import Drop, PartRig, draw_loadout
from space_shooter.entities.player import PLAY_TOP, Player
from space_shooter.salvage import Loadout, Part


class FakeWorld:
    def __init__(self):
        self.player_pos = (WIDTH / 2, HEIGHT - 60)
        self.rng = random.Random(1)
        self.shots = []

    def aim_point(self):
        return self.player_pos

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

    def test_fire_respects_cooldown(self):
        p = Player()
        assert len(p.try_fire()) == 1
        assert p.try_fire() == []

    def test_player_fire_adds_slug_rounds(self):
        p = Player()
        p.loadout.attach(Part("slug"), (-14, -30))
        bullets = p.try_fire()
        assert len(bullets) == 2 and sum(isinstance(b, SlugBullet) for b in bullets) == 1

    def test_thruster_moves_player_faster(self):
        a, b = Player(), Player()
        b.loadout.attach(Part("thruster"), (-16, 30))
        a.update(0.2, (1, 0))
        b.update(0.2, (1, 0))
        assert b.x - WIDTH / 2 == pytest.approx((a.x - WIDTH / 2) * 1.15)

    def test_armour_takes_hit_before_hull(self):
        p = Player()
        p.loadout.attach(Part("armour"), (0, 0))
        assert p.take_damage(30, random.Random(0)) == "armour"
        assert p.health == PLAYER_MAX_HEALTH and p.last_outcome.kind == "armour"

    def test_hit_then_brief_invulnerability(self):
        p = Player()
        assert p.take_damage(30, random.Random(0)) == "hit"
        assert p.health == PLAYER_MAX_HEALTH - 30
        assert p.take_damage(30, random.Random(0)) == "ignored"

    def test_player_dies_once_at_zero_hull(self):
        p = Player()
        assert p.take_damage(999, random.Random(0)) == "died"
        assert p.dead and p.health == 0 and p.try_fire() == []
        p.invuln_timer = 0
        assert p.take_damage(10, random.Random(0)) == "ignored"


@pytest.mark.usefixtures("display")
class TestParts:
    def test_slug_bullet_stats(self):
        b = SlugBullet((100, 100), (0, -500))
        assert b.damage == 3 and b.pierce == 1

    def test_drop_blinks_and_expires(self):
        d = Drop("turret", (100, 100), vel=(0, 0), lifetime=6.0)
        group = pygame.sprite.Group(d)
        d.update(4.5)
        assert d.blinking and d.alive()
        d.update(1.6)
        assert not d.alive() and len(group) == 0

    def test_pickup_delay(self):
        d = Drop("turret", (100, 100), vel=(0, 0), lifetime=6.0, pickup_delay=0.8)
        pygame.sprite.Group(d)
        assert not d.collectable
        d.update(0.9)
        assert d.collectable and Drop("patch", (0, 0)).collectable

    def test_falling_drop_dies_off_screen(self):
        d = Drop("patch", (100, HEIGHT - 5), vel=(0, 300))
        pygame.sprite.Group(d)
        d.update(1.0)
        assert not d.alive()

    def test_rig_turret_fires_at_nearest_enemy_in_range(self):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        near, far = Drone(300.0), Drone(300.0)
        near.x, near.y, far.x, far.y = 300, 300, 300, -500
        rig = PartRig()
        shots = rig.update(0.6, lo, (300, 500), [far, near], 1.0)
        assert len(shots) == 1 and shots[0].vy < 0
        assert rig.update(0.1, lo, (300, 500), [near], 1.0) == []

    def test_turret_reaches_top_of_screen(self):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        e = Drone(300.0)
        e.x, e.y = 300, 40
        shots = PartRig().update(1.0, lo, (300, 600), [e], 1.0)
        assert len(shots) == 1 and shots[0].vy < 0

    def test_turret_targets_nearest_to_ship_and_swivels(self):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        near, far = Drone(100.0), Drone(500.0)
        near.x, near.y, far.x, far.y = 100, 400, 500, 100
        rig = PartRig()
        shot = rig.update(1.0, lo, (300, 560), [far, near], 1.0)[0]
        assert shot.vx < 0  # toward the nearer enemy on the left
        assert rig.aim["wing_l"] == pytest.approx(math.atan2(400 - 562, 100 - 270))

    def test_scarred_turret_bursts(self):
        lo = Loadout()
        lo.attach(Part("turret", rare=True), (-30, 2))
        e = Drone(300.0)
        e.x, e.y = 300, 200
        rig = PartRig()
        first = rig.update(0.01, lo, (300, 560), [e], 1.0)
        second = rig.update(0.09, lo, (300, 560), [e], 1.0)
        assert len(first) == 1 and len(second) == 1

    def test_twin_turrets_fire_together(self):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        lo.attach(Part("turret"), (30, 2))
        e = Drone(300.0)
        e.x, e.y = 300, 200
        rig = PartRig()
        assert len(rig.update(0.01, lo, (300, 560), [e], 1.0)) == 2
        assert rig.update(0.30, lo, (300, 560), [e], 1.0) == []
        assert len(rig.update(0.06, lo, (300, 560), [e], 1.0)) == 2  # 0.35 s period

    def test_heavy_slug_every_fourth_pull(self):
        p = Player()
        p.loadout.attach(Part("slug"), (-14, -30))
        kinds = []
        for _ in range(8):
            p.fire_cooldown = 0
            kinds.append(any(isinstance(b, HeavySlug) for b in p.try_fire()))
        assert kinds == [False, False, False, True, False, False, False, True]

    def test_broadside_every_third(self):
        p = Player()
        p.loadout.attach(Part("slug"), (-14, -30))
        p.loadout.attach(Part("slug"), (14, -30))
        heavy = []
        for _ in range(6):
            p.fire_cooldown = 0
            heavy.append(sum(isinstance(b, HeavySlug) for b in p.try_fire()))
        assert heavy == [0, 0, 2, 0, 0, 2]

    def test_heavy_slug_stats(self):
        h = HeavySlug((0, 0), (0, -500))
        assert h.damage == 4 and h.pierce >= 10**6 and h.shove == 28

    def test_draw_loadout_full(self, display):
        lo = Loadout()
        for kind, contact in [
            ("slug", (-14, -30)),
            ("claw", (14, -30)),
            ("turret", (-30, 2)),
            ("armour", (30, 2)),
            ("tractor", (-16, 30)),
            ("thruster", (16, 30)),
        ]:
            lo.attach(Part(kind, rare=kind == "slug"), contact)
        draw_loadout(display, lo, (400, 300), alpha=90)


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

    def test_hit_and_flash(self):
        e = ENEMY_CLASSES["zigzag"](200.0, hp_mult=1.0)
        assert not e.hit(1)
        assert e.flash > 0
        assert e.hit(5)


def test_ash_cloud_is_dense_enough_to_hide_bullets(display):
    from space_shooter.procgen import ash_cloud_sprite

    cloud = ash_cloud_sprite(0)
    assert cloud.get_at((100, 65)).a >= 140


def test_turret_barrel_is_drawn_toward_its_aim(display):
    lo = Loadout()
    lo.attach(Part("turret"), (-30, 2))
    up, left = pygame.Surface((200, 200)), pygame.Surface((200, 200))
    draw_loadout(up, lo, (100, 100), aim={"wing_l": -math.pi / 2})
    draw_loadout(left, lo, (100, 100), aim={"wing_l": math.pi})
    assert pygame.image.tobytes(up, "RGB") != pygame.image.tobytes(left, "RGB")


def test_bullet_speed_scale(display):
    from space_shooter.entities.bullets import EnemyBullet

    a, b = EnemyBullet((100, 100), (0, 100)), EnemyBullet((100, 100), (0, 100))
    b.speed_scale = 0.6
    a.update(1.0)
    b.update(1.0)
    assert a.y == pytest.approx(200) and b.y == pytest.approx(160)


def test_armour_cracks_are_drawn(display):
    whole, cracked = Loadout(), Loadout()
    whole.attach(Part("armour"), (30, 2))
    cracked.attach(Part("armour"), (30, 2))
    cracked.slots["wing_r"].armour_left = 1
    a, b = pygame.Surface((200, 200)), pygame.Surface((200, 200))
    draw_loadout(a, whole, (100, 100))
    draw_loadout(b, cracked, (100, 100))
    assert pygame.image.tobytes(a, "RGB") != pygame.image.tobytes(b, "RGB")


@pytest.mark.usefixtures("display")
class TestDash:
    def test_dash_needs_thruster(self):
        p = Player()
        p.update(0.0)
        assert p.start_dash((1, 0)) is False

    def test_dash_moves_fast_and_is_invulnerable(self):
        p = Player()
        p.loadout.attach(Part("thruster"), (-16, 30))
        p.update(0.0)
        x0 = p.x
        assert p.start_dash((-1, 0))
        p.update(0.1, (0, 0))
        assert x0 - p.x == pytest.approx(DASH_SPEED * 0.1, abs=1)
        assert p.take_damage(50, random.Random(0)) == "ignored"
        p.update(0.2, (0, 0))
        assert not p.dash.active

    def test_dash_direction_defaults_up(self):
        p = Player()
        p.loadout.attach(Part("thruster"), (-16, 30))
        p.update(0.0)
        p.y = 500
        p.start_dash((0, 0))
        p.update(0.05)
        assert p.y < 500 and p.x == pytest.approx(WIDTH / 2)

    def test_afterburner_two_dashes(self):
        p = Player()
        p.loadout.attach(Part("thruster"), (-16, 30))
        p.loadout.attach(Part("thruster"), (16, 30))
        p.update(0.0)
        assert p.start_dash((1, 0))
        p.update(0.2)
        assert p.start_dash((1, 0))
        p.update(0.2)
        assert p.start_dash((1, 0)) is False

    def test_losing_thruster_clears_charges(self):
        p = Player()
        p.loadout.attach(Part("thruster"), (-16, 30))
        p.update(0.0)
        assert p.dash.charges == 1
        p.loadout.slots["aft_l"] = None
        p.update(0.5)
        assert p.dash.charges == 0 and p.start_dash((1, 0)) is False


def parked(enemy, y=200.0):
    enemy.y, enemy.speed = y, 0.0
    return enemy


@pytest.mark.usefixtures("display")
class TestEnemyFire:
    def run(self, enemy, seconds, world=None):
        world = world or FakeWorld()
        pygame.sprite.Group(enemy)
        for _ in range(int(seconds * 60)):
            enemy.update(1 / 60, world)
        return world

    def test_unarmed_drone_never_fires(self):
        world = self.run(parked(Drone(400.0, armed=False)), 8)
        assert world.shots == []

    def test_drone_fires_aimed_when_armed(self):
        world = self.run(parked(Drone(200.0)), 4)
        assert world.shots
        (x, y), (vx, vy), _ = world.shots[0]
        tx, ty = world.player_pos
        assert vy > 0 and (vx > 0) == (tx > x)

    def test_zigzag_fires_spread(self):
        z = parked(ENEMY_CLASSES["zigzag"](400.0))
        world = self.run(z, 3.1)
        assert len(world.shots) == 3
        angles = sorted(math.atan2(v[1], v[0]) for _, v, _ in world.shots)
        assert angles[2] - angles[0] == pytest.approx(0.5, abs=1e-6)

    def test_diver_bursts_on_dive(self):
        d = Diver(400.0)
        d.y, d.state, d.hover = Diver.HOVER_Y, "hover", Diver.HOVER_TIME - 0.01
        world = self.run(d, 0.05)
        assert d.state == "dive" and len(world.shots) == 3

    def test_enemies_hold_fire_off_screen(self):
        for kind in ("drone", "zigzag", "gunner"):
            world = self.run(parked(ENEMY_CLASSES[kind](400.0), y=20.0), 6)
            assert world.shots == [], kind
