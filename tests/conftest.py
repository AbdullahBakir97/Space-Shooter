import os

import pytest

# Headless SDL so the suite runs in CI and on machines without audio.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Never touch the real user data directory from tests."""
    monkeypatch.setenv("SPACE_SHOOTER_DATA_DIR", str(tmp_path / "data"))
    yield


@pytest.fixture(scope="session")
def display():
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((800, 640))
    yield screen
    pygame.quit()
