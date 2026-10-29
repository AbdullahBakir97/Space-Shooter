import random

import pytest

from space_shooter.salvage import (
    DROP_BASE,
    PAIR_NAMES,
    PART_TYPES,
    PATCH_HULL,
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
    assert lo.patch_share() == pytest.approx(0.25)
    assert Loadout().patch_share() == pytest.approx(0.10)


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


def fitted(*specs):
    lo = Loadout()
    for kind, contact, *rare in specs:
        lo.attach(Part(kind, rare=bool(rare)), contact)
    return lo


FORE_L, FORE_R, WING_L, WING_R, AFT_L, AFT_R = (-14, -30), (14, -30), (-30, 2), (30, 2), (-16, 30), (16, 30)


def test_pairs_detected_in_type_order():
    lo = fitted(("thruster", AFT_L), ("thruster", AFT_R), ("turret", WING_L), ("turret", WING_R), ("slug", FORE_L))
    assert lo.pairs() == ["turret", "thruster"]
    assert PAIR_NAMES["turret"] == "TWIN TURRETS" and PAIR_NAMES["claw"] == "SCRAPPER"
    assert Loadout().pairs() == []


def test_heavy_every():
    assert Loadout().heavy_every() is None
    assert fitted(("slug", FORE_L)).heavy_every() == 4
    assert fitted(("slug", FORE_L), ("slug", FORE_R)).heavy_every() == 3


def test_bulkhead_tops_up_plates():
    lo = fitted(("armour", WING_L))
    assert lo.armour_hits() == 2 and lo.slots["wing_l"].armour_left == 2
    lo.absorb_hit(random.Random(0))
    lo.attach(Part("armour"), WING_R)
    assert lo.armour_hits() == 3
    assert lo.slots["wing_l"].armour_left == 3 and lo.slots["wing_r"].armour_left == 3


def test_dash_numbers_from_loadout():
    assert Loadout().dash_charges() == 0
    one = fitted(("thruster", AFT_L))
    assert one.dash_charges() == 1 and one.dash_recharge() == pytest.approx(2.5)
    two = fitted(("thruster", AFT_L), ("thruster", AFT_R, "rare"))
    assert two.dash_charges() == 2 and two.dash_recharge() == pytest.approx(1.5)
    scarred = fitted(("thruster", AFT_L, "rare"), ("thruster", AFT_R, "rare"))
    assert scarred.dash_recharge() == pytest.approx(1.0)


def test_turret_period_and_tractor_range():
    assert fitted(("turret", WING_L)).turret_period() == pytest.approx(0.5)
    assert fitted(("turret", WING_L), ("turret", WING_R)).turret_period() == pytest.approx(0.35)
    assert Loadout().tractor_range() == 0
    assert fitted(("tractor", AFT_L)).tractor_range() == 360
    assert fitted(("tractor", AFT_L), ("tractor", AFT_R)).tractor_range() >= 2000


def test_scrapper():
    assert not fitted(("claw", FORE_L)).drops_scarred()
    assert fitted(("claw", FORE_L), ("claw", FORE_R)).drops_scarred()


def test_patch_values():
    assert PATCH_HULL == 20
