# Loop of Ash

A grim pixel-art shooter built with Python and pygame. You are the last
salvage pilot of a dead fleet, trapped in a time loop around a dying star.
Every death resets the loop, and every run you lived through flies again
beside you as an echo.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![pygame-ce](https://img.shields.io/badge/pygame--ce-2.5%2B-6aa84f?style=flat-square)
![CI](https://img.shields.io/github/actions/workflow/status/AbdullahBakir97/Space-Shooter/ci.yml?style=flat-square&label=CI)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## How it plays

**Echoes.** Each run is recorded. On the next loop, up to five of your past
runs fly with you as translucent ghosts. They follow the path you flew, fire
when you fired, and carry the parts you had. They deal 60% of your damage and
take six hits. An echo destroyed in combat is gone from your save for good.
The ones that reached furthest fly first, so protecting them matters.

**Salvage.** Your tug has six hardpoints: two fore, two on the wings, two aft.
Destroyed enemies drop parts. Fly into one and it bolts onto the nearest free
slot, and your ship visibly changes shape. Parts do not carry over between
loops. Every loop is a fresh build.

| Part | Slots | What it does |
| --- | --- | --- |
| Auto-turret | wing, aft | Fires at the nearest enemy in range on its own. |
| Slug cannon | fore | Fires with your gun: a slow heavy round that hits for 3 and pierces one enemy. |
| Tractor | aft | Pulls drops toward you and recovers knocked-off parts. |
| Armour plate | any | Absorbs the next two hits. Enemies aim at it. |
| Thruster | aft | +15% speed, stacks twice. |
| Salvage claw | fore | +50% drop chance and more hull patches. |

When the hull takes a hit, there is a 35% chance a part is knocked off
instead. It drifts away for six seconds and you can fly back for it.
Scarred parts, marked in ember, are 1.5 times as strong.

**The loop.** Act 1 is five encounters and a boss, with a quiet drift between
each one where the radio sometimes speaks.

| Encounter | What waits there |
| --- | --- |
| Cold Wake | Drones. Your first kill always drops a part. |
| Ash Shelf | Zigzaggers, and ash clouds that hide bullets. Then the lights go out. |
| Graveyard | Divers among dead hulls that block shots and break open for salvage. |
| Picket Line | Gunners that hold a line and aim for your armour. |
| Last Light | Everything at once, falling debris, and a star flare you survive only behind a hulk. |
| The Warden | The machine that keeps the loop sealed. It learns where your echoes gather. |

The Warden has three phases. It sweeps rotating fans of fire, then hunts the
densest cluster of your echoes, then collapses into debris rings that expose
its eye for double damage. Enemy hulls grow 3% each loop, up to 45%.

**The story** is told through twenty short radio logs that unlock as you loop,
lose echoes and reach new encounters. The hangar keeps an archive of every log
you have heard.

## Quick start

```bash
git clone https://github.com/AbdullahBakir97/Space-Shooter.git
cd Space-Shooter
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py                   # or: python -m space_shooter
```

Requires Python 3.11 or newer. `pip install -e .` also installs a
`space-shooter` command.

## Controls

| Action | Keyboard | Gamepad |
| --- | --- | --- |
| Move | Arrow keys / WASD | Left stick / D-pad |
| Fire (hold) | Space / Z | A / Y / RB |
| Pause | Esc / P | Start |
| Menu confirm / back | Enter / Esc | A / Back |
| Fullscreen | F11 | |

Pausing lets you abandon a loop. Abandoning, dying and closing the window
mid-run all end the loop the same way: the run is kept as an echo and the
loop counter advances.

## Settings

Sound volume, screen shake, fullscreen, an FPS counter, difficulty, and
**reduced flashing**. Reduced flashing turns off full-screen flashes, caps
screen shake, and turns the star flare and the ash blackout into warnings
only.

Difficulty scales enemy speed, hull and fire rate, and multiplies salvage
value: Easy x0.8, Normal x1.0, Hard x1.5.

Progress, echoes, story flags, records and settings are stored per user
(`~/.local/share/space-shooter` on Linux,
`~/Library/Application Support/space-shooter` on macOS,
`%APPDATA%\space-shooter` on Windows). Set `SPACE_SHOOTER_DATA_DIR` to
override. An unreadable save is backed up as `save.json.bak` and a fresh one
is started.

## Project layout

```
main.py                      launcher
space_shooter/
  game.py                    window, clock, input mapping, main loop
  config.py / palette.py     tuning constants and the colour palette
  save.py                    versioned save, echo packing, records, migration
  salvage.py                 hardpoints, parts, knock-off and drop rules
  encounters.py              Act 1 encounters as data and their director
  echoes.py                  recording, playback, roster rules, cluster targeting
  story.py                   radio-log conditions and selection
  data/act1_logs.json        the Act 1 radio logs
  procgen.py                 generated sprites, cockpit overlay, drone and static audio
  assets.py / audio.py       cached loading, sound playback with a no-audio fallback
  starfield.py / effects.py  dying star, ash, parallax, particles, shake, flashes
  hud.py / ui.py             cockpit readout and menu widgets
  entities/                  tug, bullets, parts and drops, enemies, the Warden, hazards, echoes
  scenes/                    hangar, gameplay, log panel, archive, records, settings, pause, loop-end card
tests/                       headless pytest suite
images/                      12x16 source sprites
sounds/                      Juhani Junkala's retro SFX collection (CC0)
docs/design/            design specs and implementation plans
```

The rule modules (`save`, `salvage`, `encounters`, `echoes`, `story`) do not
import pygame, so they are tested directly without a window.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

The suite (193 tests) runs with SDL's dummy video and audio drivers, so it
passes on CI runners and headless machines. CI runs lint, format and tests on
Python 3.11 to 3.13.

## Roadmap

Act 1 is the first milestone of a larger campaign:

1. **Strategy map**: a star system where the swarm spreads each turn and you
   choose where to fight.
2. **Ground combat**: top-down drops onto planets with a small squad you
   command.
3. **The Hive**: a swarm that evolves against how you play, and its queen.
4. **The Factions**: hail instead of shooting, earn escorts or hunters, and a
   reputation that survives the loop.
5. **The Source**: the finale, an endless mode, and save polish.

## Credits

- Sound effects: *The Essential Retro Video Game Sound Effects Collection* by
  [Juhani Junkala](https://juhanijunkala.com), released under CC0.
- Source sprites: bundled in `images/`, recoloured and extended in code.

## Author

**Abdullah Bakir** - [@AbdullahBakir97](https://github.com/AbdullahBakir97)

## License

MIT. See [LICENSE](./LICENSE).
