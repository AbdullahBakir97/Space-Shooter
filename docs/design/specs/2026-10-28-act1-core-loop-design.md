# Loop of Ash — Act 1: core loop design

Date: 2026-10-28
Status: approved
Builds on: `2026-10-28-space-shooter-rebuild-design.md` (engine foundation)

## 1. Purpose

The rebuilt shooter plays well but is a generic wave shooter. This milestone
turns it into the first act of a distinct game, *Loop of Ash* (working title),
so that it feels unique from the first minute.

Two mechanics carry the identity:

- **Echoes**: every death resets a time loop, and previous runs fly beside the
  player as ghost ships replaying what they did.
- **Salvage**: destroyed enemies drop parts that bolt onto the player's hull,
  visibly changing the ship's shape and behaviour.

A sparse radio-log story, a grim visual and audio direction, and a cockpit-style
HUD carry the tone.

### Success criteria

1. A new player understands echoes and salvage within the first two loops
   without reading the README.
2. Two consecutive loops play differently because of the parts collected and
   the echoes flying.
3. Every screen reads as grim and lonely: no bright arcade colours, no score
   popups, no fanfares.
4. A full Act 1 run (five encounters and the Warden) is completable, and
   finishing it is recorded in the save.
5. All new pure logic is unit-tested, a headless loop with echoes runs in CI,
   and lint and tests stay green.

### Decisions already made (from the conversation)

- Stay on Python and pygame, 2D pixel art.
- Tone: grim and lonely.
- Echoes plus Salvage is the core loop. Hive, Factions, the strategy map and
  ground combat are later milestones.
- Act 1 core loop is built first.

## 2. Scope

In scope:

- Run structure: hangar, five authored encounters, drifts with radio logs, the
  Warden boss, loop-end card.
- Echo recording, playback, permanent echo loss, Warden targeting of echoes.
- Six hardpoints, six Act 1 part types, part knock-off and recovery.
- Story system: flag-triggered radio logs, log archive.
- New palette, ash particles, pulsing star, cockpit HUD, procedural enemy
  variants, procedural Warden sprite.
- Procedural drone audio bed generated in code; retuned sound mix.
- Versioned JSON save with migration from the current high score file.
- "Reduced flashing" setting.
- Tests for all new pure-logic modules and a headless integration loop.

Out of scope (later milestones): strategy map, ground combat and squads, the
Hive evolving swarm, Factions and reputation, Acts 2 to 4, endless mode,
persistent part unlocks, voice or music files.

## 3. Changes to the existing game

| Existing feature | Act 1 treatment |
| --- | --- |
| Menu scene | Replaced by the hangar scene. |
| Random wave director | Kept as the low-level spawner; encounters drive it with authored spawn scripts. |
| Weapon levels 1 to 4 | Removed. The tug has one fixed forward gun; firepower comes from parts. |
| Power-up badges | Removed. Drops are salvage parts and hull patches. |
| Bombs | Removed. The tractor and armour parts fill the panic-button role. |
| Combo multiplier and score popups | Removed from play. Kills still add salvage value, shown only on the loop-end card. |
| High score table | Becomes "Loop records": loop number, encounter reached, salvage value, time. Existing entries migrate. |
| Lives | Removed. One hull per loop; death ends the loop. |
| Difficulty presets | Kept, applied to enemy speed, hull and fire rate. |
| Pause, settings, gamepad, fullscreen | Kept. |

## 4. Run structure

### 4.1 Flow

```
Hangar ──launch──> Drift (log) ──> Encounter 1 ──> Drift ──> ... ──> Encounter 5
                                                                        │
     ┌──────────────── death at any point ──────────────────────────────┤
     ▼                                                                  ▼
 Loop-end card ──> Hangar (loop + 1)                         Drift ──> Warden
                                                                        │
                                                      victory ──> Act 1 ending
```

### 4.2 Hangar

The hub between loops. It shows the loop counter, the echo roster (up to five
names, each with how far it reached), the latest unread log, and options:
Launch, Log archive, Records, Settings, Quit. First launch skips straight into
the opening log.

### 4.3 Drift

A 6-second calm between encounters. No enemies; ash drifts; the star pulses.
One radio log plays if any is due. The player can recover drifting parts and
hull patches during a drift.

### 4.4 Encounters

Each encounter is data: a name, duration, spawn script and hazards. A spawn
script is a list of timed entries `(time, pattern, enemy kind, count, x)`.
Patterns: `line`, `vee`, `column`, `pincer` (from both sides), `scatter`.
An encounter ends when its script has finished and no enemies remain, or when
its time cap expires and the remaining enemies retreat.

