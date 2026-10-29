# Flyable star system — design

Date: 2026-10-29
Status: draft, for review
Builds on: `2026-10-29-strategy-map-design.md`

## 1. Purpose

The war map is a menu: you pick stops and the game plays them. This
milestone makes the star system a place you fly. You undock from Anchor
Station into open space, steer the tug to the locations you choose, dodge
swarm patrols, and dock back home to end the loop.

### Decisions made in conversation

- Each loop is still one campaign turn; the swarm spreads once, at loop end.
- Free flight with the combat controls. Lanes are fast and hidden; open
  space is slow and wears the hull.
- No route planning. Fly anywhere, fight anywhere that isn't yours; docking
  home ends the loop, and so does dying.
- A large scrolling region about three screens on each side, with a radar
  and a system chart.
- Built as a separate flight scene; each fight opens the existing combat
  scene for one encounter and returns.
- Ground combat is the next milestone. Planets show a LAND prompt but fight
  as space locations until then.

### Success criteria

1. From the hangar a player can undock, fly to a location, win its fight,
   come back to space where they were, fly on, and dock home, with hull and
   parts carried between fights.
2. Patrols are visible, chase the tug, can be outflown, and start an
   ambush fight when they catch it.
3. Dying keeps every claim made that loop and loses half the carried
   salvage; docking keeps all of it.
4. Flight rules live in a pygame-free module and are unit-tested; a
   headless autopilot plays several loops through the real screens.
5. The classic six-encounter run stays reachable in code and its tests keep
   passing.

## 2. A loop

1. **Hangar.** LAUNCH undocks. SHIPYARD stays. Requisitioned parts are
   fitted at undock and cleared from the campaign at once.
2. **Flight.** The tug starts beside Anchor Station.
3. **Arrival.** Touching the marker of a location that is not yours starts
   its fight, with the twists from the strategy map (swarm +25% hull, hive
   +50% hull and a 20% faster script). Locked locations (the gate before
   all five middle worlds are held, the core before the gate) show
   "SEALED" and cannot be entered.
4. **Win.** The location is claimed and saved at once. The tug returns to
   space just outside the marker with the hull, parts and dash charges it
   had at the end of the fight.
5. **Repair.** Flying through a held station (kind `station`, not home)
   repairs 25 hull, once per station per loop.
6. **Ambush.** A patrol that touches the tug starts an ambush fight: one
   short wave. Winning destroys that patrol and claims nothing.
7. **End.** The loop ends when the player docks at home (Enter or confirm
   inside the home ring) or dies in a fight. Then:
   - carried salvage is banked in full on docking, or half (rounded down)
     on death;
   - the yields of every held location are added;
   - the swarm turn runs as in the strategy map;
   - the loop-end card shows the report, and any radio log now due plays
     from the card instead of at the next launch.
8. **Warden.** Killing the Warden at WARDEN CORE wins the war immediately;
   there is no flight back.

Closing the window during flight ends the loop as a death, like closing it
during combat today.

## 3. Flight

| Rule | Value |
| --- | --- |
| World size | 2400 × 1920 px (three screens each way) |
| Layout | `system.json` positions × 3 |
| Speed off a lane | 260 px/s, with drift (velocity eases toward input over 0.25 s) |
| Speed on a lane | × 1.6 |
| On a lane | within 40 px of a lane segment |
| Ash wear off a lane | 1 hull every 4 s |
| Dash | as in combat, needs a thruster |
| Weapons | none in flight |
| Location marker radius | 48 px |
| Home dock ring | 90 px |

**Camera.** Follows the tug, clamped to the world edges.

**HUD.** Hull, carried salvage, dash charges. Also the name and owner of
the nearest location, and a prompt: DOCK at home, LAND on planets (shown as
"LAND — ground forces not ready" for now), SEALED on locked ones.

**Radar.** A circle in a corner, range 900 px. It shows locations coloured
by owner, patrols as rust dots, and an arrow toward home.

**System chart.** Tab toggles an overlay of the whole system: owners,
hives, fortifications, patrols and the tug. F on the chart fortifies the
selected held location, as on today's map. The chart is also reachable from
the hangar.

## 4. Patrols

- **Count.** One per two swarm locations (rounded down), plus one per hive,
  capped at 6. Recomputed at undock; patrols destroyed in ambushes stay
  gone for the loop.
