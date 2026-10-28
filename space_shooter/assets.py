"""Image, font and sound loading with caching, scaling and safe fallbacks."""

from __future__ import annotations

from functools import cache

import pygame

from space_shooter.config import SPRITE_SCALE
from space_shooter.paths import IMAGES_DIR, SOUNDS_DIR

SPRITE_NAMES = {
    "player": ["player0", "player1", "player2"],
    "enemy": ["enemy0", "enemy1"],
    "explode": ["explode0", "explode1", "explode2", "explode3"],
}
DIGIT_NAMES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def _placeholder(size: tuple[int, int]) -> pygame.Surface:
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((255, 0, 255))  # debug placeholder for a missing image
    return surf


@cache
def load_image(name: str, scale: int = SPRITE_SCALE) -> pygame.Surface:
    """Load ``images/<name>.png`` scaled by an integer factor (nearest neighbour).

    Missing files yield a magenta placeholder so the game keeps running.
    """
    path = IMAGES_DIR / f"{name}.png"
    try:
        raw = pygame.image.load(str(path))
    except (pygame.error, FileNotFoundError):
        raw = _placeholder((12, 16))
    if pygame.display.get_surface() is not None:
        raw = raw.convert_alpha()
    if scale != 1:
        raw = pygame.transform.scale_by(raw, scale)
    return raw


@cache
def silhouette(name: str, colour: tuple[int, int, int], scale: int = SPRITE_SCALE) -> pygame.Surface:
    """A flat-colour version of a sprite (used for hit flashes)."""
    base = load_image(name, scale).copy()
    mask = pygame.mask.from_surface(base)
    return mask.to_surface(setcolor=(*colour, 255), unsetcolor=(0, 0, 0, 0))


@cache
def font(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, size)


_EXTRA_CACHES: list = []


def register_cache(fn):
    """Decorator: make ``clear_caches`` also clear this lru_cache'd function."""
    _EXTRA_CACHES.append(fn)
    return fn


def clear_caches() -> None:
    """Drop cached surfaces/fonts; required after pygame is re-initialised."""
    for fn in (load_image, silhouette, font, load_sound, *_EXTRA_CACHES):
        fn.cache_clear()


@cache
def load_sound(key: str, relative: str) -> pygame.mixer.Sound | None:
    """Return a Sound or None when the mixer is unavailable or the file is missing."""
    if not pygame.mixer.get_init():
        return None
    try:
        return pygame.mixer.Sound(str(SOUNDS_DIR / relative))
    except (pygame.error, FileNotFoundError):
        return None