| # | Name | Content | Named moment |
| --- | --- | --- | --- |
| 1 | Cold Wake | Drones in lines and vees. Teaches shooting and first salvage drop. | First part drop is guaranteed. |
| 2 | Ash Shelf | Drones and zigzags; slow ash clouds that hide bullets. | Ash cloud blackout lasting 4 s. |
| 3 | Graveyard | Divers among drifting hulks that block shots and can be destroyed for parts. | A hulk breaks open with a guaranteed rare part. |
| 4 | Picket Line | Gunners holding a line, drones screening them. | Gunners focus fire on the player's armour plate if present. |
| 5 | Last Light | Mixed pincers, faster spawns, debris rain. | Star flare: 2 s screen-wide ember flash that damages anything not behind a hulk. Disabled to a warning only under reduced flashing. |
| W | The Warden | Boss, see 4.5. | — |

Enemy kinds are the existing drone, zigzag, diver and gunner, re-skinned per 7.3.

### 4.5 The Warden

A large procedural machine with an ember eye. Hull scales with difficulty
(base 160 hits). Three phases at 100 %, 66 % and 33 % hull:

1. **Sweep**: rotating fan of shots.
2. **Hunt**: aims volleys at the densest echo cluster (see 5.5), then at the
   player.
3. **Collapse**: fires slower but spawns debris rings; the eye is exposed for
   double damage between rings.

Killing the Warden plays the Act 1 ending log sequence, marks `act1_complete`
in the save, stores the run's trace as an echo, and returns to the hangar with the archive entry unlocked. Later
loops can still be played after completion.

### 4.6 Death and the loop-end card

On death: 1.2 s slow-motion, hull breakup, then the card. It shows
"LOOP n", how far this run reached, salvage value, echoes lost this run, and a
one-line log. The run's trace is saved as a new echo (see 5.3) before the
hangar returns.

## 5. Echoes

### 5.1 Recording

During each run, `EchoRecorder` samples the player at 20 Hz: run time,
position, and whether the gun fired since the last sample. It also records the
hardpoint loadout whenever it changes. Encounter boundaries are recorded so
playback stays aligned with encounters.

### 5.2 Playback

An echo replays its trace on the same run clock, interpolating position
linearly between samples. When a sample has `fired`, the echo fires its fixed
gun plus any slug cannon it had at that time. Auto-turrets on an echo act on
their own timer exactly like the player's. Echo bullets
deal 60 % of player damage. Echoes collide with enemy bullets and enemies but
not with the player or each other. When a trace ends (the run died there), the
echo flickers and fades out at that point.

Echoes are drawn as translucent cold-blue silhouettes of the tug with their
parts, with a faint trail.

### 5.3 Roster rules

- Up to 5 echoes fly per loop: the 5 traces that reached furthest, ties broken
  by most recent.
- Traces shorter than 10 seconds are not kept.
- At most 12 traces are stored; the shortest are dropped first.
- Each echo has 6 hits of hull per loop. Destroyed echoes are removed from the
  save permanently, named in a radio line ("Echo 7 is gone.").
- Echo names are the loop number they came from.

### 5.4 Synchronisation

Echo playback is keyed to encounter-relative time, not total run time. If the
player clears an encounter faster or slower than the echo did, each echo jumps
to the start of its recording for the next encounter when the player's next
encounter begins. Echoes that died before reaching an encounter do not appear
in it.

### 5.5 Warden targeting

`densest_cluster(points, radius=90)` returns the centre of the circle of the
given radius containing the most live echo positions, or the player position
when no echoes are alive. Pure function, tested.

## 6. Salvage

### 6.1 Hardpoints

Six slots on the tug: `fore_l`, `fore_r`, `wing_l`, `wing_r`, `aft_l`, `aft_r`.
Each part type lists the slots it may occupy.

### 6.2 Act 1 parts

| Part | Slots | Behaviour |
| --- | --- | --- |
| Auto-turret | wing, aft | Fires at the nearest enemy within 260 px every 0.5 s. |
| Slug cannon | fore | Fires with the main gun; slow, heavy round dealing 3 hits, pierces one enemy. |
| Tractor | aft | Pulls drops within 180 px; recovers knocked-off parts automatically. |
| Armour plate | any | Absorbs the next 2 hits before the hull; enemies prefer to aim at it. |
| Thruster | aft | +15 % speed and faster acceleration, stacks twice. |
| Salvage claw | fore | +50 % drop chance; drops hull patches more often. |

### 6.3 Drops

- Base drop chance per kill 18 %, modified by difficulty and the claw.
- A drop is a part (80 %) or a hull patch (20 %) that restores 25 hull.
- Rare parts (Graveyard hulk, Warden phases) are the same types with a
  "scarred" variant that has 1.5 times the effect. One rare per encounter at
  most.

