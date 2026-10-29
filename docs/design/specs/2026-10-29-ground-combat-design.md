# Ground combat — design

Date: 2026-10-29
Status: approved in conversation
Builds on: `2026-10-29-flyable-map-design.md`

## 1. Purpose

The war is fought in space and on the ground. Flying into one of the three
planets (KESS, HALE, MERE) lands the tug, and the pilot fights on foot, with
hand weapons and a few survivors of the old garrison, to take the planet.

### Success criteria

1. Flying into a planet that isn't yours starts a ground fight. Completing
   its mission claims it; walking back to the tug takes off into flight.
2. The pilot moves, aims, fires, reloads, switches weapons, throws grenades
   and dodge-rolls. Rocks and wrecks block movement and shots.
3. Crawlers, spitters and brood nests behave as described in section 4 and
   find their way around rocks.
4. Survivors join when reached, obey follow, hold and move orders, and shoot
   at swarm they can see.
5. Each planet's mission works: KESS destroy the nests, HALE hold the
   beacon, MERE carry the core to the tug.
6. Ground rules live in a pygame-free module and are unit-tested. A
   headless autopilot lands, completes a mission and takes off.

## 2. A ground fight

1. **Landing.** The flight scene opens a ground fight instead of a space
   fight for a node with `ground: true` that can be engaged.
2. **The pad.** The pilot starts at the landing pad beside the tug.
3. **Mission.** The objective is shown at the top of the screen.
4. **Claim.** When the mission is complete, the planet is claimed and saved
   at once, and "RETURN TO THE TUG" is shown.
5. **Take off.** Pressing Enter within 60 px of the pad returns to flight.
6. **Salvage.** Kills give salvage, and each survivor still alive at take-off
   adds 100.
7. **Death.** The pilot's death ends the loop as a death in space does
   (claims kept, half the carried salvage lost).
8. **Hull.** The tug's hull is not touched by the ground fight; the pilot
   has their own health, full at every landing.

Abandoning from pause or closing the window ends the loop as a death.

## 3. The map

| Rule | Value |
| --- | --- |
| Tile size | 32 px |
| Map | 75 × 40 tiles (2400 × 1280 px) |
| Tiles | floor, rock (blocks movement and shots), wreck (blocks movement and shots) |
| Layout | generated from a seed fixed per planet (`zlib.crc32` of its id) |
| Pad | 3 × 3 floor tiles near the bottom-left |

- **Reachability.** Every objective, survivor and crate is reachable from the
  pad; a corridor is carved to any that is not.
- **Looks.** KESS is ash grey, HALE rust and MERE bone pale. Every planet
  draws a dark vignette 380 px around the pilot.

## 4. The swarm on foot

| Kind | Hull | Speed | Attack | Salvage |
| --- | --- | --- | --- | --- |
| Crawler | 6 | 150 px/s | contact, 8 damage, once per 0.6 s | 10 |
| Spitter | 8 | 70 px/s | keeps 260 px away with a clear shot; spit every 1.6 s, 6 damage, 320 px/s | 20 |
| Brood nest | 40 | — | spawns a crawler every 5 s, up to 6 alive per nest, while the pilot is within 700 px | 60 |

- **Pathing.** A flow field of tile distances from the pilot is rebuilt every
  0.5 s. Crawlers and spitters step toward lower-distance tiles.
- **Targets.** Enemies attack the nearest of the pilot and the survivors.
- **Twists.** Hull × the encounter's `hull` (1.25 on swarm ground, 1.5 on a
  hive). On a hive the nest and wave timers run at × 0.8.

## 5. The pilot and weapons

**The pilot.**
- 100 health, moving at 210 px/s.
- **Dodge roll** (Shift, X or the dash button): 0.35 s at 520 px/s,
  invulnerable while it lasts, with a 1.2 s cooldown.

| Weapon | Damage | Shots | Spread | Period | Magazine | Reserve | Reload |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sidearm | 2 | 1 | 0.03 rad | 0.25 s | unlimited | — | — |
| Rifle | 2 | 1 | 0.06 rad | 0.10 s | 30 | 90 | 1.6 s |
| Scattergun | 2 | 6 | 0.35 rad | 0.70 s | 6 | 24 | 2.0 s |

- **Bullets.** They fly at 700 px/s for up to 0.9 s and stop at rock and
  wrecks.
- **Grenades.** The pilot carries 2, up to 4. G throws one to the aim point
  (at most 300 px away). It bursts after 1.2 s for 12 damage within 90 px,
  hurting enemies only.
- **Weapon slots.** 1, 2 and 3 select the sidearm, rifle and scattergun once
  owned. R reloads, and an empty magazine reloads on its own.
- **Crates** give a weapon the pilot lacks, or its ammo, plus a grenade.
- **Aim.** The mouse aims and the left button fires; Space and Z also fire.
  A gamepad aims with the right stick.

## 6. The squad

- **Survivors.** Each planet holds 3 survivors (60 health) placed away from
  the pad. One joins when the pilot comes within 80 px.
- **Orders:**
  - **Q (follow):** stay 70 to 140 px from the pilot;
  - **E (hold):** stay put;
  - **right-click (move):** go to the clicked point, then hold.
- **Shooting.** A survivor shoots the nearest swarm in sight within 380 px:
  2 damage every 0.45 s, from a rifle that never runs dry.
- **Death.** A dead survivor drops 30 rifle ammo.

## 7. Missions

| Planet | Mission | Done when |
| --- | --- | --- |
| KESS | DESTROY THE BROOD NESTS | all 4 nests are dead |
| HALE | HOLD THE BEACON | the pilot has spent 90 s within 120 px of the beacon; waves of 3 crawlers and 1 spitter come from the map edge every 12 s while the hold runs |
| MERE | RECOVER THE CORE | the pilot has carried the core (picked up within 40 px, carrying slows to × 0.8) to within 60 px of the pad; MERE also has 2 nests |

## 8. Architecture

- `space_shooter/ground.py` (new, pure). All rules above, as a `GroundWorld`:
  - `GroundWorld.step(dt, inputs) -> list[event]` advances it;
  - `GroundInputs` is a plain data class (move, aim point, fire, roll,
    reload, weapon slot, grenade, orders).
- `space_shooter/scenes/ground.py` (new):
  - reads input and draws the map, entities and HUD;
  - talks to `CampaignRun` like the fight mode of `GameplayScene` does:
    `fight_over`, `end_loop`, `win_fight`.
- `scenes/flight.py`: planets open a `GroundScene`.
- `scenes/pause.py` and `game.close_open_loop` treat any scene with
  `end_loop` as a fight.

## 9. Testing

- **Unit:**
  - map size, determinism, reachability;
  - collision and line of sight;
  - every weapon number and reload;
  - grenades;
  - the roll;
  - flow-field pathing around a wall;
  - each enemy's behaviour;
  - the hull twist;
  - survivor joining and each order;
  - each mission completing;
  - pickups.
- **Integration:** landing from flight opens the ground scene; completing a
  mission claims and saves; take-off returns to flight; death ends the loop;
  abandon and window close end it once; drawing every state.
- **Headless autopilot:** land on KESS, clear the nests with scripted
  inputs, take off, dock.
