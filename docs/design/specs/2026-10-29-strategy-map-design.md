# Strategy map — design

Date: 2026-10-29
Status: approved; rules marked *tuned* were changed by the campaign balance pass in Task 5
Builds on: `2026-10-28-act1-core-loop-design.md`, `2026-10-29-salvage-overhaul-challenge-design.md`

## 1. Purpose

Turn Act 1 from a fixed run into a war. Each loop becomes one turn of a
campaign on a star-system map: you choose where to fight, winning takes
ground, and a swarm spreads between loops toward your home station.

### Decisions made in conversation

- Each loop is one campaign turn. The map persists between loops.
- Each turn you plan a route of up to three locations, borrowing the
  "choice within a run" idea.
- Pressure keeps building: the swarm spreads every loop, faster as time
  passes, and ignored ground becomes hives.
- One star system of 14 locations in three rings; campaigns of roughly 7 to
  12 loops (tuned in Task 5; the first draft aimed for 15 to 25).
- Win by killing the Warden at the core. Lose if the swarm takes home: the
  map resets but echoes, records and story flags stay.

### Success criteria

1. From the hangar, a player can open the map, plan a valid route, fly it,
   and see the map change afterwards: claimed ground, swarm spread, hives.
2. A full campaign can be won (Warden killed at the core) and lost (home
   taken), and both outcomes are recorded and recoverable.
3. All campaign rules live in a pygame-free module and are unit-tested; a
   headless test plays a campaign through several turns.
4. Existing Act 1 behaviour (the classic six-encounter run) still works for
   tests and stays reachable in code.

## 2. The system

Fourteen locations defined in `space_shooter/data/system.json`. Each has an
id, name, ring, kind (station, field, planet, gate, core), the base
encounter it plays as, a yield, an optional `ground` flag (planets, reserved
for milestone 3), a screen position, and lanes to its neighbours.

| Id | Name | Ring | Plays as | Yield |
| --- | --- | --- | --- | --- |
| home | ANCHOR STATION | home | — | 0 |
| o1 | COLD WAKE FIELD | outer | Cold Wake | 100 |
| o2 | RUSTED BUOY | outer | Cold Wake | 100 |
| o3 | ASH DRIFT | outer | Ash Shelf | 100 |
| o4 | THE SHELF | outer | Ash Shelf | 100 |
| o5 | BONEYARD | outer | Graveyard | 100 |
| o6 | SALT LINE | outer | Picket Line | 100 |
| m1 | KESS (planet) | middle | Graveyard | 300 |
| m2 | VARO STATION | middle | Picket Line | 300 |
| m3 | HALE (planet) | middle | Last Light | 300 |
| m4 | ORIN DOCKS | middle | Picket Line | 300 |
| m5 | MERE (planet) | middle | Last Light | 300 |
| c1 | SHELF GATE | core | Last Light | 0 |
| c2 | WARDEN CORE | core | The Warden | 0 |

Lanes:

- **Home:** home–o1, home–o2.
- **Outer ring:** o1–o3, o2–o4, o3–o5, o4–o6.
- **Outer to middle:** o1–m1, o2–m2, o3–m1, o3–m3, o4–m2, o4–m4, o5–m3, o6–m4.
- **Middle ring:** m1–m2, m1–m5, m2–m5, m3–m5, m4–m5.
- **Middle to core:** m3–c1, m4–c1, m5–c1, and c1–c2.

The swarm starts holding o5 and o6. Home starts yours; everything else is
neutral.

## 3. A turn

1. **Plan.** In the hangar, LAUNCH opens the map. You build a route of 1 to 3
   locations:
   - the first is adjacent to home or to a location you hold;
   - each next one is adjacent to the previous;
   - none is home, none is already yours, and none repeats;
   - SHELF GATE is locked until you hold all 5 middle-ring locations
     (*tuned*, was 4), and WARDEN CORE is reachable only from the gate.
2. **Fly.** The run is the route's encounters back to back, with drifts
   between them. Each location plays as its base encounter with twists:
   - +25% enemy hull if the swarm holds it;
   - +50% hull and a 20% faster script if it is a hive.
3. **Claim.** Every location fully cleared becomes yours. If you die, you keep
   everything you cleared before the death. Clearing the whole route also
   ends the loop.
4. **Earn.** Salvage from the run plus the yield of every location you hold
   is added to your campaign salvage.
5. **Swarm turn.** See section 4. Then the loop counter advances.

## 4. The swarm

- **Spread count per turn:** 1 + turn ÷ 6 (rounded down, *tuned*, was ÷ 4),
  capped at 3, plus 1 for every two hives.
