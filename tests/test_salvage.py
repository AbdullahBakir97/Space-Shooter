import random

import pytest

from space_shooter.salvage import (
    DROP_BASE,
    PART_TYPES,
    SLOTS,
    Loadout,
    Part,
    part_from_code,
    roll_drop,
)


def test_part_table_matches_spec():
    def kinds(*prefixes):
        return tuple(s for s in SLOTS if s.split("_")[0] in prefixes)

    assert PART_TYPES["turret"].slots == kinds("wing", "aft")
    assert PART_TYPES["slug"].slots == kinds("fore")
    assert PART_TYPES["tractor"].slots == kinds("aft")
    assert PART_TYPES["armour"].slots == SLOTS
    assert PART_TYPES["thruster"].slots == kinds("aft")
    assert PART_TYPES["claw"].slots == kinds("fore")


def test_slot_validity():
    lo = Loadout()
    slot, ejected = lo.attach(Part("slug"), contact=(-20, -40))
    assert slot == "fore_l" and ejected is None
    with pytest.raises(ValueError):
        Loadout().attach(Part("unknown"), (0, 0))


def test_closest_free_valid_slot():
    lo = Loadout()
    lo.attach(Part("armour"), (30, 30))
    assert lo.slots["aft_r"].kind == "armour"


def test_full_valid_slots_replace_oldest_and_eject():
    lo = Loadout()
    lo.attach(Part("slug"), (-14, -30))
    lo.attach(Part("claw"), (14, -30))
    slot, ejected = lo.attach(Part("slug", rare=True), (14, -30))
    assert ejected.kind == "slug" and slot == "fore_l"
    assert lo.slots["fore_l"].rare


def test_armour_absorbs_before_knock():
    lo = Loadout()
    lo.attach(Part("armour"), (0, 0))
    lo.attach(Part("turret"), (-30, 2))
    rng = random.Random(0)
    assert [lo.absorb_hit(rng).kind for _ in range(2)] == ["armour", "armour"]
    assert lo.count("armour") == 0  # plate destroyed after 2 hits


def test_knock_rate_close_to_35_percent():
    rng = random.Random(1)
    knocked = 0
    for _ in range(2000):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        outcome = lo.absorb_hit(rng)
        if outcome.kind == "knocked":
            knocked += 1
            assert outcome.part.kind == "turret" and lo.count("turret") == 0
    assert 0.31 < knocked / 2000 < 0.39


def test_empty_loadout_always_hull():
    assert Loadout().absorb_hit(random.Random(0)).kind == "hull"


def test_thruster_caps_at_two():
    lo = Loadout()
    lo.attach(Part("thruster"), (-16, 30))
    lo.attach(Part("thruster"), (16, 30))
    assert lo.speed_multiplier() == pytest.approx(1.30)
    lo2 = Loadout()
    lo2.attach(Part("thruster", rare=True), (-16, 30))
    lo2.attach(Part("thruster", rare=True), (16, 30))
    assert lo2.speed_multiplier() == pytest.approx(1.30)


def test_claw_raises_drop_chance_and_patch_share():
    lo = Loadout()
    lo.attach(Part("claw"), (14, -30))
    assert lo.drop_chance(DROP_BASE) == pytest.approx(0.27)
    assert lo.patch_share() == pytest.approx(0.35)
    assert Loadout().patch_share() == pytest.approx(0.2)


def test_roll_drop_distribution():
    rng = random.Random(4)
    results = [roll_drop(rng, 1.0) for _ in range(5000)]
    assert 0.17 < results.count("patch") / 5000 < 0.23 and None not in results
    assert set(results) - {"patch"} <= set(PART_TYPES)
    assert roll_drop(random.Random(0), 0.0) is None


def test_codes_round_trip_ignores_unknown():
    lo = Loadout()
    lo.attach(Part("turret", rare=True), (-30, 2))
    assert lo.to_codes() == {"wing_l": "turret*"}
    assert Loadout.from_codes(lo.to_codes() | {"aft_l": "laser"}).to_codes() == lo.to_codes()
    assert part_from_code("slug*") == Part("slug", rare=True)
    assert part_from_code("laser") is None
