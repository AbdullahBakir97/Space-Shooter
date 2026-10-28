from pathlib import Path

from space_shooter.settings_store import Settings, load_settings, save_settings


def test_defaults_when_missing(tmp_path: Path):
    assert load_settings(tmp_path) == Settings()


def test_round_trip(tmp_path: Path):
    s = Settings(sfx_volume=0.3, screen_shake=False, difficulty="hard")
    save_settings(s, tmp_path)
    assert load_settings(tmp_path) == s


def test_values_are_clamped_and_unknown_keys_ignored(tmp_path: Path):
    (tmp_path / "settings.json").write_text('{"sfx_volume": 7, "difficulty": "nightmare", "bogus": 1}')
    s = load_settings(tmp_path)
    assert s.sfx_volume == 1.0
    assert s.difficulty == "normal"


def test_corrupt_file(tmp_path: Path):
    (tmp_path / "settings.json").write_text("[1,2")
    assert load_settings(tmp_path) == Settings()
