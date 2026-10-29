import pytest

from space_shooter.save import SaveData
from space_shooter.story import (
    SPEAKERS,
    LogDirector,
    LogEntry,
    StoryState,
    load_logs,
    load_logs_safe,
    parse_condition,
    state_from_save,
)


def S(loop=1, reached=0, echoes_lost=0, flags=()):
    return StoryState(loop=loop, reached=reached, echoes_lost=echoes_lost, flags=frozenset(flags))


@pytest.mark.parametrize(
    "text,state,expected",
    [
        ("always", S(), True),
        ("loop >= 3", S(loop=3), True),
        ("loop >= 3", S(loop=2), False),
        ("loop == 2", S(loop=2), True),
        ("reached < 2", S(reached=1), True),
        ("echoes_lost > 0", S(echoes_lost=1), True),
        ("flag:warden_seen", S(flags={"warden_seen"}), True),
        ("flag:warden_seen", S(), False),
        ("not flag:warden_seen", S(flags={"warden_seen"}), False),
        ("flag:a and reached > 1", S(flags={"a"}, reached=2), True),
        ("flag:a and reached > 1", S(flags={"a"}, reached=1), False),
    ],
)
def test_conditions(text, state, expected):
    assert parse_condition(text)(state) is expected


@pytest.mark.parametrize("bad", ["loop >> 3", "flag:", "health >= 2", "loop >= x", "", "loop >= 3 and"])
def test_bad_conditions_raise(bad):
    with pytest.raises(ValueError):
        parse_condition(bad)


def test_priority_and_unread():
    logs = [LogEntry("a", "pilot", ("x",), "always", 1), LogEntry("b", "pilot", ("y",), "always", 5)]
    d = LogDirector(logs, read=[])
    assert d.next_log(S()).id == "b"
    d.mark_read("b")
    assert d.next_log(S()).id == "a"
    d.mark_read("a")
    assert d.next_log(S()) is None and [e.id for e in d.unlocked()] == ["a", "b"]


def test_ineligible_logs_wait():
    d = LogDirector([LogEntry("late", "pilot", ("x",), "loop >= 3")], read=[])
    assert d.next_log(S(loop=2)) is None and d.next_log(S(loop=3)).id == "late"


def test_mark_read_shares_list_with_save():
    save = SaveData()
    d = LogDirector([LogEntry("a", "pilot", ("x",), "always")], read=save.read_logs)
    d.mark_read("a")
    d.mark_read("a")
    assert save.read_logs == ["a"] and d.get("a").speaker == "pilot" and d.get("zz") is None


def test_bundled_logs_valid():
    logs = load_logs()
    assert len(logs) == 26 and len({log.id for log in logs}) == 26
    assert all(1 <= len(log.lines) <= 3 and log.speaker in SPEAKERS for log in logs)
    assert logs[0].id == "a1_open"
    assert {"a1_end_1", "a1_end_2", "a1_end_3", "a1_first_echo_lost", "a1_warden_seen"} <= {log.id for log in logs}


def test_opening_log_is_first_choice():
    d = LogDirector(load_logs(), read=[])
    assert d.next_log(S()).id == "a1_open"


@pytest.mark.parametrize(
    "payload",
    [
        '[{"id":"a","speaker":"pilot","lines":["x"],"when":"loop >> 1"}]',
        '[{"id":"a","speaker":"pilot","lines":[],"when":"always"}]',
        '[{"id":"a","speaker":"pilot","lines":["1","2","3","4"],"when":"always"}]',
        '[{"id":"a","speaker":"ghost","lines":["x"],"when":"always"}]',
        '[{"id":"a","speaker":"pilot","lines":["x"],"when":"always"},'
        '{"id":"a","speaker":"pilot","lines":["y"],"when":"always"}]',
        "{not json",
    ],
)
def test_invalid_file_is_safe(tmp_path, payload):
    p = tmp_path / "logs.json"
    p.write_text(payload)
    with pytest.raises(ValueError):
        load_logs(p)
    logs, notice = load_logs_safe(p)
    assert logs == [] and notice


def test_echoes_lost_counted_from_flags():
    save = SaveData(flags={"echo_lost:3", "echo_lost:5", "warden_seen"})
    assert state_from_save(save).echoes_lost == 2
    assert state_from_save(save).flags == frozenset(save.flags)


def test_reached_uses_records_or_override():
    from space_shooter.save import Record

    save = SaveData(loop=4, records=[Record(1, 3, 0, 1.0), Record(2, 1, 0, 1.0)])
    assert state_from_save(save).reached == 3 and state_from_save(save).loop == 4
    assert state_from_save(save, reached=5).reached == 5


@pytest.mark.parametrize(
    "upcoming,expected", [(1, "a1_ash"), (2, "a1_graveyard"), (3, "a1_picket"), (4, "a1_last_light")]
)
def test_encounter_logs_play_in_the_drift_before_their_encounter(upcoming, expected):
    # drift_start passes the index of the encounter about to begin as `reached`
    earlier = {1: [], 2: ["a1_ash"], 3: ["a1_ash", "a1_graveyard"], 4: ["a1_ash", "a1_graveyard", "a1_picket"]}
    d = LogDirector(load_logs(), read=["a1_open", "a1_empty_channel", *earlier[upcoming]])
    assert d.next_log(S(reached=upcoming)).id == expected


@pytest.mark.parametrize(
    "flag,expected",
    [
        ("node_claimed", "m_first_claim"),
        ("node_lost", "m_first_lost"),
        ("hive_formed", "m_first_hive"),
        ("home_threatened", "m_home_threat"),
        ("gate_open", "m_gate_open"),
        ("war_lost", "m_war_lost"),
    ],
)
def test_campaign_logs_trigger(flag, expected):
    logs = load_logs()
    read = [log.id for log in logs if not log.id.startswith("m_")]
    d = LogDirector(logs, read=read)
    assert d.next_log(S(flags={flag})).id == expected
