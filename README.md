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
The ones that reached furthest fly first, so protecting them matters. In the
war, echoes follow the kind of fight: the runs that fought a Graveyard-type
location join every Graveyard-type fight.

**Salvage.** Your tug has six hardpoints: two fore, two on the wings, two aft.
Destroyed enemies drop parts. Fly into one and it bolts onto the nearest free
slot, and your ship visibly changes shape. Parts do not carry over between
loops. Every loop is a fresh build.

| Part | Slots | What it does |
| --- | --- | --- |
| Auto-turret | wing, aft | Swivels and fires on its own at the enemy nearest you, anywhere on screen. Scarred turrets fire two-round bursts. |
| Slug cannon | fore | Fires with your gun. Every fourth shot is a heavy round that tears through its whole line and shoves enemies back. |
| Tractor | aft | A visible beam reels in drops up to 360 px away and recovers knocked-off parts. Its drag field slows enemy bullets near you by 40%. |
| Armour plate | any | Absorbs two hits and draws enemy aim. It cracks as it wears, then bursts into shrapnel that shreds nearby enemies. |
| Thruster | aft | +15% speed, and a dash on X or Shift: a short burst you can't be hit during. One charge, recharging in 2.5 s. |
| Salvage claw | fore | Tears enemies that touch it, and anything it kills always drops salvage. +50% drop chance. |

**Pair bonuses.** Two of the same part unlock a named bonus, shown in the cockpit panel:

| Pair | Bonus |
| --- | --- |
| TWIN TURRETS | Turrets fire together, faster. |
| BROADSIDE | Heavy slug every third shot. |
| GRAVITY WELL | The tractor pulls from anywhere on screen. |
| BULKHEAD | Each plate takes three hits. |
| AFTERBURNER | Two dash charges, recharging faster. |
| SCRAPPER | Every part dropped by a kill is scarred. |

When the hull takes a hit, there is a 35% chance a part is knocked off
instead. It drifts away for six seconds and you can fly back for it.
Scarred parts, marked in ember, are 1.5 times as strong.

**The war.** Each loop is one turn of a war for the star system, and you fly
it. LAUNCH undocks the tug from Anchor Station into a system three screens
wide: fourteen locations on three rings, linked by lanes. Fly into any
location that isn't yours and its fight begins. Each one plays as one of the
encounters below. Win and the ground is yours at once; you come back to space
with the hull and parts you finished the fight with, and you can fly on to
the next one or turn for home.

- **Lanes** are the safe roads: the tug flies 60% faster on them and patrols
  see you at half the range. Open space is slower, and ash wears a point of
  hull every four seconds.
- **The swarm** spreads after every loop, faster as the war drags on. It takes
  empty space first and turns on your ground when nothing is left. Its ground
  fights back harder (+25% enemy hull). Ground it holds for three turns
  becomes a hive (+50% hull and a faster script), and hives spread it further.
- **Patrols** drift along the lanes out of swarm ground. One that spots you
  gives chase; outfly it and it loses interest after four seconds. If it
  catches you, you fight a short ambush for salvage but no ground.
- **Ending a loop:** dock at home (Enter inside the ring) to bank everything
  you carry. If you die, you keep every location you won but lose half the
  salvage you were carrying. Held stations patch 25 hull once a loop as you
  fly through them.
- **Salvage** from each loop, plus a yield from every location you hold, goes
  into a war chest. Spend it in the SHIPYARD on up to two parts fitted when
  you undock (800 each), or fortify a held location from the CHART (1000) so
  it survives one attack.
- **Winning:** hold all five middle worlds to unseal SHELF GATE, take it, and
  kill the Warden at WARDEN CORE.
- **Losing:** ANCHOR STATION, your home, is the last stand. If the swarm takes
  it, the war is lost and a fresh one starts. Your echoes, records and story
  carry over.

The planets (KESS, HALE, MERE) are where ground combat will land next; for
now they fight like any other location.