- **Targets:** non-swarm locations adjacent to swarm ground. The swarm picks
  the one closest to home by lane distance; ties break with the seeded RNG.
  - *Tuned:* it takes neutral ground first and turns on yours only when no
    neutral target is left.
  - *Tuned:* home is the last stand. It is attacked only when it is the
    swarm's only target.
  - Why: under the first draft the swarm reached home in three turns
    (o6, o4, o2, home) whatever the player did, and it retook the ground
    next to home every turn, so claims never stuck.
- **Fortified targets:** taking a fortified location removes the
  fortification instead and still uses up that spread.
- **Your ground:** if the swarm takes a location you hold, it is lost.
- **Home:** if the swarm takes home, the war is lost.
- **Hives:** a location the swarm has held for 3 turns in a row becomes a
  hive. A hive taken back by you stops being a hive.

## 5. Salvage

- Earned per loop: run salvage value plus the yields of held locations.
- Spent in the hangar SHIPYARD, between loops:
  - **Requisition** a part (800): up to two parts fitted at the next launch,
    used for that loop only.
  - **Fortify** a held location (1000), from the map: it survives one swarm
    attack.

## 6. Win and lose

- **Win:** kill the Warden at WARDEN CORE. Act 1 is complete (flags and
  `act1_complete` as today). The next launch starts a fresh campaign.
- **Lose:** the swarm takes home. Flag `war_lost`, and a fresh campaign
  starts at the next launch. Echoes, records and story flags are kept.

## 7. Story

Six new radio logs:

| Id | Speaker | Plays when |
| --- | --- | --- |
| m_first_claim | pilot | `flag:node_claimed` |
| m_first_lost | fleet | `flag:node_lost` |
| m_first_hive | unknown | `flag:hive_formed` |
| m_home_threat | fleet | `flag:home_threatened` (the swarm is adjacent to home) |
| m_gate_open | warden | `flag:gate_open` |
| m_war_lost | pilot | `flag:war_lost` |

The bundled log count becomes 26.

## 8. Screens

- **Map screen**, in the cockpit style:
  - locations drawn as markers on lanes, coloured steel for yours, rust for
    the swarm's, pulsing ember for hives, bone for home, and ash for neutral;
  - locked locations are drawn dim;
  - the planned route is highlighted;
  - a side panel shows the selected location's name, encounter, yield, owner
    and fortification, plus campaign salvage and turn number.
- **Map controls:** arrows move the selection to the nearest location in that
  direction; mouse click selects. Enter adds or removes the selection from
  the route. F fortifies a held location. L launches. Esc goes back.
- **Shipyard** (new hangar menu item): a list of the six parts with
  requisition cost, the current requisition, and campaign salvage.
- **Loop-end card:** also lists what changed on the map (claimed, lost, hives
  formed, swarm near home), and shows "ROUTE CLEARED", "THE WAR IS LOST" or
  "THE WARDEN IS SILENT" as its title when one applies.

## 9. Architecture

- `space_shooter/campaign.py` (new, pure):
  - `System` and `Node`, loaded and validated from `system.json`;
  - `CampaignState` with `to_dict` and `from_dict`;
  - `new_campaign`, `valid_route`, `route_encounters`, `apply_run`,
    `swarm_turn`, `requisition`, `fortify`, `locked`.
- `space_shooter/encounters.py`:
  - `Encounter` gains `hull: float = 1.0`;
  - `EncounterDirector` completes after its last encounter instead of
    index 5;
  - the `act_complete` event becomes `run_complete`.
- `space_shooter/save.py`: version 2 adds `campaign: dict | None`; version 1
  saves load with `campaign = None`.
- `scenes/gameplay.py`: `GameplayScene(game, seed=None, route=None)`.
  - With a route, the director plays the campaign encounters and
    requisitioned parts are fitted at launch.
  - `end_loop` applies the run and the swarm turn.
  - Story and record "reached" use the encounter's base index; echoes stay
    keyed by route position.
- New scenes: `scenes/map.py`, `scenes/shipyard.py`. The hangar's LAUNCH opens
  the map.

## 10. Testing

- **Unit tests:**
  - system data validates;
  - route rules, including adjacency, locked gate and no own ground;
  - encounter twists;
  - claiming on partial and full routes;
  - yields;
  - swarm spread order, count, fortification, hives, home loss;
  - win;
  - requisition and fortify costs and limits;
  - state round trip and save migration.
- **Integration:** hangar to map to route to gameplay to loop-end, with the
  map changed; a route clear ends the loop; a Warden kill wins the campaign;
  losing home resets the campaign and keeps echoes.
- **Headless:** a seeded campaign played by an autopilot for several turns
  without errors.
