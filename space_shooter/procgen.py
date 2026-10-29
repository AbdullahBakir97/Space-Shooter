"""Procedurally generated art (and later, audio)."""

from __future__ import annotations

from functools import cache

import pygame

from space_shooter import assets
from space_shooter.config import SPRITE_SCALE
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM

# 6x6 pixel masks per part kind: "#" body, "+" highlight, "o" accent.
_PART_SHAPES: dict[str, tuple[str, ...]] = {
    "turret": ("..++..", ".#oo#.", "######", "#.##.#", ".####.", "..##.."),
    "slug": ("..++..", "..##..", ".####.", ".#oo#.", "######", "##..##"),
    "tractor": (".####.", "#....#", "#.oo.#", "#.oo.#", "#....#", ".####."),
    "armour": ("######", "#++++#", "#+##+#", "#+##+#", "#++++#", "######"),
    "thruster": (".####.", ".#++#.", "######", ".#oo#.", ".o..o.", "o....o"),
    "claw": ("#....#", "##..##", ".#oo#.", ".####.", "..##..", "..++.."),
}
_PART_COLOURS = {"#": STEEL_DIM, "+": STEEL, "o": RUST}


@assets.register_cache
@cache
def part_sprite(kind: str, rare: bool = False, scale: int = SPRITE_SCALE) -> pygame.Surface:
    rows = _PART_SHAPES.get(kind, _PART_SHAPES["armour"])
    surf = pygame.Surface((6, 6), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in _PART_COLOURS:
                colour = EMBER if (rare and ch == "o") else _PART_COLOURS[ch]
                surf.set_at((x, y), (*colour, 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def patch_sprite(scale: int = SPRITE_SCALE) -> pygame.Surface:
    rows = ("..##..", ".#++#.", "##++##", "##++##", ".#++#.", "..##..")
    surf = pygame.Surface((6, 6), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x, y), (*(BONE if ch == "+" else ASH), 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def hulk_sprite(seed: int, scale: int = SPRITE_SCALE) -> pygame.Surface:
    """A dead ship's broken hull: a jagged slab in steel_dim and rust."""
    import random

    rng = random.Random(seed)
    w, h = 16, 8
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        top = rng.randint(0, 2)
        bottom = h - rng.randint(0, 2)
        for y in range(top, bottom):
            colour = RUST if rng.random() < 0.18 else (STEEL if y == top else STEEL_DIM)
            surf.set_at((x, y), (*colour, 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def ash_cloud_sprite(seed: int) -> pygame.Surface:
    import random

    rng = random.Random(seed)
    surf = pygame.Surface((200, 130), pygame.SRCALPHA)
    puffs = [(100, 65, 48)] + [(rng.randint(45, 155), rng.randint(40, 90), rng.randint(18, 40)) for _ in range(24)]
    for x, y, r in puffs:
        puff = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(puff, (*ASH, 60), (r, r), r)
        surf.blit(puff, (x - r, y - r))  # blit blends, so overlapping puffs build density
    return surf


@assets.register_cache
@cache
def debris_sprite(seed: int, scale: int = 3) -> pygame.Surface:
    import random

    rng = random.Random(seed)
    surf = pygame.Surface((5, 5), pygame.SRCALPHA)
    for x in range(5):
        for y in range(5):
            if (x - 2) ** 2 + (y - 2) ** 2 <= 4 and rng.random() < 0.85:
                surf.set_at((x, y), (*(RUST if rng.random() < 0.4 else ASH), 255))
    return pygame.transform.scale_by(surf, scale)


@assets.register_cache
@cache
def warden_sprites(scale: int = SPRITE_SCALE) -> tuple[pygame.Surface, pygame.Surface]:
    """The Warden: a symmetric 48x32 machine body plus a separate ember eye layer."""
    import random

    rng = random.Random(1987)
    w, h, half = 48, 32, 24
    body = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(half):
        # silhouette: a wide crown tapering to a lower jaw, with ragged edges
        reach = 1.0 - (half - 1 - x) / half  # 0 at the outer edge, 1 at the centre
        top = int(10 - 8 * reach) + rng.randint(0, 1)
        bottom = int(14 + 16 * reach) - rng.randint(0, 2)
        for y in range(max(0, top), min(h, bottom)):
            roll = rng.random()
            if y in (top, top + 1):
                colour = STEEL
            elif roll < 0.12:
                colour = RUST
            elif roll < 0.2:
                colour = ASH
            else:
                colour = STEEL_DIM
            body.set_at((x, y), (*colour, 255))
            body.set_at((w - 1 - x, y), (*colour, 255))
    # the socket the eye sits in
    pygame.draw.circle(body, (6, 7, 12, 255), (half, 18), 5)
    eye = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(eye, (*EMBER, 255), (half, 18), 4)
    pygame.draw.circle(eye, (*BONE, 255), (half, 18), 1)
    if scale != 1:
        body = pygame.transform.scale_by(body, scale)
        eye = pygame.transform.scale_by(eye, scale)
    return body, eye


# --- recolouring -------------------------------------------------------------
def _recolour(name: str, fn, scale: int) -> pygame.Surface:
    small = assets.load_image(name, 1).copy()
    for x in range(small.get_width()):
        for y in range(small.get_height()):
            c = small.get_at((x, y))
            if c.a:
                small.set_at((x, y), fn(x, y, c))
    return pygame.transform.scale_by(small, scale) if scale != 1 else small


def _tone(colour: pygame.Color, hue: float, sat: float) -> pygame.Color:
    _, _, v, a = colour.hsva
    out = pygame.Color(0)
    out.hsva = (hue, sat, v, a)
    return out


_RUST_HUE = pygame.Color(*RUST).hsva[0]
_STEEL_HUE = pygame.Color(*STEEL).hsva[0]
# the bright orange "eye" pixels of the enemy art become each kind's accent
_ENEMY_ACCENTS = {"drone": (200, 96, 60), "zigzag": STEEL, "diver": ASH, "gunner": EMBER}


@assets.register_cache
@cache
def scarred_variant(name: str, kind: str, scale: int = SPRITE_SCALE) -> pygame.Surface:
    """Enemy art pulled toward rust, with one accent colour and scorch marks."""
    import random
    import zlib

    accent = _ENEMY_ACCENTS.get(kind, ASH)

    def fn(x, y, c):
        h, s, v, a = c.hsva
        if s > 80 and v > 90 and 20 <= h <= 45:  # the orange accent pixels
            return pygame.Color(*accent, c.a)
        rusted = _tone(c, _RUST_HUE, min(60.0, s * 0.9))
        h2, s2, v2, a2 = rusted.hsva
        rusted.hsva = (h2, s2, v2 * 0.8, a2)  # darker and browner, not salmon
        return rusted

    img = _recolour(name, fn, 1)
    rng = random.Random(zlib.crc32(f"{name}:{kind}".encode()))
    opaque = [(x, y) for x in range(img.get_width()) for y in range(img.get_height()) if img.get_at((x, y)).a]
    for x, y in rng.sample(opaque, k=min(len(opaque), rng.randint(2, 4))):
        img.set_at((x, y), (22, 18, 16, 255))
    return pygame.transform.scale_by(img, scale) if scale != 1 else img


@assets.register_cache
@cache
def tug_frames(scale: int = SPRITE_SCALE) -> list[pygame.Surface]:
    """The player's tug in cold steel instead of the source art's bright blue."""
    return [
        _recolour(n, lambda x, y, c: _tone(c, _STEEL_HUE, min(c.hsva[1], 40)), scale)
        for n in assets.SPRITE_NAMES["player"]
    ]


@assets.register_cache
@cache
def explosion_frames(scale: int = SPRITE_SCALE) -> list[pygame.Surface]:
    """The four explosion frames in ember, rust and char instead of arcade yellow."""
    mapping = {(242, 252, 36): EMBER, (254, 167, 17): RUST, (251, 59, 2): (70, 30, 22)}

    def fn(x, y, c):
        return pygame.Color(*mapping.get((c.r, c.g, c.b), ASH), c.a)

    return [_recolour(n, fn, scale) for n in assets.SPRITE_NAMES["explode"]]


@assets.register_cache
@cache
def cockpit_overlay(size: tuple[int, int]) -> pygame.Surface:
    """Scanlines plus a cracked frame around the edges of the view."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(surf, (0, 0, 0, 18), (0, y), (w, y))
    edge = (*STEEL_DIM, 200)
    pygame.draw.rect(surf, edge, (0, 0, w, h), 4)
    for corner, sign in (((0, 0), (1, 1)), ((w, 0), (-1, 1)), ((0, h), (1, -1)), ((w, h), (-1, -1))):
        cx, cy = corner
        sx, sy = sign
        pygame.draw.line(surf, edge, (cx, cy + sy * 70), (cx + sx * 70, cy), 3)
    crack = [(w - 4, 140), (w - 22, 152), (w - 30, 178), (w - 46, 186)]
    pygame.draw.lines(surf, (*STEEL, 120), False, crack, 1)
    crack2 = [(4, h - 160), (18, h - 150), (24, h - 128)]
    pygame.draw.lines(surf, (*STEEL, 120), False, crack2, 1)
    return surf


# --- audio -------------------------------------------------------------------
def _mixer_format() -> tuple[int, int] | None:
    init = pygame.mixer.get_init()
    if not init:
        return None
    freq, _size, channels = init
    return freq, channels


@cache
def _drone_pcm(seconds: float, freq: int, channels: int) -> bytes:
    import array
    import math
    import random

    n = int(seconds * freq)
    # round each tone so it completes whole cycles: the buffer loops without a click
    f1 = round(55.0 * seconds) / seconds
    f2 = round(55.7 * seconds) / seconds
    f3 = round(27.5 * seconds) / seconds
    rng = random.Random(7)
    noise, lp = [], 0.0
    for _ in range(n):
        lp += 0.02 * (rng.uniform(-1, 1) - lp)
        noise.append(lp)
    fade = int(0.25 * freq)  # crossfade the noise ends so its seam is silent too
    for i in range(fade):
        k = i / fade
        noise[i] = noise[i] * k + noise[n - fade + i] * (1 - k)
    out = array.array("h")
    tau = 2 * math.pi
    for i in range(n):
        t = i / freq
        swell = 0.75 + 0.25 * math.sin(tau * t / seconds)
        v = 0.30 * math.sin(tau * f1 * t) + 0.24 * math.sin(tau * f2 * t) + 0.16 * math.sin(tau * f3 * t)
        v = (v * swell + 0.9 * noise[i]) * 0.55
        sample = int(max(-1.0, min(1.0, v)) * 32767)
        out.extend([sample] * channels)
    return out.tobytes()


def drone_sound(seconds: float = 8.0, rate: int | None = None) -> pygame.mixer.Sound | None:
    """A low, slowly beating drone bed that loops seamlessly. None without a mixer."""
    fmt = _mixer_format()
    if fmt is None:
        return None
    freq, channels = fmt
    return pygame.mixer.Sound(buffer=_drone_pcm(float(seconds), rate or freq, channels))


@cache
def _static_pcm(seconds: float, freq: int, channels: int) -> bytes:
    import array
    import random

    rng = random.Random(3)
    n = int(seconds * freq)
    out = array.array("h")
    hp = prev = 0.0
    for i in range(n):
        x = rng.uniform(-1, 1)
        hp = 0.9 * (hp + x - prev)  # high-passed hiss
        prev = x
        env = min(1.0, i / (0.03 * freq), (n - i) / (0.15 * freq))
        crackle = 1.0 if rng.random() > 0.002 else 3.0
        out.extend([int(max(-1.0, min(1.0, hp * 0.18 * env * crackle)) * 32767)] * channels)
    return out.tobytes()


def static_sound(seconds: float = 0.6) -> pygame.mixer.Sound | None:
    fmt = _mixer_format()
    if fmt is None:
        return None
    return pygame.mixer.Sound(buffer=_static_pcm(float(seconds), *fmt))


@cache
def _tone_pcm(freq_hz: float, seconds: float, freq: int, channels: int) -> bytes:
    import array
    import math

    n = int(seconds * freq)
    out = array.array("h")
    for i in range(n):
        env = min(1.0, i / (0.2 * freq)) * (1 - i / n) ** 1.5
        v = 0.5 * math.sin(2 * math.pi * freq_hz * i / freq) * env
        out.extend([int(v * 32767)] * channels)
    return out.tobytes()


def tone(freq_hz: float, seconds: float) -> pygame.mixer.Sound | None:
    """A single low fading tone (Act 1's ending has no fanfare)."""
    fmt = _mixer_format()
    if fmt is None:
        return None
    return pygame.mixer.Sound(buffer=_tone_pcm(float(freq_hz), float(seconds), *fmt))