### 6.4 Attach, knock-off, recovery

- Flying into a drop attaches it to the free valid slot closest to the
  contact point. If no valid slot is free, the part replaces the oldest part in
  a valid slot, and the old part is ejected as a drifting drop.
- When the hull takes a hit, there is a 35 % chance one random part is knocked
  off first instead (armour plates absorb before this roll). A knocked-off part
  drifts for 6 s, blinking for its last 2 s, and can be re-collected.
- Parts do not persist between loops. Echoes keep the parts they had.

### 6.5 Drawing

Parts are drawn as small procedural pixel shapes attached at fixed offsets per
slot, scaled with the tug sprite, so the silhouette changes as parts are
added. Knocked-off parts tumble.

## 7. Story, look and sound

### 7.1 Story system

- `LogEntry`: id, speaker (`pilot`, `fleet`, `warden`, `unknown`), up to 3
  lines, trigger condition, priority.
- Trigger conditions are small declarative rules evaluated against a
  `StoryState` (loop count, flags set, encounter reached, echoes lost, Warden
  seen, act complete). Examples: `loop >= 3`, `flag:first_echo_lost`,
  `reached:4 and loop >= 5`.
- At most one log plays per drift; the highest-priority unread eligible log is
  chosen. Hangar shows the latest one again.
- About 20 Act 1 logs, stored in `space_shooter/data/act1_logs.json` so writing
  can change without touching code.
- Log panel: typewriter text at 40 characters per second, radio static under
  it, cracked panel frame. Any key completes the line; a second press closes.
- Archive in the hangar lists every unlocked log in order.

Story beats the logs must cover: the fleet is gone; the pilot is talking to an
empty channel; the loop is noticed; echoes appear and the pilot does not trust
them; the first echo lost; the Warden is first seen; the Warden speaks; the
Act 1 ending hints that the loop was built, not an accident.

### 7.2 Palette

| Token | Use | RGB |
| --- | --- | --- |
| void | background | 4, 5, 9 |
| steel | UI, player, echoes | 96, 128, 160 |
| steel_dim | inactive UI | 48, 60, 76 |
| ash | particles, text secondary | 130, 128, 124 |
| rust | enemies, damage | 140, 62, 40 |
| bone | primary text | 210, 205, 196 |
| ember | the star, fire, the Warden's eye, only important things | 255, 122, 40 |

The existing bright cyan, yellow, magenta and green are removed from play.

### 7.3 Visuals

- Dim two-layer starfield, a dying star at the top edge pulsing slowly in
  ember, drifting ash particles across the playfield.
- Enemies: existing sprites desaturated toward rust with scorch-mark pixels
  added procedurally. Each kind keeps a distinct silhouette accent.
- The Warden: a procedurally built symmetric sprite (about 48 x 32 source
  pixels, drawn at 4x) with a separate ember eye layer.
- HUD as a cockpit readout: a cracked frame overlay, faint scanlines, hull as a
  damaged schematic of the tug with its occupied hardpoints lit, loop counter,
  echo roster as small icons that grey out when lost, encounter name on entry.
- Explosions are heavier and dimmer: fewer particles, longer smoke, ember core.
- Reduced flashing setting disables full-screen flashes and caps shake.

### 7.4 Sound

- Drone bed: generated at startup with numpy-free pure Python into a
  `pygame.mixer.Sound` buffer (two detuned low sine layers plus slow filtered
  noise, about 8 s, seamless loop). Volume rises slightly in encounters and
  drops in drifts.
- Radio static: generated noise burst under each log.
- Retuned sound choices from the existing CC0 library: heavier explosions,
  quieter gun, hull creak on part knock-off, alarm only below 25 % hull.
- No fanfares. Act 1 completion uses a single low tone and silence.
- If the mixer is unavailable, all of this is skipped silently.

## 8. Save and settings

`save.json` in the user data directory, versioned:

```json
{
  "version": 1,
  "loop": 12,
  "echoes": [{"loop": 9, "reached": 4, "duration": 212.4, "samples": "<base64>", "loadouts": []}],
  "flags": ["first_echo_lost", "warden_seen"],
  "read_logs": ["a1_open", "a1_loop3"],
  "records": [{"loop": 9, "reached": 4, "salvage": 3120, "time": 212.4, "difficulty": "normal"}],
  "act1_complete": false
}
```

- Echo samples are packed as little-endian floats and base64-encoded to keep
  the file small (5 minutes at 20 Hz is about 6000 samples).
- On first load, if `save.json` is missing and `high_scores.json` exists, its
  entries become records with `reached` unknown (stored as 0).
