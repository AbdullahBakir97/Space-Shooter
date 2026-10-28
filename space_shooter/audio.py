"""Sound playback with a master volume and a no-audio fallback."""

from __future__ import annotations

import pygame

from space_shooter import assets
from space_shooter.config import SOUND_FILES, SOUND_VOLUMES


def init_mixer() -> bool:
    """Initialise the mixer; return False (without raising) if no device exists."""
    if pygame.mixer.get_init():
        return True
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(24)
        return True
    except pygame.error:
        return False


class AudioManager:
    def __init__(self, volume: float = 0.8) -> None:
        self.enabled = init_mixer()
        self._volume = volume
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._loops: dict[str, pygame.mixer.Channel | None] = {}
        if self.enabled:
            for key, rel in SOUND_FILES.items():
                self._sounds[key] = assets.load_sound(key, rel)
            self.set_volume(volume)

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, volume: float) -> None:
        self._volume = min(1.0, max(0.0, volume))
        for key, snd in self._sounds.items():
            if snd is not None:
                snd.set_volume(self._volume * SOUND_VOLUMES.get(key, 1.0))

    def play(self, key: str) -> None:
        snd = self._sounds.get(key)
        if snd is not None and self._volume > 0:
            snd.play()

    def loop(self, key: str) -> None:
        """Start a looping sound if it is not already playing."""
        snd = self._sounds.get(key)
        if snd is None or self._volume <= 0:
            return
        ch = self._loops.get(key)
        if ch is None or not ch.get_busy():
            self._loops[key] = snd.play(loops=-1)

    def stop(self, key: str) -> None:
        ch = self._loops.pop(key, None)
        if ch is not None:
            ch.stop()

    def stop_all_loops(self) -> None:
        for key in list(self._loops):
            self.stop(key)
