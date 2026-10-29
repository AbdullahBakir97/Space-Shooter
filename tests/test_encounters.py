import random

import pytest

from space_shooter.encounters import (
    DRIFT_TIME,
    ENCOUNTERS,
    WARDEN_INDEX,
    EncounterDirector,
    SpawnEntry,
    expand,
)


def test_six_encounters_warden_last():
    assert len(ENCOUNTERS) == 6 and ENCOUNTERS[WARDEN_INDEX].script[0].kind == "warden"
    assert [e.name for e in ENCOUNTERS] == [
        "COLD WAKE",
        "ASH SHELF",
        "GRAVEYARD",
        "PICKET LINE",
        "LAST LIGHT",
        "THE WARDEN",
    ]
    assert [e.time_cap for e in ENCOUNTERS] == [60, 70, 75, 80, 90, None]


@pytest.mark.parametrize("idx,total", [(0, 18), (1, 24), (2, 28), (3, 32), (4, 40)])
def test_script_totals(idx, total):
    assert sum(len(expand(e, random.Random(0))) for e in ENCOUNTERS[idx].script) == total


@pytest.mark.parametrize(
    "idx,kinds",
    [
        (0, {"drone"}),
        (1, {"drone", "zigzag"}),
        (2, {"diver", "drone"}),
        (3, {"gunner", "drone"}),
        (4, {"drone", "zigzag", "diver", "gunner"}),
    ],
)
def test_script_kinds(idx, kinds):
    assert {e.kind for e in ENCOUNTERS[idx].script} == kinds


def test_hazards_and_moments():
    assert ENCOUNTERS[1].hazards == ("ash",) and ENCOUNTERS[1].moments == ((25.0, "blackout"),)
    assert ENCOUNTERS[2].hazards == ("hulks",) and ENCOUNTERS[2].moments == ((30.0, "hulk_breach"),)
    assert ENCOUNTERS[4].hazards == ("debris", "hulks") and ENCOUNTERS[4].moments == ((45.0, "flare"),)
    assert ENCOUNTERS[0].moments == ((0.0, "first_drop"),)


def test_scripts_end_before_time_cap():
    for enc in ENCOUNTERS[:WARDEN_INDEX]:
        last = max(s.at for e in enc.script for s in expand(e, random.Random(0)))
        assert last < enc.time_cap - 10


def test_patterns_positions_in_range_and_ordered():
    for p in ("line", "vee", "column", "pincer", "scatter", "single"):
        spawns = expand(SpawnEntry(2.0, p, "drone", 5 if p != "single" else 1, 0.5), random.Random(1))
        assert spawns and all(0.0 <= s.x_frac <= 1.0 and s.at >= 2.0 for s in spawns)


def test_pincer_uses_both_edges():
    xs = {s.x_frac < 0.5 for s in expand(SpawnEntry(0, "pincer", "drone", 4, 0.5), random.Random(0))}
    assert xs == {True, False}


def test_unknown_pattern_raises():
    with pytest.raises(ValueError):
        expand(SpawnEntry(0, "spiral", "drone", 3, 0.5), random.Random(0))


def test_director_flow_drift_active_clear():
    d = EncounterDirector(random.Random(0))
    assert d.state == "drift" and ("drift_start", 0) in d.drain_events()
    d.update(DRIFT_TIME + 0.01, 0)
    assert d.state == "active" and ("encounter_start", 0) in d.drain_events()


def test_director_spawns_whole_script_then_advances():
    d = EncounterDirector(random.Random(0))
    d.update(DRIFT_TIME + 0.01, 0)
    spawned = []
    for _ in range(400):
        spawned += d.update(0.1, 0)
        if d.state == "drift":
            break
    assert len(spawned) == 18 and d.index == 1
    assert ("encounter_end", 0) in d.drain_events()


def test_time_cap_emits_retreat():
    d = EncounterDirector(random.Random(0))
    d.update(DRIFT_TIME + 0.01, 0)
    for _ in range(61 * 10):
        d.update(0.1, 5)
    assert ("retreat", 0) in d.drain_events()


def test_completing_warden_emits_run_complete():
    d = EncounterDirector(random.Random(0))
    d.index = WARDEN_INDEX
    d.update(DRIFT_TIME + 0.01, 0)
    d.update(0.1, 1)
    d.update(0.1, 0)
    assert ("run_complete", None) in d.drain_events() and d.state == "complete"
    assert d.update(1.0, 0) == []


def test_moment_fires_once():
    d = EncounterDirector(random.Random(0))
    d.index = 1
    d.update(DRIFT_TIME + 0.01, 0)
    events = []
    for _ in range(300):
        d.update(0.1, 3)
        events += d.drain_events()
    assert events.count(("moment", "blackout")) == 1


def clear_all(d, limit=4000):
    for _ in range(limit):
        d.update(0.1, 0)
        if d.state == "complete":
            return


def test_director_completes_short_route():
    d = EncounterDirector(random.Random(0), encounters=(ENCOUNTERS[0], ENCOUNTERS[1]))
    clear_all(d)
    events = d.drain_events()
    assert d.state == "complete" and ("run_complete", None) in events
    assert [v for e, v in events if e == "encounter_start"] == [0, 1]


def test_director_counts_cleared():
    d = EncounterDirector(random.Random(0), encounters=(ENCOUNTERS[0], ENCOUNTERS[1]))
    assert d.cleared == 0
    for _ in range(4000):
        d.update(0.1, 0)
        if d.index == 1:
            break
    assert d.cleared == 1
    clear_all(d)
    assert d.cleared == 2


def test_ambush_encounter():
    from space_shooter.encounters import AMBUSH

    assert AMBUSH.index == 6 and AMBUSH.time_cap == 25
    assert {e.kind for e in AMBUSH.script} <= {"drone", "zigzag"} and AMBUSH.script


def test_director_first_drift():
    import random

    from space_shooter.encounters import ENCOUNTERS, EncounterDirector

    d = EncounterDirector(random.Random(0), (ENCOUNTERS[0],), first_drift=1.5)
    d.update(1.4, 0)
    assert d.state == "drift"
    d.update(0.2, 0)
    assert d.state == "active"