| In flight | Keyboard | Gamepad |
| --- | --- | --- |
| Fly | Arrow keys / WASD | Left stick / D-pad |
| Dash (needs a thruster) | X / Shift | X |
| Dock at home | Enter | A |
| System chart | Tab | |
| Pause | Esc / P | Start |

**The encounters.** Act 1 has five encounters and a boss, each reached
through a quiet drift where the radio sometimes speaks.

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
its eye for double damage, and it sheds a scarred part each time it breaks into
a new phase.

**Every enemy shoots.** Drones fire aimed shots from Ash Shelf on, zigzaggers
fire spreads, divers fire a burst as they dive, and gunners hold a firing line.
Each echo flying with you makes new enemies 8% tougher and 10% quicker to
fire, and enemy hulls grow 4% each loop, up to 60%.

**The story** is told through twenty-six short radio logs that unlock as you loop,
lose echoes, reach new encounters and fight the war. The hangar keeps an archive of every log
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
| Dash (needs a thruster) | X / Shift | X |
| Pause | Esc / P | Start |
| Menu confirm / back | Enter / Esc | A / Back |
| Fullscreen | F11 | |

Pausing lets you abandon a loop. Abandoning, dying and closing the window
mid-run, in flight or in a fight, all end the loop the same way: the run is
kept as an echo, half the carried salvage is lost, and the loop counter
advances.

## Settings

Sound volume, screen shake, fullscreen, an FPS counter, difficulty, and
**reduced flashing**. Reduced flashing turns off full-screen flashes, caps
screen shake, and turns the star flare and the ash blackout into warnings
only.

Difficulty scales enemy speed, hull and fire rate, and multiplies salvage
value:

| Preset | Speed | Hull | Fire rate | Salvage |
| --- | --- | --- | --- | --- |
| Easy | 1.0 | 1.0 | 1.0 | x0.8 |
| Normal | 1.25 | 1.4 | 1.8 | x1.0 |
| Hard | 1.4 | 1.8 | 2.4 | x1.5 |

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
  salvage.py                 hardpoints, parts, pair bonuses, knock-off and drop rules
  dash.py                    thruster dash charges and recharge
  encounters.py              Act 1 encounters as data and their director
  campaign.py                the war: star system, claims, swarm spread, hives, war chest
  flight.py                  flying the system: lanes, drift, ash wear, patrols, repairs
  data/system.json           the fourteen locations and their lanes
  echoes.py                  recording, playback, roster rules, cluster targeting
  story.py                   radio-log conditions and selection
  data/act1_logs.json        the Act 1 radio logs
  procgen.py                 generated sprites, cockpit overlay, drone and static audio
  assets.py / audio.py       cached loading, sound playback with a no-audio fallback
  starfield.py / effects.py  dying star, ash, parallax, particles, shake, flashes
  hud.py / ui.py             cockpit readout and menu widgets
  entities/                  tug, bullets, parts and drops, enemies, the Warden, hazards, echoes
  scenes/salvage_ops.py      claw, tractor, drag field and shrapnel behaviour
  scenes/run.py              one flown loop: the tug and its cargo across fights, closed once
  scenes/                    hangar, flight, system chart, shipyard, gameplay, log panel,
                             archive, records, settings, pause, loop-end card
tests/                       headless pytest suite
images/                      12x16 source sprites
sounds/                      Juhani Junkala's retro SFX collection (CC0)
docs/design/            design specs and implementation plans
```

The rule modules (`save`, `salvage`, `dash`, `campaign`, `flight`, `encounters`, `echoes`, `story`) do not
import pygame, so they are tested directly without a window.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

The suite (356 tests) runs with SDL's dummy video and audio drivers, so it
passes on CI runners and headless machines. CI runs lint, format and tests on
Python 3.11 to 3.13.

## Roadmap

Act 1 is the first milestone of a larger campaign:

1. **Strategy map** (done): a star system you fly through, where the swarm
   spreads each turn and you choose where to fight.
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
