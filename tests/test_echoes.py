import pytest

from space_shooter.echoes import (
    MAX_ACTIVE,
    MAX_STORED,
    EchoPlayback,
    EchoRecorder,
    EchoTrace,
    densest_cluster,
    select_roster,
    store_trace,
)


def test_recorder_samples_at_20hz_and_marks_fire():
    r = EchoRecorder(loop=3)
    r.begin_encounter(0)
    for i in range(61):
        if i == 10:
            r.note_fire()
        r.sample(i / 60, 100 + i, 200)
    t = r.finish(reached=0, duration=1.0)
    assert len(t.samples) == 21 and sum(s[4] for s in t.samples) == 1
    assert t.loop == 3 and t.duration == 1.0


def test_recorder_keeps_encounters_separate():
    r = EchoRecorder(loop=1)
    r.begin_encounter(0)
    r.sample(0.0, 1, 1)
    r.begin_encounter(1)
    r.sample(0.0, 2, 2)
    t = r.finish(reached=1, duration=5.0)
    assert [s[0] for s in t.samples] == [0, 1]


def test_recorder_records_loadout_changes_only():
    r = EchoRecorder(loop=1)
    r.begin_encounter(0)
    r.note_loadout({})
    r.sample(0.5, 0, 0)
    r.note_loadout({"wing_l": "turret"})
    r.note_loadout({"wing_l": "turret"})
    t = r.finish(0, 1.0)
    assert t.loadouts == [(0, 0.5, {"wing_l": "turret"})]


def test_playback_interpolates_and_reports_fire_once():
    t = EchoTrace(1, 0, 1.0, [(0, 0.0, 0, 0, False), (0, 0.05, 10, 0, True), (0, 0.1, 20, 0, False)], [])
    p = EchoPlayback(t)
    s = p.advance(0, 0.025)
    assert s.x == pytest.approx(5) and not s.fired
    assert p.advance(0, 0.06).fired and not p.advance(0, 0.07).fired


def test_playback_ends_at_last_sample():
    t = EchoTrace(1, 0, 0.1, [(0, 0.0, 0, 0, False), (0, 0.1, 20, 0, False)], [])
    s = EchoPlayback(t).advance(0, 5.0)
    assert s.ended and s.x == 20


def test_playback_not_ended_in_earlier_encounter():
    t = EchoTrace(1, 1, 2.0, [(0, 0.0, 0, 0, False), (0, 0.1, 5, 0, False), (1, 0.0, 9, 9, False)], [])
    p = EchoPlayback(t)
    assert not p.advance(0, 3.0).ended  # it went on to encounter 1; it just waits at its last point
    assert p.has_encounter(1) and not p.has_encounter(2)


def test_missing_encounter_returns_none():
    t = EchoTrace(1, 0, 0.1, [(0, 0.0, 0, 0, False)], [])
    assert EchoPlayback(t).advance(3, 1.0) is None


def test_loadout_follows_time():
    t = EchoTrace(1, 0, 2, [(0, 0.0, 0, 0, False), (0, 2.0, 0, 0, False)], [(0, 1.0, {"wing_l": "turret"})])
    p = EchoPlayback(t)
    assert p.advance(0, 0.5).loadout == {} and p.advance(0, 1.5).loadout == {"wing_l": "turret"}


def test_loadout_carries_into_next_encounter():
    t = EchoTrace(1, 1, 2, [(0, 0.0, 0, 0, False), (1, 0.0, 0, 0, False)], [(0, 1.0, {"fore_l": "slug"})])
    assert EchoPlayback(t).advance(1, 0.0).loadout == {"fore_l": "slug"}


def test_roster_furthest_then_most_recent():
    ts = [EchoTrace(i, reached, 30.0, [], []) for i, reached in enumerate([1, 4, 4, 2, 0, 3, 4])]
    assert [t.loop for t in select_roster(ts)] == [6, 2, 1, 5, 3]
    assert len(select_roster(ts)) == MAX_ACTIVE


def test_store_drops_short_and_caps():
    traces = []
    for i in range(15):
        traces = store_trace(traces, EchoTrace(i, 0, 10.0 + i, [], []))
    traces = store_trace(traces, EchoTrace(99, 0, 4.0, [], []))
    assert len(traces) == MAX_STORED and 99 not in [t.loop for t in traces]
    assert min(t.duration for t in traces) == 13.0


def test_densest_cluster():
    pts = [(0, 0), (10, 0), (0, 10), (500, 500)]
    cx, cy = densest_cluster(pts, 90)
    assert cx < 20 and cy < 20
    assert densest_cluster([], 90, fallback=(7, 8)) == (7, 8)


def test_trace_data_round_trip():
    t = EchoTrace(2, 1, 12.0, [(0, 0.0, 1.5, 2.5, True)], [(0, 0.0, {"fore_l": "slug*"})])
    back = EchoTrace.from_data(t.to_data())
    assert back.loop == 2 and back.loadouts == t.loadouts and back.samples[0][4] is True
