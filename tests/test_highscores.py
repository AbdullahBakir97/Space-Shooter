from pathlib import Path

from space_shooter import highscores
from space_shooter.highscores import MAX_ENTRIES, HighScoreTable


def test_empty_table():
    t = HighScoreTable()
    assert t.best == 0
    assert t.qualifies(1)
    assert not t.qualifies(0)
    assert t.rank_of(10) == 1


def test_add_orders_and_truncates():
    t = HighScoreTable()
    for s in range(1, 15):
        t.add("abc", s * 100, wave=s)
    assert len(t.entries) == MAX_ENTRIES
    assert t.best == 1400
    assert [e.score for e in t.entries] == sorted((e.score for e in t.entries), reverse=True)
    assert not t.qualifies(500)  # lowest kept is 500, ties don't qualify
    assert t.qualifies(501)


def test_name_is_cleaned():
    t = HighScoreTable()
    t.add("  bob the builder ", 10, 1)
    assert t.entries[0].name == "BOB"
    t.add("", 20, 1)
    assert t.entries[0].name == "AAA"


def test_rank_of_with_ties():
    t = HighScoreTable()
    t.add("A", 300, 1)
    t.add("B", 200, 1)
    assert t.rank_of(300) == 2
    assert t.rank_of(250) == 2
    assert t.rank_of(400) == 1


def test_round_trip(tmp_path: Path):
    t = HighScoreTable()
    t.add("ZED", 999, 3, "hard")
    t.save(tmp_path)
    loaded = HighScoreTable.load(tmp_path)
    assert loaded.entries[0].name == "ZED"
    assert loaded.entries[0].difficulty == "hard"


def test_corrupt_file_is_ignored(tmp_path: Path):
    (tmp_path / highscores.SCORES_FILE).write_text("{not json")
    assert HighScoreTable.load(tmp_path).entries == []


def test_legacy_import(tmp_path: Path, monkeypatch):
    legacy = tmp_path / "high_scores.txt"
    legacy.write_text("120\n0\nabc\n340\n")
    monkeypatch.setattr(highscores, "LEGACY_FILE", legacy)
    t = HighScoreTable.load(tmp_path)
    assert [e.score for e in t.entries] == [340, 120]
