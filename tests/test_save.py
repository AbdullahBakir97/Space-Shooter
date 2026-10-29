import pytest

from space_shooter.save import (
    MAX_RECORDS,
    EchoData,
    Record,
    SaveData,
    add_record,
    load_save,
    pack_samples,
    unpack_samples,
    write_save,
)


def test_pack_round_trip():
    s = [(0, 0.0, 10.5, 20.25, False), (2, 1.05, 400.0, 500.0, True)]
    back = unpack_samples(pack_samples(s))
    assert [(e, f) for e, _, _, _, f in back] == [(0, False), (2, True)]
    assert [v for row in back for v in row[1:4]] == pytest.approx([v for row in s for v in row[1:4]], abs=1e-4)


def test_pack_empty():
    assert unpack_samples(pack_samples([])) == []


def test_round_trip(tmp_path):
    d = SaveData(loop=4, flags={"warden_seen"}, read_logs=["a1_open"])
    d.echoes.append(EchoData(3, 2, 64.0, pack_samples([(0, 0.0, 1, 2, True)]), []))
    assert write_save(d, tmp_path)
    back = load_save(tmp_path)
    assert back.loop == 4 and back.flags == {"warden_seen"} and back.echoes[0].loop == 3
    assert back.read_logs == ["a1_open"] and back.notice is None


def test_fresh_when_missing(tmp_path):
    d = load_save(tmp_path)
    assert d.loop == 1 and d.records == [] and d.notice is None


def test_migrates_high_scores(tmp_path):
    (tmp_path / "high_scores.json").write_text(
        '[{"name":"ZED","score":900,"wave":3,"difficulty":"hard","timestamp":0}]'
    )
    d = load_save(tmp_path)
    assert d.records == [Record(loop=0, reached=0, salvage=900, time=0.0, difficulty="hard")]


def test_corrupt_is_backed_up(tmp_path):
    (tmp_path / "save.json").write_text("{nope")
    d = load_save(tmp_path)
    assert d.loop == 1 and d.notice and (tmp_path / "save.json.bak").exists()


def test_newer_version_is_backed_up(tmp_path):
    (tmp_path / "save.json").write_text('{"version": 99}')
    d = load_save(tmp_path)
    assert d.notice and (tmp_path / "save.json.bak").exists()


def test_unwritable_directory_returns_false(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")  # a file, not a directory
    assert write_save(SaveData(), target) is False


def test_records_order_and_limit():
    d = SaveData()
    for i in range(12):
        add_record(d, Record(loop=i, reached=i % 6, salvage=i * 10, time=1.0))
    assert len(d.records) == MAX_RECORDS
    keys = [(r.reached, r.salvage) for r in d.records]
    assert keys == sorted(keys, reverse=True)


def test_add_record_returns_rank():
    d = SaveData()
    assert add_record(d, Record(1, 2, 100, 1.0)) == 1
    assert add_record(d, Record(2, 4, 50, 1.0)) == 1
    assert add_record(d, Record(3, 0, 10, 1.0)) == 3


def test_game_persist_sets_notice_when_unwritable(tmp_path, monkeypatch):
    import pygame

    from space_shooter.game import Game
    from space_shooter.settings_store import Settings

    game = Game(settings=Settings(sfx_volume=0.0), headless=True)
    blocker = tmp_path / "blocked"
    blocker.write_text("x")
    monkeypatch.setenv("SPACE_SHOOTER_DATA_DIR", str(blocker / "sub"))
    game.persist()
    assert game.save.notice == "Progress could not be saved."
    pygame.quit()


@pytest.mark.parametrize(
    "bad_echo",
    [
        {"loop": 2, "reached": 1, "duration": 30.0, "samples": "%%%not base64%%%", "loadouts": []},
        {"loop": 2, "reached": 1, "duration": 30.0, "samples": "QUJD", "loadouts": []},  # 3 bytes: truncated
        {"loop": 2, "reached": 1, "duration": 30.0, "samples": "", "loadouts": [{"t": 0.0, "parts": {}}]},
    ],
)
def test_damaged_echo_is_dropped_with_notice(tmp_path, bad_echo):
    import json

    good = {"loop": 3, "reached": 0, "duration": 12.0, "samples": pack_samples([(0, 0.0, 1, 2, False)]), "loadouts": []}
    (tmp_path / "save.json").write_text(json.dumps({"version": 1, "loop": 5, "echoes": [bad_echo, good]}))
    d = load_save(tmp_path)
    assert d.loop == 5 and [e.loop for e in d.echoes] == [3] and d.notice


def test_damaged_record_is_dropped(tmp_path):
    import json

    payload = {"version": 1, "loop": 2, "records": [{"loop": 1, "reached": "far", "salvage": 1, "time": 1.0}]}
    (tmp_path / "save.json").write_text(json.dumps(payload))
    d = load_save(tmp_path)
    assert d.records == [] and d.loop == 2 and d.notice
