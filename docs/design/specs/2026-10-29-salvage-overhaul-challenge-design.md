# Salvage overhaul and challenge pass — design

Date: 2026-10-29
Status: approved; numbers below marked *tuned* were changed by the balance pass in Task 6
Builds on: `2026-10-28-act1-core-loop-design.md`

## 1. Why

Play feedback: Act 1 plays well but Normal is not challenging, and several
salvage parts do little or nothing in real play. An audit of the shipped code
found:

| Part | Problem |
| --- | --- |
| Auto-turret | 260 px range from a ship near the bottom: it never reaches enemies in the top half and idles most of the time. |
| Tractor | 180 px range: drops 250 px away fall past untouched. |
| Armour plate | Only gunners and the Warden shoot, so its "draws fire" role barely happens. |
| Thruster, claw | Work, but the effect is too small to notice. |
| Echo bullets | Pass through hulks and debris. |

A headless autopilot run through Act 1 on Normal took two hits; the Warden
fell in 18 to 33 seconds.

### Success criteria

1. Every part has a visible, useful effect a player notices within one encounter.
2. Owning two of the same part unlocks a stronger, named bonus shown on the HUD.
3. On Normal, a scripted autopilot takes at least three times as many hits
   over the same Act 1 run as before, and the Warden fight lasts at least
   twice as long.
4. All new rules are unit-tested; lint and the full suite stay green.

## 2. Part signature moves

| Part | Signature move | Numbers |
| --- | --- | --- |
| Auto-turret | Screen-wide range; targets the enemy nearest the ship; drawn barrel swivels toward its target. Scarred: two-round burst. | range 900 px, period 0.5 s, burst gap 0.08 s |
| Slug cannon | Every 4th trigger pull fires a heavy round that pierces every enemy in its path and shoves each hit enemy back. | normal round 2 *tuned* (was 3), heavy damage 4, pierce unlimited, shove 28 px up |
| Tractor | Visible beam to the drop it is pulling; range doubled. Drag field slows enemy bullets near the ship. | pull range 360 px, drag radius 150 px, drag 40% slower |
| Armour plate | Drawn cracks as it loses hits. When it breaks it bursts into shrapnel. | 10 shrapnel rounds, 1 damage each, 520 px/s |
| Thruster | Dash on X / Shift / gamepad X: a short invulnerable burst with afterimages. Passive speed bonus stays. | dash 0.18 s at 1100 px/s, recharge 2.5 s per charge, scarred thruster −0.5 s |
| Salvage claw | Tears enemies that touch it; anything the claw kills always drops salvage. Passive drop bonus stays. | 2 damage per contact, 0.3 s per-enemy cooldown, contact radius 20 px |

Dash direction is the current move input, or straight up when there is none.
Dashing needs at least one thruster.

## 3. Pair bonuses

A kind is "paired" when two or more of it are bolted on (scarred counts).

| Pair | Name on HUD | Effect |
| --- | --- | --- |
| Turrets | TWIN TURRETS | Turrets fire together, period 0.35 s |
| Slug cannons | BROADSIDE | Heavy round every 3rd trigger pull |
| Tractors | GRAVITY WELL | Pull range covers the whole screen |
| Armour plates | BULKHEAD | Each plate absorbs 3 hits instead of 2 |
| Thrusters | AFTERBURNER | Dash has 2 charges, recharge 2.0 s per charge |
| Claws | SCRAPPER | Every part dropped by a kill is scarred |

## 4. Challenge pass

- **Everyone shoots.**
  - Drones fire an aimed single shot every 2.6 to 3.6 s, from Ash Shelf on.
  - Zigzaggers fire a 3-round spread every 3.0 s.
  - Divers fire a 3-round burst at the moment they start their dive.
  - All of them aim at the player's armour plate when one is fitted.
  - Enemies only fire once they are on screen (y > 40).
- **Enemy bullets** travel at 290 px/s (was 260).
- **Difficulty presets** (enemy speed, enemy hull, enemy fire rate, salvage
  multiplier):

  | Preset | Speed | Hull | Fire | Salvage |
  | --- | --- | --- | --- | --- |
  | Easy | 1.0 | 1.0 | 1.0 | 0.8 |
  | Normal | 1.25 | 1.4 | 1.8 *tuned* | 1.0 |
  | Hard | 1.4 | 1.8 | 2.4 *tuned* | 1.5 |

- **Echo pressure.** Each live echo at the moment an enemy spawns adds 8% to
  its hull and 10% to its fire rate.
- **Loop scaling.** Enemy hull grows 4% per loop, capped at +60%.
- **The Warden.**
  - Base hull 600 *tuned* (was 160; 260 in the first draft).
  - Sweep every 0.75 s, Hunt every 0.95 s, rings every 2.6 s, Collapse single
    shots every 1.1 s.
  - Entering phase 2 and phase 3 each drops one scarred part.
- **Healing.** Hull patches are 10% of drops (claw +15%) and heal 20 hull.

## 5. Fixes in scope

- Echo bullets collide with hulks and debris like the player's.
- HUD shows dash charges and the names of active pair bonuses.

## 6. Architecture

- `salvage.py` (pure): pair detection and every part number above
  (`pairs()`, `heavy_every()`, `armour_hits()`, `dash_charges()`,
  `dash_recharge()`, `turret_period()`, `tractor_range()`, `drops_scarred()`).
- `dash.py` (new, pure): `Dash` charge/recharge/active-timer state.
- `entities/parts.py`: turret aiming and swivel state, heavy-slug volley, tractor beam data, armour crack drawing.
- `entities/bullets.py`: `HeavySlug`; bullets carry a `speed_scale` for the drag field.
- `entities/enemies.py`: enemy firing for drone, zigzag and diver; `armed` flag.
- `entities/warden.py`: new numbers and a phase-change callback.
- `scenes/gameplay.py`: wires dash input, claw contact, drag field,
  shrapnel, echo pressure and echo-bullet hazards. Part behaviour helpers
  move to a new `scenes/salvage_ops.py` so gameplay does not grow.
- `hud.py`: dash pips and pair names.

## 7. Testing

- Unit: pair detection; each number in sections 2 to 4; `Dash` charges and
  recharge; turret targets the nearest enemy anywhere on screen; heavy
  round on the right trigger pull; tractor range and drag; armour break
  spawns shrapnel; claw contact damage and forced drop; enemy firing rules;
  echo pressure; Warden phase drops.
- Integration: dash makes the player invulnerable for its duration; echo
  bullets damage hulks; the HUD draws with every pair active.
- Balance check: the scripted autopilot from the final review, run before
  and after, recorded in the commit message of the balance task.
