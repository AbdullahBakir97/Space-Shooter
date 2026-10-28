# Space Shooter

A polished arcade shoot-'em-up built with Python and pygame. Fly, dodge, chain
kills for combo multipliers, collect power-ups, and take down a Dreadnought
boss every five waves.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![pygame-ce](https://img.shields.io/badge/pygame--ce-2.5%2B-6aa84f?style=flat-square)
![CI](https://img.shields.io/github/actions/workflow/status/AbdullahBakir97/Space-Shooter/ci.yml?style=flat-square&label=CI)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## Features

**Gameplay**

- Four-direction movement with auto-fire and four weapon levels (single, twin, spread, quad).
- Five enemy behaviours: drones, zigzaggers, divers that lunge at you, gunners that park and
  shoot, and a multi-phase boss whose bullet patterns intensify as its hull fails.
- Timed waves that grow and unlock new enemy types; a boss every fifth wave.
- Combo multiplier (up to x8) for chaining kills, bombs that clear the screen, shields,
  hull repairs and score pickups.
- Three lives, three difficulty presets, and a persistent top-ten high score table with
  arcade-style initials entry.

**Feel**

- Parallax starfield with warp streaks between waves, particle exhaust and debris,
  explosion animations, screen shake, hit flashes, floating score popups.
- Low-hull alarm, boss warning klaxon, menu and pause sounds from Juhani Junkala's
  CC0 retro sound library.
- Frame-rate independent movement, so the game plays the same on any machine.

**Engineering**

- Clean package layout with scene stack, data-driven wave design and pure-logic modules.
- Headless test suite (43 tests) covering waves, scoring, persistence, entities and the
  full game loop; lint and format checks via `ruff`; CI on Python 3.11 to 3.13.

## Quick start

```bash
git clone https://github.com/AbdullahBakir97/Space-Shooter.git
cd Space-Shooter
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py                   # or: python -m space_shooter
```

Requires Python 3.11 or newer. `pip install -e .` also installs a `space-shooter`
command.

## Controls

| Action            | Keyboard                 | Gamepad          |
| ----------------- | ------------------------ | ---------------- |
| Move              | Arrow keys / WASD        | Left stick / D-pad |
| Fire (hold)       | Space / Z                | A / Y / RB       |
| Bomb              | X / Shift                | B / X            |
| Pause             | Esc / P                  | Start            |
| Menu confirm/back | Enter / Esc              | A / Back         |
| Fullscreen        | F11                      |                  |

## How it plays

- **Waves** spawn enemies over time. Clear everything to advance; a "BOSS NEXT WAVE"
  banner warns you a wave early.
- **Combo**: kills within 1.6 s of each other build a chain. Every three chained kills
  raise the multiplier. The yellow bar under the counter shows how long you have.
- **Power-ups** drop from destroyed enemies: `W` weapon level, `+` hull repair,
  `S` eight-second shield, `B` extra bomb, `$` bonus score. Bosses always drop two.
- **Dying** costs a life and one weapon level; you respawn with a short invulnerability.
- **Bombs** destroy every regular enemy and bullet on screen and strip a quarter of a
  boss's hull.
- **Difficulty** scales enemy speed, hull, spawn rate and fire rate, and multiplies score
  (Easy x0.8, Normal x1.0, Hard x1.5).

Settings and high scores are stored per user (`~/.local/share/space-shooter` on Linux,
`~/Library/Application Support/space-shooter` on macOS, `%APPDATA%\space-shooter` on
Windows). Set `SPACE_SHOOTER_DATA_DIR` to override.

## Project layout

```
main.py                     launcher
space_shooter/
  game.py                   window, clock, input mapping, main loop
  config.py                 every tunable constant
  waves.py                  pure wave/spawn-plan generation
  combo.py                  kill-chain multiplier
  highscores.py             top-ten table, JSON persistence
  settings_store.py         user settings, JSON persistence
  assets.py / audio.py      cached loading, hue-shifted sprites, sfx with fallback
  starfield.py / effects.py parallax background, particles, shake, flashes
  entities/                 player, bullets, enemies (drone, zigzag, diver, gunner, boss), power-ups
  scenes/                   menu, settings, high scores, gameplay, pause, game over
  hud.py / ui.py            overlay and menu widgets
tests/                      headless pytest suite
images/                     12x16 pixel-art source sprites (drawn at 4x)
sounds/                     Juhani Junkala's retro SFX collection (CC0)
```

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

The tests run with the SDL dummy video and audio drivers, so they pass on CI runners
and headless machines. Gameplay tuning lives in `space_shooter/config.py`.

## Credits

- Sound effects: *The Essential Retro Video Game Sound Effects Collection* by
  [Juhani Junkala](https://juhanijunkala.com), released under CC0.
- Pixel art sprites: bundled in `images/`.

## Author

**Abdullah Bakir** - [@AbdullahBakir97](https://github.com/AbdullahBakir97)

Full-Stack Developer based in Germany - Python · Django · Vue · Nuxt.

## License

MIT. See [LICENSE](./LICENSE).
