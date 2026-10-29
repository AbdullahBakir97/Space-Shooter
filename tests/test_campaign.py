import json
import random

import pytest

from space_shooter.campaign import (
    FORTIFY_COST,
    MAX_REQUISITION,
    PART_COST,
    CampaignState,
    TurnReport,
    apply_run,
    fortify,
    load_system,
    locked,
    new_campaign,
    requisition,
    route_encounters,
    spread_count,
    swarm_turn,
    valid_route,
)
from space_shooter.encounters import ENCOUNTERS


@pytest.fixture(scope="module")
def system():
    return load_system()


def owners(state, who):
    return {n for n, o in state.owner.items() if o == who}


def test_system_loads_and_validates(system):
    assert len(system.nodes) == 14
    assert system.nodes["c2"].template == 5 and system.nodes["m1"].ground
    assert system.neighbours("home") == {"o1", "o2"}
    assert all(a in system.neighbours(b) for a in system.nodes for b in system.neighbours(a))
    dist = {n: system.distance_to_home(n) for n in ("o1", "o3", "m1", "m5", "c1", "c2")}
    assert dist == {"o1": 1, "o3": 2, "m1": 2, "m5": 3, "c1": 4, "c2": 5}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["nodes"].append(dict(d["nodes"][1])),  # duplicate id
        lambda d: d["lanes"].append(["o1", "nowhere"]),  # lane to an unknown node
        lambda d: d["nodes"].__setitem__(1, {**d["nodes"][1], "template": 9}),  # bad template
        lambda d: d["nodes"].pop(0),  # no home
    ],
)
def test_bad_system_rejected(tmp_path, mutate):
    from space_shooter.campaign import SYSTEM_PATH

    data = json.loads(SYSTEM_PATH.read_text())
    mutate(data)
    path = tmp_path / "system.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_system(path)


def test_new_campaign_owners(system):
    s = new_campaign(system)
    assert owners(s, "player") == {"home"} and owners(s, "swarm") == {"o5", "o6"}
    assert s.status == "active" and s.turn == 0 and s.salvage == 0 and s.requisition == []


def test_route_rules(system):
    s = new_campaign(system)
    assert valid_route(system, s, ["o1"])
    assert valid_route(system, s, ["o1", "o3"])
    assert valid_route(system, s, ["o1", "m1", "m5"])
    assert valid_route(system, s, ["o2", "o4", "o6"])  # attacking swarm ground is allowed
    for bad in ([], ["o3"], ["home"], ["o1", "o1"], ["o1", "m1", "m5", "m3"], ["o1", "m5"], ["zz"]):
        assert not valid_route(system, s, bad), bad
    s.owner["o1"] = "player"
    assert not valid_route(system, s, ["o1"])  # already yours
    assert valid_route(system, s, ["o3"])  # adjacent to ground you hold


def test_gate_locked_until_every_middle_world(system):
    s = new_campaign(system)
    for n in ("m1", "m2", "m3", "m5"):
        s.owner[n] = "player"
    assert locked(system, s, "c1") and locked(system, s, "c2")
    assert not valid_route(system, s, ["c1"])
    s.owner["m4"] = "player"
    assert not locked(system, s, "c1") and locked(system, s, "c2")
    assert valid_route(system, s, ["c1", "c2"])


def test_route_encounter_twists(system):
    s = new_campaign(system)
    s.hive_age["o6"] = 3
    plain, swarmed, hive = route_encounters(system, s, ["o1", "o5", "o6"])
    assert plain.index == 0 and plain.name == "COLD WAKE FIELD" and plain.hull == 1.0
    assert swarmed.index == 2 and swarmed.hull == pytest.approx(1.25)
    base = ENCOUNTERS[3]
    assert hive.hull == pytest.approx(1.5)
    assert [e.at for e in hive.script] == pytest.approx([e.at * 0.8 for e in base.script])


def test_apply_run_claims_and_earns(system):
    s = new_campaign(system)
    report = apply_run(system, s, ["o1", "m1"], cleared=2, run_salvage=500, warden_killed=False, rng=random.Random(0))
    assert {"o1", "m1"} <= owners(s, "player") and report.claimed == ["o1", "m1"]
    assert report.salvage_gained == 500 + 100 + 300 and s.salvage == 900
    assert s.turn == 1 and isinstance(report, TurnReport)


