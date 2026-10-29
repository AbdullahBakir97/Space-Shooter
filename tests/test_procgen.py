import pygame
import pytest

from space_shooter import audio, config, procgen
from space_shooter.palette import EMBER, STEEL, STEEL_DIM

pytestmark = pytest.mark.usefixtures("display")


def test_scarred_variant_size_and_determinism():
    a, b = procgen.scarred_variant("enemy0", "drone"), procgen.scarred_variant("enemy0", "drone")
    assert a.get_size() == (48, 64)
    assert pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def test_scarred_variants_differ_by_kind():
    kinds = ["drone", "zigzag", "diver", "gunner"]
    images = {pygame.image.tobytes(procgen.scarred_variant("enemy0", k), "RGBA") for k in kinds}
    assert len(images) == 4


def test_scarred_variant_has_no_bright_saturated_pixels():
    img = procgen.scarred_variant("enemy0", "drone", scale=1)
    for x in range(img.get_width()):
        for y in range(img.get_height()):
            c = img.get_at((x, y))
            if c.a and c != pygame.Color(*EMBER):
                assert c.hsva[1] <= 75  # desaturated except the ember accent


def test_tug_frames_are_steel_toned():
    frames = procgen.tug_frames(scale=1)
    assert len(frames) == 3
    pixels = [frames[0].get_at((x, y)) for x in range(12) for y in range(16)]
    tinted = [c.hsva for c in pixels if c.a and c.hsva[1] > 10]
    steel_hue = pygame.Color(*STEEL).hsva[0]
    assert tinted and all(abs(h - steel_hue) < 20 and s <= 50 for h, s, _, _ in tinted)


def test_cockpit_overlay_is_mostly_transparent():
    overlay = procgen.cockpit_overlay((800, 640))
    assert overlay.get_size() == (800, 640)
    assert overlay.get_at((400, 320)).a <= 20
    assert overlay.get_at((2, 2)).a > 100  # frame edge


def test_explosion_frames_use_palette():
    frames = procgen.explosion_frames(scale=1)
    assert len(frames) == 4
    colours = {tuple(frames[3].get_at((x, y)))[:3] for x in range(12) for y in range(16) if frames[3].get_at((x, y)).a}
    assert colours and not colours & {(242, 252, 36), (254, 167, 17), (251, 59, 2)}


def test_generated_sounds_when_mixer_available():
    if not audio.init_mixer():
        pytest.skip("no mixer")
    snd = procgen.drone_sound(2.0)
    assert snd is not None and snd.get_length() == pytest.approx(2.0, abs=0.05)
    assert procgen.static_sound(0.6).get_length() == pytest.approx(0.6, abs=0.05)
    assert procgen.tone(55.0, 1.0).get_length() == pytest.approx(1.0, abs=0.05)


def test_generated_sounds_none_without_mixer(monkeypatch):
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    assert procgen.drone_sound(1.0) is None and procgen.static_sound() is None and procgen.tone(55, 1) is None


def test_audio_manager_register_and_bed_level():
    am = audio.AudioManager(0.8)
    if not am.enabled:
        pytest.skip("no mixer")
    am.register("drone", procgen.drone_sound(1.0))
    am.start_bed("drone")
    am.set_bed_level(0.25)
    assert am.bed_level == 0.25
    am.register("missing", None)
    am.play("missing")  # silently ignored


def test_bright_arcade_colours_are_gone_from_config():
    for name in ("CYAN", "YELLOW", "MAGENTA", "GREEN", "ORANGE", "RED", "WHITE"):
        assert not hasattr(config, name)


def test_sound_mix_has_no_fanfares():
    assert "wave" not in config.SOUND_FILES and "high_score" not in config.SOUND_FILES
    assert config.SOUND_FILES["knock"].endswith("sfx_sounds_impact3.wav")
    assert config.LOW_HEALTH_THRESHOLD == 25


def test_starfield_has_dying_star_and_ash():
    from space_shooter.starfield import Starfield

    sf = Starfield()
    assert len(sf.layers) == 2 and len(sf.ash.flecks) == 60
    radii = []
    for _ in range(60 * 6):
        sf.update(1 / 60)
        radii.append(sf.star.radius)
    assert max(radii) - min(radii) == pytest.approx(8, abs=1)
    surf = pygame.Surface((800, 640))
    sf.draw(surf)
    assert surf.get_at((int(sf.star.x), 2))[:3] != (0, 0, 0)


def test_slot_marker_colours():
    from space_shooter.hud import slot_colour
    from space_shooter.salvage import Part

    assert slot_colour(None) == STEEL_DIM
    assert slot_colour(Part("turret")) == STEEL and slot_colour(Part("turret", rare=True)) == EMBER
