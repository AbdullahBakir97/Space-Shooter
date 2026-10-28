import pygame
import pytest

from space_shooter.effects import Flash, ScreenShake
from space_shooter.game import Game
from space_shooter.palette import BONE
from space_shooter.salvage import Part
from space_shooter.settings_store import Settings
from tests.helpers import run_frames, start_run


@pytest.fixture
def game():
    g = Game(settings=Settings(sfx_volume=0.0), headless=True)
    yield g
    pygame.quit()


def test_flash_disabled_is_noop():
    f = Flash()
    f.enabled = False
    f.trigger(BONE, 200)
    assert f.alpha == 0


def test_shake_cap():
    s = ScreenShake()
    s.cap = 4.0
    s.add(50)
    assert s.strength == 4.0


def test_reduced_flashing_disables_flash_and_caps_shake(game):  # Review Focus 4
    game.settings.reduced_flashing = True
    scene = start_run(game)
    scene.flash.trigger((255, 255, 255), 200)
    assert scene.flash.alpha == 0
    scene.shake.add(50)
    assert scene.shake.strength <= 4.0


def test_flare_with_reduced_flashing_is_warning_only(game):  # Review Focus 4
    game.settings.reduced_flashing = True
    scene = start_run(game, encounter=4)
    scene.trigger_moment("flare")
    run_frames(game, 60 * 4)
    assert scene.flash.alpha == 0 and scene.player.health == 100
    assert scene.warning_text is None or "FLARE" in scene.warning_text


def test_blackout_with_reduced_flashing_is_warning_only(game):  # Review Focus 4
    game.settings.reduced_flashing = True
    scene = start_run(game, encounter=1)
    scene.trigger_moment("blackout")
    assert scene.blackout_timer == 0 and "ASH" in scene.warning_text


def test_hud_draws_with_full_loadout(game):
    from tests.test_gameplay import seeded_trace

    game.save.echoes = [seeded_trace(n, x=150.0 + n * 90).to_data() for n in range(1, 6)]
    scene = start_run(game, encounter=0)
    lo = scene.player.loadout
    for kind, contact in [
        ("slug", (-14, -30)),
        ("claw", (14, -30)),
        ("turret", (-30, 2)),
        ("armour", (30, 2)),
        ("tractor", (-16, 30)),
        ("thruster", (16, 30)),
    ]:
        lo.attach(Part(kind, rare=kind == "claw"), contact)
    scene.player.health = 20
    run_frames(game, 30)
    assert scene.roster == [5, 4, 3, 2, 1]  # roster order: most recent first among equals