def test_partial_run_claims_prefix(system):
    s = new_campaign(system)
    apply_run(system, s, ["o1", "m1"], cleared=1, run_salvage=0, warden_killed=False, rng=random.Random(0))
    assert s.owner["o1"] == "player" and s.owner["m1"] != "player"


def test_swarm_spreads_toward_home(system):
    s = new_campaign(system)
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    new = owners(s, "swarm") - {"o5", "o6"}
    assert len(new) == 1 and new <= {"o3", "o4"}


def test_spread_count_grows(system):
    s = new_campaign(system)
    assert [spread_count(CampaignState(**{**s.__dict__, "turn": t})) for t in (0, 5, 6, 12, 20)] == [1, 1, 2, 3, 3]
    s.hive_age = {"o5": 3, "o6": 4}
    assert spread_count(s) == 2


def surrounded(system, s):
    """Leave home and o1 as the swarm's only targets."""
    s.owner = {n: "swarm" for n in system.nodes}
    s.owner.update({"home": "player", "o1": "player"})


def test_fortified_node_survives_once(system):
    s = new_campaign(system)
    surrounded(system, s)
    s.fortified.add("o1")
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    assert s.owner["o1"] == "player" and "o1" not in s.fortified and report.fortify_spent == ["o1"]


def test_swarm_takes_empty_space_before_player_ground(system):
    s = new_campaign(system)
    s.owner.update({"o1": "player", "o3": "swarm"})
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    assert s.owner["o1"] == "player" and report.lost == [] and len(report.swarm_took) == 1


def test_swarm_takes_player_ground(system):
    s = new_campaign(system)
    surrounded(system, s)
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    assert s.owner["o1"] == "swarm" and report.lost == ["o1"] and report.home_threatened
    assert s.owner["home"] == "player"


def test_hive_forms_after_three_turns(system):
    s = new_campaign(system)
    formed = []
    for _ in range(3):
        report = TurnReport()
        s.fortified.update({"home", "o1", "o2"})  # keep the front away from home for this test
        swarm_turn(system, s, random.Random(1), report)
        s.turn += 1
        formed += report.hives
    assert {"o5", "o6"} <= set(formed) and s.hive_age["o5"] >= 3


def test_retaken_hive_is_cleared(system):
    s = new_campaign(system)
    s.hive_age["o5"] = 4
    s.owner["o3"] = "player"
    apply_run(system, s, ["o5"], cleared=1, run_salvage=0, warden_killed=False, rng=random.Random(0))
    assert s.owner["o5"] == "player" and s.hive_age.get("o5", 0) == 0


def test_home_is_the_last_stand(system):
    s = new_campaign(system)
    s.owner.update({"o1": "swarm", "o2": "swarm"})
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    assert s.owner["home"] == "player" and s.status == "active" and report.home_threatened


def test_home_taken_loses(system):
    s = new_campaign(system)
    s.owner = {n: ("player" if n == "home" else "swarm") for n in system.nodes}
    report = TurnReport()
    swarm_turn(system, s, random.Random(0), report)
    assert s.owner["home"] == "swarm" and s.status == "lost" and report.status == "lost"


def test_warden_win(system):
    s = new_campaign(system)
    for n in ("m1", "m2", "m3", "m4", "c1"):
        s.owner[n] = "player"
    before = dict(s.owner)
    report = apply_run(system, s, ["c2"], cleared=1, run_salvage=0, warden_killed=True, rng=random.Random(0))
    assert s.status == "won" and report.status == "won"
    assert {k: v for k, v in s.owner.items() if k != "c2"} == {k: v for k, v in before.items() if k != "c2"}


def test_requisition_and_fortify_costs(system):
    s = new_campaign(system)
    assert (PART_COST, FORTIFY_COST, MAX_REQUISITION) == (800, 1000, 2)
    assert not requisition(s, "turret")  # no salvage yet
    s.salvage = 2600
    assert requisition(s, "turret") and requisition(s, "slug")
    assert not requisition(s, "claw")  # two at most
    assert not requisition(s, "laser")
    assert s.requisition == ["turret", "slug"] and s.salvage == 1000
    assert not fortify(s, "o1")  # not yours
    assert fortify(s, "home") and s.salvage == 0 and "home" in s.fortified
    s.salvage = 5000
    assert not fortify(s, "home")  # already fortified


