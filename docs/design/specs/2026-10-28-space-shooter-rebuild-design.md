# Space Shooter rebuild — design

Date: 2026-10-28

## Why

The committed game does not run. `main.py` and `scripts/` reference images
(`player.png`, `enemy.png`, `bullet.png`, `powerup.png`, `background.png`) and
sounds (`shoot.wav`, `explosion.wav`, `background.mp3`) that are not in the
repository, `Boss` is never defined, the player has no fire key, score is
passed by value and never changes, and the menu reads a stale event.

The repository does contain usable assets: a set of 12x16 pixel-art sprites
(three player frames, two enemy frames, four explosion frames, a title, a
"press to play" banner, digits) and Juhani Junkala's CC0 retro sound library.

Goal: a complete, polished, fun arcade shooter built on those assets, with the
engineering around it (package layout, tests, CI, docs) at a professional
standard.

## Scope

In scope:

- A `space_shooter` package replacing `scripts/`, run with `python main.py`
  or `python -m space_shooter`.
- Scenes: main menu, settings, high scores, gameplay, pause, game over with
  arcade-style initials entry.
- Gameplay: four-direction movement, auto-fire with weapon levels 1-4,
  bombs, shield, lives + health, combo multiplier, five enemy behaviours
  (drone, zigzag, diver, gunner, boss), timed wave spawning with a boss every
  fifth wave, five power-up types, three difficulty presets.
- Feel: parallax starfield, particle exhaust and debris, explosion animation,
  screen shake, hit flash, floating score text, low-health alarm, menu sounds.
- Input: keyboard (arrows/WASD, Space/Z fire, X/Shift bomb, Esc/P pause,
  F11 fullscreen) and a basic gamepad mapping.
- Persistence: settings and top-ten high scores as JSON in a per-user data
  directory; the old `high_scores.txt` is imported once if present.
- Delta-time movement so the game plays the same at any frame rate.
- Headless test suite (`SDL_VIDEODRIVER=dummy`), `pyproject.toml`, `ruff`,
  a CI workflow that actually fails on errors, a rewritten README with
  credits.

Out of scope: background music (the library has no music tracks), online
leaderboards, new art, localisation.

## Architecture

```
space_shooter/
  __init__.py       version
  __main__.py       entry for python -m
  config.py         window, colours, tuning constants, asset paths
  paths.py          repo root, user data dir
  assets.py         image/sound/font loading with cache and scaling
  audio.py          AudioManager: sfx volume, graceful no-audio fallback
  settings_store.py Settings dataclass + JSON load/save
  highscores.py     HighScoreTable: load/save/qualify/add, legacy import
  starfield.py      parallax star layers
  waves.py          pure wave/spawn-plan generation
  effects.py        Explosion, Particle, FloatingText, ScreenShake
  entities/
    player.py       Player
    bullets.py      PlayerBullet, EnemyBullet
    enemies.py      Enemy base, Drone, Zigzag, Diver, Gunner, Boss
    powerups.py     PowerUp
  hud.py            in-game overlay drawing
  scenes/
    base.py         Scene, SceneManager (stack)
    menu.py, settings.py, highscores.py, gameplay.py, pause.py, gameover.py
  game.py           Game: window, clock, loop, scene stack, input abstraction
main.py             thin launcher
tests/              headless pytest suite
```

Data flow: `Game.run` ticks the clock, converts pygame events into scene
calls (`handle_event`, `update(dt)`, `draw(surface)`), and lets scenes push,
pop, or replace scenes on the `SceneManager`. The gameplay scene owns sprite
groups and a `WaveDirector` that consumes the pure spawn plan from `waves.py`.
`waves.py`, `highscores.py`, `settings_store.py`, and the combo logic have no
pygame display dependency so they are unit-testable without a window.

Error handling: missing sound files or a missing audio device disable audio
rather than crashing; missing images fall back to generated placeholder
surfaces; corrupt JSON state files are ignored and rewritten.

## Testing

- Unit: wave plans (counts grow with wave, boss every 5th), high score
  qualification and ordering, settings round-trip, combo decay, player
  clamping and weapon level bounds, enemy bounds.
- Integration: run the gameplay scene headless for several hundred frames,
  asserting no exceptions and that score increases when bullets hit enemies.
- CI runs `ruff check` and `pytest` on Python 3.11-3.13 with dummy SDL
  drivers.
