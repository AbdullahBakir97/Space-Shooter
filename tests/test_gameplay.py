"""Headless integration tests that drive the real scenes."""

import random

import pygame
import pytest

from space_shooter.config import HEIGHT, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.echoes import EchoTrace
from space_shooter.encounters import DRIFT_TIME, loop_hull_multiplier
from space_shooter.entities.bullets import EnemyBullet, PlayerBullet
from space_shooter.entities.enemies import ENEMY_CLASSES, Drone
from space_shooter.entities.hazards import AshCloud, Debris, Hulk
from space_shooter.entities.parts import Drop
from space_shooter.game import Game
from space_shooter.salvage import PATCH_HULL, SLOT_OFFSETS, Part
from space_shooter.save import load_save
from space_shooter.scenes import salvage_ops
from space_shooter.scenes.gameplay import ECHO_RAM_DAMAGE, GameplayScene
from space_shooter.scenes.log_panel import LogPanel
from space_shooter.settings_store import Settings
from space_shooter.story import BAD_LOGS_NOTICE, LogDirector


@pytest.fixture
def game():
    """A game with the radio silent, so mechanics tests are not paused by log panels."""
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    g.logs = LogDirector([], g.save.read_logs)
    yield g
    pygame.quit()


@pytest.fixture
def story_game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    yield g
    pygame.quit()


def run_frames(game, n, dt=1 / 60):
    for _ in range(n):
        scene = game.scenes.top
        scene.update(dt)
        game.scenes.draw(game.screen)


def test_waves_spawn_and_bullets_score(game):
    scene = GameplayScene(game, seed=42)
    game.scenes.push(scene)
    run_frames(game, int(60 * (DRIFT_TIME + 4)))  # drift, then the first spawns
    assert scene.director.index == 0 and scene.director.state == "active" and len(scene.enemies) > 0
    # park an enemy right above the player and shoot it
    enemy = Drone(scene.player.x)
    enemy.y = scene.player.y - 120
    scene.enemies.add(enemy)
    scene.player.fire_cooldown = 0
    bullets = scene.player.try_fire()
    scene.player_bullets.add(bullets)
    run_frames(game, 30)
    assert scene.score > 0
    assert scene.kills >= 1


class AlwaysKnock:
    """RNG stub: every roll succeeds and choices take the first option."""

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]

    def uniform(self, a, b):
        return a

    def choices(self, population, weights=None):
        return [population[0]]


