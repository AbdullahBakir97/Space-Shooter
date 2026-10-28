import random

from space_shooter import waves


def test_boss_every_fifth_wave():
    assert [w for w in range(1, 16) if waves.is_boss_wave(w)] == [5, 10, 15]
    assert not waves.is_boss_wave(0)


def test_boss_wave_contains_only_boss():
    plan = waves.build_wave(5, rng=random.Random(1))
    assert [s.kind for s in plan] == ["boss"]


def test_enemy_count_grows_and_caps():
    counts = [waves.enemy_count(w) for w in (1, 2, 3, 10, 50)]
    assert counts == sorted(counts)
    assert counts[-1] == 60


def test_plan_is_deterministic_with_seed_and_sorted():
    a = waves.build_wave(3, rng=random.Random(7))
    b = waves.build_wave(3, rng=random.Random(7))
    assert a == b
    assert [s.at for s in a] == sorted(s.at for s in a)
    assert len(a) == waves.enemy_count(3)


def test_early_waves_only_drones():
    plan = waves.build_wave(1, rng=random.Random(3))
    assert {s.kind for s in plan} == {"drone"}


def test_later_waves_unlock_all_kinds():
    seen = set()
    for seed in range(20):
        seen |= {s.kind for s in waves.build_wave(8, rng=random.Random(seed))}
    assert seen == set(waves.ENEMY_KINDS)


def test_spawn_rate_compresses_plan():
    slow = waves.build_wave(4, spawn_rate=1.0, rng=random.Random(5))
    fast = waves.build_wave(4, spawn_rate=2.0, rng=random.Random(5))
    assert fast[-1].at < slow[-1].at


def test_x_positions_inside_playfield():
    for s in waves.build_wave(6, rng=random.Random(9)):
        assert 0.0 <= s.x_frac <= 1.0