def test_state_round_trip(system):
    s = new_campaign(system)
    s.salvage, s.turn, s.requisition = 1234, 7, ["armour"]
    s.fortified.add("home")
    s.hive_age["o5"] = 2
    back = CampaignState.from_dict(json.loads(json.dumps(s.to_dict())))
    assert back == s


# -- free flight ---------------------------------------------------------------
def test_can_engage_rules(system):
    from space_shooter.campaign import can_engage

    s = new_campaign(system)
    assert can_engage(system, s, "o1") and can_engage(system, s, "m5")  # no adjacency needed in flight
    assert not can_engage(system, s, "home")
    s.owner["o1"] = "player"
    assert not can_engage(system, s, "o1")
    assert not can_engage(system, s, "c1") and not can_engage(system, s, "c2")
    for n in system.ring_ids("middle"):
        s.owner[n] = "player"
    assert can_engage(system, s, "c1") and not can_engage(system, s, "c2")
    s.owner["c1"] = "player"
    assert can_engage(system, s, "c2")


def test_encounter_for_twists(system):
    from space_shooter.campaign import encounter_for

    s = new_campaign(system)
    s.hive_age["o6"] = 3
    plain, swarmed, hive = (encounter_for(system, s, n) for n in ("o1", "o5", "o6"))
    assert plain.name == "COLD WAKE FIELD" and plain.hull == 1.0
    assert swarmed.hull == pytest.approx(1.25)
    assert hive.hull == pytest.approx(1.5)
    assert [e.at for e in hive.script] == pytest.approx([e.at * 0.8 for e in ENCOUNTERS[3].script])


def test_claim_records_once(system):
    from space_shooter.campaign import claim

    s = new_campaign(system)
    s.hive_age["o5"] = 4
    claim(s, "o1")
    claim(s, "o1")
    claim(s, "o5")
    assert s.owner["o1"] == "player" and s.claimed_this_loop == ["o1", "o5"] and "o5" not in s.hive_age


def test_end_turn_dock_banks_all(system):
    from space_shooter.campaign import claim, end_turn

    s = new_campaign(system)
    claim(s, "o1")
    report = end_turn(system, s, carried=500, died=False, warden_killed=False, rng=random.Random(0))
    assert report.salvage_gained == 600 and s.salvage == 600
    assert report.claimed == ["o1"] and s.claimed_this_loop == [] and s.turn == 1


def test_end_turn_death_banks_half(system):
    from space_shooter.campaign import end_turn

    s = new_campaign(system)
    report = end_turn(system, s, carried=501, died=True, warden_killed=False, rng=random.Random(0))
    assert report.salvage_gained == 250 and s.salvage == 250


def test_end_turn_warden_wins(system):
    from space_shooter.campaign import end_turn

    s = new_campaign(system)
    before = dict(s.owner)
    report = end_turn(system, s, carried=0, died=False, warden_killed=True, rng=random.Random(0))
    assert s.status == "won" and report.status == "won" and s.owner == before


def test_patrol_count(system):
    from space_shooter.campaign import patrol_count

    s = new_campaign(system)
    assert patrol_count(s) == 1
    for n in ("o1", "o2", "o3", "o4", "m1", "m2", "m3"):
        s.owner[n] = "swarm"
    s.hive_age.update({"o5": 3, "o6": 3, "o3": 3})
    assert patrol_count(s) == 6


def test_claimed_this_loop_round_trips(system):
    s = new_campaign(system)
    s.claimed_this_loop = ["o1"]
    assert CampaignState.from_dict(s.to_dict()).claimed_this_loop == ["o1"]
    raw = s.to_dict()
    del raw["claimed_this_loop"]
    assert CampaignState.from_dict(raw).claimed_this_loop == []


def test_damaged_state_rejected(system):
    with pytest.raises(ValueError):
        CampaignState.from_dict({"owner": [1, 2]})
    with pytest.raises(ValueError):
        CampaignState.from_dict({"owner": {"home": "player"}, "hive_age": [3]})
    raw = new_campaign(system).to_dict()
    raw["requisition"] = ["bogus", "claw"]
    assert CampaignState.from_dict(raw).requisition == ["claw"]