- A corrupt or newer-version save is backed up as `save.json.bak` and a fresh
  save is started; the player sees a one-line notice in the hangar.
- Settings gain `reduced_flashing: bool = False`.

## 9. Architecture

New modules:

```
space_shooter/
  palette.py          colour tokens from 7.2
  save.py             SaveData, load/save, migration, echo packing
  echoes.py           EchoTrace, EchoRecorder, EchoPlayback, roster selection, densest_cluster
  salvage.py          PartType table, Loadout (slots, attach, replace, knock_off), drop rolls
  story.py            LogEntry, condition parser, StoryState, LogDirector
  encounters.py       Encounter data, SpawnEntry, pattern expansion, EncounterDirector
  procgen.py          scarred enemy variants, Warden sprite, part sprites, drone and static audio
  data/act1_logs.json
  entities/echo.py    Echo sprite driven by EchoPlayback
  entities/parts.py   attached part drawing, Drop sprite
  entities/warden.py  Warden boss
  scenes/hangar.py    replaces scenes/menu.py
  scenes/loop_end.py  loop-end card
  scenes/archive.py   log archive
  scenes/log_panel.py overlay used by drifts and the hangar
```

Changed modules: `scenes/gameplay.py` becomes a coordinator that owns the
player, groups, `EncounterDirector`, `EchoRecorder`, echo sprites, `Loadout`
and `LogDirector`; combat and drawing helpers move out to keep it under about
400 lines. `hud.py` is rewritten for the cockpit HUD. `config.py` gains Act 1
tuning. `player.py` loses weapon levels, lives and bombs and gains a `Loadout`.
`highscores.py` and `combo.py` are removed once records live in `save.py`.

Pure modules with no display dependency: `save.py`, `echoes.py` (except
drawing), `salvage.py`, `story.py`, `encounters.py` (data and expansion).

Data flow per frame in an encounter:

1. Input → player movement and fire.
2. `EchoRecorder.sample(t, player)`; each echo sprite asks `EchoPlayback` for
   its state at encounter time `t`.
3. `EncounterDirector.update` yields spawns.
4. Entities update; parts act (turrets choose targets, tractor pulls).
5. Collisions resolve against hull, armour, parts and echoes.
6. `LogDirector` is polled only during drifts and the hangar.

Error handling follows the foundation rules: missing assets or audio degrade
silently, corrupt state is backed up and reset, never a crash.

## 10. Testing

Unit tests:

- `echoes`: recording at 20 Hz, interpolation, fire events, trace end, roster
  selection and limits, encounter re-sync, `densest_cluster`.
- `salvage`: valid slots, closest-slot attach, replacement and ejection,
  knock-off with armour precedence, thruster stacking cap, drop roll odds with
  a seeded RNG.
- `story`: condition parser (comparisons, flags, `and`), priority selection,
  one-log-per-drift, read tracking, JSON data validates (unique ids, at most 3
  lines, parseable conditions).
- `encounters`: pattern expansion positions, script ordering, time cap.
- `save`: round trip, echo packing, migration from `high_scores.json`, corrupt
  and newer-version backup.

Integration (headless):

- Hangar → launch → first encounter spawns → a part drop attaches.
- Die in encounter 2 → loop-end card → hangar shows loop 2 and one echo.
- Loop with three seeded echoes runs two encounters without error and echoes
  fire.
- Warden fight with forced low hull reaches all three phases and completion
  sets `act1_complete`.

CI is unchanged: ruff check, ruff format check, pytest on 3.11 to 3.13.

## 11. Delivery

This milestone lands on the existing branch and pull request, which will be
retitled for Act 1. Implementation follows a written plan with tasks in this
order, each leaving the game runnable and tests green:

1. Palette, save module and migration.
2. Salvage logic and part drawing; player refactor.
3. Echo logic, recorder, echo sprites.
4. Encounters and directors; drifts.
5. Story system, logs and log panel.
6. Warden.
7. Hangar, loop-end card, archive.
8. Visual and audio pass, HUD, reduced flashing.
9. Cleanup of removed systems, README and docs update.

## 12. Open risks

- **Balance**: five echoes firing can trivialise early encounters. Mitigation:
  echo damage at 60 %, echo hull limits, and encounter difficulty rising with
  loop count (+3 % enemy hull per loop, capped at +45 %).
- **Readability**: echoes, parts and ash can clutter the screen. Mitigation:
  echoes at 35 % opacity, ash behind gameplay, one accent colour.
- **Procedural audio quality**: pure-Python generation may sound thin. If it
  does, fall back to layering existing CC0 sounds at low volume.