- **Spawn.** On lanes touching swarm ground, at least 600 px from the tug.
- **Wander.** Each follows lanes at 140 px/s, picking a random next lane at
  each location (seeded RNG), never entering held ground.
- **Detect.** It spots the tug within 320 px, or 160 px while the tug is on
  a lane.
- **Chase.** At 220 px/s toward the tug, slower than the tug on a lane but
  faster than off it.
- **Lose interest.** After 4 s with the tug outside its detection range it
  goes back to wandering from the nearest lane point.
- **Catch.** Contact within 26 px starts an ambush.

## 5. Fights

- A fight is `GameplayScene(game, fight=FightSpec(...))`:
  - it plays one encounter;
  - it starts from the carried hull, loadout and dash state;
  - it skips the opening drift and starts after a 1.5 s "contact" beat;
  - on win, it hands back the outcome instead of ending the loop.
- **Ambush** is a new encounter: index 6, "AMBUSH", 25 s, drones and
  zigzaggers, scaled like any other.
- **Death** in a fight ends the loop through the usual death beat and the
  loop-end card.
- **Echoes** are keyed by encounter type (the base encounter index, 6 for
  ambushes), so past runs that fought any Graveyard-type location fly in
  every Graveyard-type fight.
  - One loop records every fight it flies.
  - Roster selection and echo pressure work as today.
  - Existing saved echoes stay valid.
- **Records.** "Reached" for a loop is the highest encounter index won.

## 6. Campaign rule changes

- Remove `MAX_ROUTE`, `valid_route`, `valid_prefix` and `route_encounters`.
  Add `can_engage(system, state, node_id)`, true for any location that is
  not held, not home and not locked, and `encounter_for(system, state,
  node_id)`, the twisted encounter for one location.
- **`claim(state, node_id)`** marks a location held and clears its hive age.
  It is called and saved the moment a fight is won.
- **`end_turn(system, state, carried, died, warden_killed, rng)`** replaces
  `apply_run`. It banks salvage, adds yields, runs the swarm turn unless the
  Warden fell, advances the turn, and returns the `TurnReport`.
  - The report lists every location claimed this loop.
- **`patrol_count(state)`** follows section 4.
- The swarm, hive, fortify, requisition and win/lose rules are unchanged.
- `CampaignState` gains `claimed_this_loop: list[str]` so a crash mid-loop
  still reports correctly; save version stays 2 (the field defaults to
  empty).

## 7. Architecture

- **`space_shooter/flight.py`** (new, pure, no pygame):
  - world scaling;
  - lane geometry (nearest point, on-lane test);
  - tug movement with drift, lane boost and ash wear;
  - patrol state and its wander, detect, chase and give-up steps;
  - the repair ledger.
- **`space_shooter/scenes/flight.py`** (new): the flight scene. It owns the
  run state:
  - hull, loadout, dash, carried salvage;
  - the echo recorder;
  - the claimed and repaired sets.
  It draws space, lanes, markers, patrols, the tug, the HUD and the radar,
  and opens fights.
- **`space_shooter/scenes/chart.py`** (new): replaces `scenes/map.py`.
- **`scenes/gameplay.py`:** gains the single-fight mode and loses the route
  mode. The classic six-encounter mode stays (success criterion 5).
- **`scenes/hangar.py`:** LAUNCH opens flight, and a CHART item is added.
- **`campaign.py`:** the changes in section 6.
- **`encounters.py`:** adds the AMBUSH encounter.

## 8. Testing

- **Unit:**
  - lane geometry and on-lane test;
  - speed on and off lanes;
  - ash wear timing;
  - patrol spawn distance, wander, detect ranges on and off lanes, chase,
    give-up timing;
  - patrol count;
  - repair once per station;
  - `can_engage` with locks;
  - `claim`;
  - `end_turn` banking (dock vs death), yields, swarm turn, Warden win.
- **Integration (headless, real scenes):**
  - undock, fly to a location, win, return to space at the marker with hull
    carried, then dock and read the card;
  - die in a fight and keep the claim, with half the salvage;
  - get caught by a patrol and survive the ambush;
  - a sealed gate refuses entry;
  - window close mid-flight ends the loop;
  - a radio log due at loop end plays from the card.
- **Headless autopilot:** five loops, seeded, flying to the nearest
  engageable location each time; the map changes and nothing errors.
- **Balance:** re-run the campaign simulation with free choice of targets
  and report win rate and length in the plan's results.