def test_collecting_drop_attaches_part(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.drops.add(Drop("turret", (scene.player.x - 30, scene.player.y), vel=(0, 0)))
    run_frames(game, 2)
    assert scene.player.loadout.count("turret") == 1 and len(scene.drops) == 0


def test_collecting_patch_heals(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.health = 50
    scene.drops.add(Drop("patch", (scene.player.x, scene.player.y), vel=(0, 0)))
    run_frames(game, 2)
    assert scene.player.health == 50 + PATCH_HULL


def test_replaced_part_is_ejected_as_drop(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    lo = scene.player.loadout
    lo.attach(Part("slug"), (-14, -30))
    lo.attach(Part("claw"), (14, -30))
    scene.drops.add(Drop("slug*", (scene.player.x, scene.player.y - 30), vel=(0, 0)))
    run_frames(game, 1)
    codes = [d.code for d in scene.drops]
    assert codes == ["slug"] and lo.slots["fore_l"].rare


def test_knocked_part_becomes_recoverable_drop(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.loadout.attach(Part("turret"), (-30, 2))
    scene.rng = AlwaysKnock()
    scene.enemy_bullets.add(EnemyBullet((scene.player.x, scene.player.y), (0, 0)))
    run_frames(game, 1)
    knocked = [d for d in scene.drops if d.code == "turret"]
    assert scene.player.loadout.count("turret") == 0 and knocked and knocked[0].lifetime == 6.0
    assert scene.player.health == PLAYER_MAX_HEALTH


def test_tractor_pulls_drops(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    drop = Drop("armour", (scene.player.x + 150, scene.player.y), vel=(0, 0))
    scene.drops.add(drop)
    start = drop.x
    run_frames(game, 10)
    assert drop.x < start or not drop.alive()


def test_long_headless_run_is_stable(game):
    """Simulate a couple of minutes at a high difficulty with autofire on."""
    game.settings.difficulty = "hard"
    scene = GameplayScene(game, seed=7)
    game.scenes.push(scene)
    for frame in range(60 * 120):
        top = game.scenes.top
        if isinstance(top, GameplayScene):
            top.player_bullets.add(top.player.try_fire())
            if frame % 7 == 0:
                top.player.x = (top.player.x + 40) % WIDTH
        top.update(1 / 60)
        game.scenes.draw(game.screen)
    assert 0 <= scene.player.x <= WIDTH and 0 <= scene.player.y <= HEIGHT
    assert scene.director.index >= 1


def start_at(game, index, seed=1):
    """Gameplay scene whose director sits at the start of encounter ``index``."""
    scene = GameplayScene(game, seed=seed)
    scene.director.index = index
    game.scenes.push(scene)
    run_frames(game, int(60 * DRIFT_TIME) + 2)
    assert scene.director.state in ("active", "clearing") and scene.director.index == index
    return scene


def test_encounter_spawns_after_drift(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    run_frames(game, int(60 * (DRIFT_TIME - 1)))
    assert scene.director.state == "drift" and len(scene.enemies) == 0
    run_frames(game, 60 * 4)
    assert len(scene.enemies) > 0 and scene.banner_text == "COLD WAKE"


def test_loop_scaling_caps():
    assert loop_hull_multiplier(1) == 1.0
    assert loop_hull_multiplier(5) == pytest.approx(1.16)
    assert loop_hull_multiplier(30) == pytest.approx(1.60)


def test_loop_scaling_applies_to_enemy_hull(game):
    game.save.loop = 30
    scene = start_at(game, 2)
    run_frames(game, 60 * 3)
    zig = [e for e in scene.enemies if e.kind == "drone"]
    assert zig and all(e.max_hp >= 1 for e in zig)
    assert scene.hull_mult == pytest.approx(1.60)


def test_aim_point_prefers_armour(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    assert scene.aim_point() == scene.player_pos
    scene.player.loadout.attach(Part("armour"), (30, 30))
    ox, oy = SLOT_OFFSETS["aft_r"]
    assert scene.aim_point() == (scene.player.x + ox, scene.player.y + oy)


def test_hulk_blocks_bullets(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    hulk = Hulk((400, 300))
    scene.hazards.add(hulk)
    bullet = PlayerBullet((400, 420), (0, -800), 1)
    scene.player_bullets.add(bullet)
    enemy_shot = EnemyBullet((400, 180), (0, 300))
    scene.enemy_bullets.add(enemy_shot)
    run_frames(game, 30)
    assert not bullet.alive() and not enemy_shot.alive() and hulk.hp < 8


def test_destroyed_hulk_drops_part(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    hulk = Hulk((400, 300), hp=1, rare_drop=True)
    scene.hazards.add(hulk)
    scene.player_bullets.add(PlayerBullet((400, 420), (0, -800), 1))
    run_frames(game, 30)
    assert not hulk.alive() and any(d.code.endswith("*") for d in scene.drops)


def test_graveyard_spawns_hulks_and_breach_drops_rare(game):
    scene = start_at(game, 2)
    assert len([h for h in scene.hazards if isinstance(h, Hulk)]) == 4
    scene.trigger_moment("hulk_breach")
    assert len([h for h in scene.hazards if isinstance(h, Hulk)]) == 3
    assert any(d.code.endswith("*") for d in scene.drops)


def test_ash_shelf_drifts_ash_clouds(game):
    scene = start_at(game, 1)
    run_frames(game, 60 * 6)
    assert any(isinstance(h, AshCloud) for h in scene.hazards)


def test_last_light_rains_debris_that_hurts(game):
    scene = start_at(game, 4)
    run_frames(game, 60 * 3)
    assert any(isinstance(h, Debris) for h in scene.hazards)
    rock = Debris((scene.player.x, scene.player.y), (0, 0))
    scene.hazards.add(rock)
    run_frames(game, 1)
    assert scene.player.health < PLAYER_MAX_HEALTH and not rock.alive()


def test_first_kill_of_cold_wake_always_drops_part(game):
    scene = start_at(game, 0)
    enemy = Drone(scene.player.x)
    enemy.y = scene.player.y - 150
    scene.enemies.add(enemy)
    scene.rng = random.Random(123)
    scene.drops.empty()
    scene._kill_enemy(enemy)
    assert [d.code for d in scene.drops] and scene.drops.sprites()[0].code != "patch"


def test_blackout_moment(game):
    scene = start_at(game, 1)
    scene.trigger_moment("blackout")
    assert scene.blackout_timer == pytest.approx(4.0)
    run_frames(game, 60 * 5)
    assert scene.blackout_timer == 0


def test_flare_hurts_unshadowed_player(game):
    scene = start_at(game, 4)
    scene.trigger_moment("flare")
    run_frames(game, int(60 * 1.4))
    assert scene.player.health == PLAYER_MAX_HEALTH  # still the warning
    run_frames(game, 60)
    assert scene.player.health == PLAYER_MAX_HEALTH - 30


def test_flare_spares_player_behind_hulk(game):
    scene = start_at(game, 4)
    scene.hazards.add(Hulk((scene.player.x, scene.player.y - 160)))
    scene.trigger_moment("flare")
    run_frames(game, 60 * 3)
    assert scene.player.health == PLAYER_MAX_HEALTH


def test_retreat_removes_enemies(game):
    scene = start_at(game, 0)
    run_frames(game, 60 * 3)
    assert len(scene.enemies) > 0
    scene.director.t_rel = scene.director.encounter.time_cap - 0.05  # hit the real time cap
    run_frames(game, 60 * 6)
    assert len(scene.enemies) == 0 and scene.director.index == 1


def seeded_trace(loop, encounters=(0,), seconds=20.0, x=400.0, reached=None):
    samples = []
    for enc in encounters:
        for i in range(int(seconds * 20)):
            samples.append((enc, i / 20, x, 500.0, i % 4 == 0))
    return EchoTrace(loop, reached if reached is not None else max(encounters), seconds, samples, [])


def test_echoes_fly_and_fire(game):
    game.save.echoes = [seeded_trace(n, x=200.0 + n * 100).to_data() for n in (1, 2, 3)]
    scene = start_at(game, 0)
    run_frames(game, 60 * 2)
    assert len(scene.live_echoes()) == 3
    assert len(scene.echo_bullets) > 0
    xs = sorted(round(e.x) for e in scene.live_echoes())
    assert xs == [300, 400, 500]


def test_destroyed_echo_is_removed_from_save(game):
    game.save.echoes = [seeded_trace(7, x=200.0).to_data(), seeded_trace(8, x=600.0).to_data()]
    scene = start_at(game, 0)
    run_frames(game, 10)
    echo = next(e for e in scene.live_echoes() if e.loop == 7)
    echo.hp = 1
    scene.enemy_bullets.add(EnemyBullet((echo.x, echo.y), (0, 0)))
    run_frames(game, 2)
    assert not echo.alive()
    assert [d.loop for d in game.save.echoes] == [8]
    assert {"first_echo_lost", "echo_lost:7"} <= game.save.flags
    assert "Echo 7 is gone." in [text for text, _ in scene.radio_lines]


def test_echo_without_encounter_data_is_absent(game):
    game.save.echoes = [seeded_trace(4, encounters=(0,)).to_data()]
    scene = start_at(game, 1)
    run_frames(game, 60)
    assert scene.live_echoes() == []


def test_finished_echo_fades_out(game):
    game.save.echoes = [seeded_trace(5, seconds=1.0, reached=0).to_data()]
    scene = start_at(game, 0)
    run_frames(game, 60 * 3)
    assert scene.live_echoes() == [] and len(scene.echoes) == 0
    assert [d.loop for d in game.save.echoes] == [5]  # fading is not dying


def test_death_stores_trace_and_advances_loop(game):
    scene = start_at(game, 0)
    run_frames(game, 60 * 6)
    rng = random.Random(0)
    while not scene.player.dead:  # parts or a warm-up ram may absorb the first lethal hits
        scene.player.invuln_timer = 0
        scene.player.take_damage(999, rng)
    run_frames(game, 2)
    assert game.save.loop == 2 and len(game.save.echoes) == 1
    stored = EchoTrace.from_data(game.save.echoes[0])
    assert stored.loop == 1 and stored.samples and stored.samples[0][0] == 0
    assert load_save().loop == 2


def test_drift_pushes_log_panel_once(story_game):
    game = story_game
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    run_frames(game, 1)
    assert isinstance(game.scenes.top, LogPanel) and game.scenes.top.entry.id == "a1_open"
    assert game.save.read_logs == ["a1_open"]
    game.scenes.top.handle_action("confirm")
    game.scenes.top.handle_action("confirm")
    assert game.scenes.top is scene
    run_frames(game, 60 * 3)
    assert game.scenes.top is scene  # one log per drift
    assert load_save().read_logs == ["a1_open"]


def test_next_drift_plays_next_eligible_log(story_game):
    game = story_game
    game.save.read_logs.append("a1_open")
    scene = GameplayScene(game, seed=1)
    scene.director.index = 0
    game.scenes.push(scene)
    run_frames(game, 1)
    assert game.scenes.top is scene  # nothing eligible before the first encounter
    scene.director.index = 1
    scene.director._events.append(("drift_start", 1))
    run_frames(game, 1)
    assert isinstance(game.scenes.top, LogPanel) and game.scenes.top.entry.id == "a1_ash"  # warns before Ash Shelf


def test_log_panel_completes_then_closes(story_game):
    game = story_game
    closed = []
    entry = game.logs.get("a1_open")
    game.scenes.push(GameplayScene(game, seed=1))
    panel = LogPanel(game, entry, on_close=lambda: closed.append(True))
    game.scenes.push(panel)
    run_frames(game, 5)
    assert 0 < panel.shown < len(panel.full_text)
    panel.handle_action("fire")
    assert panel.shown == len(panel.full_text) and game.scenes.top is panel
    panel.handle_action("back")
    assert game.scenes.top is not panel and closed == [True]


def test_typewriter_speed(story_game):
    game = story_game
    panel = LogPanel(game, game.logs.get("a1_open"))
    game.scenes.push(panel)
    panel.update(0.5)
    assert panel.shown == 20  # 40 characters per second


def test_bad_log_data_starts_silent_with_notice(tmp_path, monkeypatch):
    from space_shooter import story

    bad = tmp_path / "logs.json"
    bad.write_text("{broken")
    monkeypatch.setattr(story, "LOGS_PATH", bad)
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    assert g.logs.logs == [] and g.save.notice == BAD_LOGS_NOTICE
    scene = GameplayScene(g, seed=1)
    g.scenes.push(scene)
    run_frames(g, 60)
    assert g.scenes.top is scene
    pygame.quit()


def test_ash_cloud_hides_but_does_not_destroy_player_bullets(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    scene.hazards.add(AshCloud((400, 300)))
    bullet = PlayerBullet((400, 320), (0, 0), 1)
    scene.player_bullets.add(bullet)
    run_frames(game, 3)
    assert bullet.alive()


def test_last_light_has_shelter_from_the_flare(game):
    scene = start_at(game, 4)
    hulks = [h for h in scene.hazards if isinstance(h, Hulk)]
    assert hulks and all(h.vy <= 2.0 for h in hulks)  # still on screen when the flare comes at 45 s


def test_echo_contact_damage_has_a_cooldown(game):
    game.save.echoes = [seeded_trace(9, x=400.0).to_data()]
    scene = start_at(game, 0)
    run_frames(game, 2)
    echo = scene.live_echoes()[0]
    gunner = ENEMY_CLASSES["gunner"](echo.x)
    gunner.hp = gunner.max_hp = 99
    scene.enemies.add(gunner)
    for _ in range(30):  # half a second of overlap
        gunner.x, gunner.y = echo.x, echo.y
        gunner.rect.center = (round(echo.x), round(echo.y))
        scene._collisions()
    assert echo.hp == 6 - ECHO_RAM_DAMAGE and gunner.hp == 98


def test_hud_does_not_mark_a_finished_echo_as_lost(game):
    from space_shooter.hud import roster_status

    game.save.echoes = [seeded_trace(5, seconds=1.0, reached=0).to_data()]
    scene = start_at(game, 0)
    run_frames(game, 60 * 3)
    assert len(scene.echoes) == 0  # it faded out at the end of its recording
    assert roster_status(scene) == [(5, False)]


def test_difficulty_table():
    from space_shooter.config import DIFFICULTIES, ENEMY_BULLET_SPEED

    rows = {k: (d.enemy_speed, d.enemy_hp, d.enemy_fire_rate, d.score_mult) for k, d in DIFFICULTIES.items()}
    assert rows == {"easy": (1.0, 1.0, 1.0, 0.8), "normal": (1.25, 1.4, 1.5, 1.0), "hard": (1.4, 1.8, 2.0, 1.5)}
    assert ENEMY_BULLET_SPEED == 290.0


def column_of_gunners(scene, x, ys, hp=1):
    out = []
    for y in ys:
        g = ENEMY_CLASSES["gunner"](x)
        g.y, g.hp, g.line_y, g.speed = y, hp, 10**6, 0.0  # parked: only the test moves it
        g.rect.center = (round(g.x), round(g.y))
        scene.enemies.add(g)
        out.append(g)
    return out


def test_heavy_slug_pierces_line_and_shoves(game):
    from space_shooter.entities.bullets import HeavySlug

    scene = start_at(game, 3)
    scene.enemies.empty()
    a, b, c = column_of_gunners(scene, 300.0, (400, 300, 200), hp=50)
    scene.player_bullets.add(HeavySlug((300, 470), (0, -520)))
    run_frames(game, 40)
    assert a.hp == b.hp == c.hp == 46
    assert a.y == pytest.approx(400 - 28)  # shoved back once


def test_heavy_kill_counted_once(game):
    from space_shooter.entities.bullets import HeavySlug

    scene = start_at(game, 3)
    scene.enemies.empty()
    kills = scene.kills
    column_of_gunners(scene, 300.0, (400, 380), hp=1)
    scene.player_bullets.add(HeavySlug((300, 470), (0, -520)))
    run_frames(game, 30)
    assert scene.kills - kills == 2


def test_claw_tears_and_forces_drop(game):
    scene = start_at(game, 0)
    scene.enemies.empty()
    scene.player.loadout.attach(Part("claw"), (-14, -30))
    scene.rng = random.Random(5)
    ox, oy = SLOT_OFFSETS["fore_l"]
    (victim,) = column_of_gunners(scene, scene.player.x + ox, (scene.player.y + oy,), hp=2)
    scene.drops.empty()
    salvage_ops.claw_contacts(scene, 1 / 60)
    assert not victim.alive() and len(scene.drops) == 1


def test_claw_cooldown_per_enemy(game):
    scene = start_at(game, 0)
    scene.enemies.empty()
    scene.player.loadout.attach(Part("claw"), (-14, -30))
    ox, oy = SLOT_OFFSETS["fore_l"]
    (victim,) = column_of_gunners(scene, scene.player.x + ox, (scene.player.y + oy,), hp=10)
    salvage_ops.claw_contacts(scene, 1 / 60)
    salvage_ops.claw_contacts(scene, 0.1)
    assert victim.hp == 8
    salvage_ops.claw_contacts(scene, 0.25)
    assert victim.hp == 6


def test_scrapper_drops_are_scarred(game):
    scene = start_at(game, 1)
    lo = scene.player.loadout
    lo.attach(Part("claw"), (-14, -30))
    lo.attach(Part("claw"), (14, -30))
    codes = []
    for _ in range(60):
        scene.drops.empty()
        scene._drop((400, 200), force=True)
        codes += [d.code for d in scene.drops if d.code != "patch"]
    assert codes and all(code.endswith("*") for code in codes)


def test_tractor_range_360_pulls_distant_drop(game):
    scene = start_at(game, 0)
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    drop = Drop("armour", (scene.player.x + 300, scene.player.y - 40), vel=(0, 0))
    scene.drops.add(drop)
    start = (drop.x, drop.y)
    target = salvage_ops.tractor(scene, 1 / 60)
    assert target == start and (drop.x, drop.y) != start  # beam locked on, drop moving
    run_frames(game, 120)
    assert scene.player.loadout.count("armour") == 1


def test_tractor_ignores_drops_beyond_range(game):
    scene = start_at(game, 0)
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    drop = Drop("armour", (scene.player.x - 390, 120), vel=(0, 0))
    scene.drops.add(drop)
    assert salvage_ops.tractor(scene, 1 / 60) is None


def test_gravity_well_pulls_from_anywhere(game):
    scene = start_at(game, 0)
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    scene.player.loadout.attach(Part("tractor"), (16, 30))
    drop = Drop("armour", (20, 80), vel=(0, 0))
    scene.drops.add(drop)
    assert salvage_ops.tractor(scene, 1 / 60) is not None


def test_drag_field_slows_near_bullets_only(game):
    scene = start_at(game, 0)
    near = EnemyBullet((scene.player.x, scene.player.y - 100), (0, 0))
    far = EnemyBullet((scene.player.x, scene.player.y - 300), (0, 0))
    scene.enemy_bullets.add(near, far)
    salvage_ops.drag_field(scene)
    assert near.speed_scale == far.speed_scale == 1.0  # no tractor, no field
    scene.player.loadout.attach(Part("tractor"), (-16, 30))
    salvage_ops.drag_field(scene)
    assert near.speed_scale == pytest.approx(0.6) and far.speed_scale == 1.0


def test_armour_break_spawns_shrapnel(game):
    scene = start_at(game, 0)
    scene.enemies.empty()
    scene.player.loadout.attach(Part("armour"), (30, 2))
    scene.player.loadout.slots["wing_r"].armour_left = 1
    before = len(scene.player_bullets)
    scene.enemy_bullets.add(EnemyBullet((scene.player.x, scene.player.y), (0, 0)))
    run_frames(game, 1)
    assert scene.player.loadout.count("armour") == 0
    assert len(scene.player_bullets) - before >= 10


def test_shrapnel_never_hurts_player_or_echoes(game):
    game.save.echoes = [seeded_trace(4, x=420.0).to_data()]
    scene = start_at(game, 0)
    scene.enemies.empty()
    run_frames(game, 2)
    echo = scene.live_echoes()[0]
    salvage_ops.shrapnel(scene, (scene.player.x, scene.player.y))
    salvage_ops.shrapnel(scene, (echo.x, echo.y))
    run_frames(game, 30)
    assert scene.player.health == PLAYER_MAX_HEALTH and echo.hp == 6


def test_echo_bullets_hit_hulks(game):
    scene = GameplayScene(game, seed=1)
    game.scenes.push(scene)
    hulk = Hulk((400, 300))
    scene.hazards.add(hulk)
    shot = PlayerBullet((400, 340), (0, -600), 1)
    scene.echo_bullets.add(shot)
    run_frames(game, 20)
    assert hulk.hp < 8 and not shot.alive()
