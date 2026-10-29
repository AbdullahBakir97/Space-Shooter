# Flyable Star System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static war map with a star system the player flies through in real time, fighting at the locations they choose and docking home to end the loop.

**Architecture:**
- A pure `flight.py` owns movement, lanes and patrols.
- A `CampaignRun` object owns one loop's run state (tug, recorder, carried salvage, claims) and closes the loop exactly once.
- A new flight scene drives the run and pushes the existing combat scene, in a new single-fight mode, for each fight.

**Tech Stack:** Python 3.11+, pygame-ce 2.5, pytest (SDL dummy drivers), ruff.

**Spec:** `docs/design/specs/2026-10-29-flyable-map-design.md`

## Global Constraints

- Commits are authored by Abdullah Bakir <abdullah.bakir.1997@gmail.com> with no footer lines; nothing in the repository mentions an AI assistant.
- Every task ends with `ruff check .`, `ruff format --check .` and `python -m pytest` passing.
- `campaign.py`, `flight.py`, `encounters.py`, `echoes.py`, `save.py` and `story.py` must not import pygame.
- The classic six-encounter run (`GameplayScene(game)` with no run) keeps working and its tests keep passing.
- Save version stays 2.

## Review Focus

1. **Ash wear takes the hull to zero in flight.** The loop must end as a death (card shown, half salvage) with no fight starting and no negative hull. Test: `test_ash_death_in_flight_ends_loop` (Task 4).
2. **A patrol catches the tug on the same frame it touches a location marker.** Exactly one fight must start: the location wins and the patrol waits. Test: `test_one_fight_per_frame` (Task 4).
3. **Two fights of the same encounter type in one loop.** Only the first is recorded into the echo, so playback never mixes two segments. Test: `test_repeat_type_not_recorded_twice` (Task 3).
4. **The window closes during a fight pushed over the flight scene.** The loop closes once, with no second turn applied. Test: `test_window_close_mid_fight_closes_once` (Task 3).
5. **The Warden dies.** The war is won without docking, and no later dock or death closes the loop again. Test: `test_warden_kill_wins_without_docking` (Task 3).

---

### Task 1: Campaign rules for free flight

**Files:**
- Modify: `space_shooter/campaign.py`
- Modify: `space_shooter/encounters.py`
- Test: `tests/test_campaign.py`, `tests/test_encounters.py`

**Interfaces:**
- Produces:
  - `can_engage(system, state, node_id) -> bool`: not home, not held, not locked.
  - `encounter_for(system, state, node_id) -> Encounter`: renamed to the location and twisted (swarm `hull=1.25`; hive `hull=1.5` with script times ×0.8).
  - `claim(state, node_id) -> None`: owner becomes `player`, hive age is cleared, and the id is appended to `state.claimed_this_loop` if it isn't there already.
  - `end_turn(system, state, carried: int, died: bool, warden_killed: bool, rng) -> TurnReport`:
    - banks `carried // 2` if `died`, else `carried`;
    - adds the yields of held ground; `salvage_gained` = banked + yields;
    - sets `report.claimed = list(state.claimed_this_loop)`, then clears the list;
    - a Warden kill sets status `won`, otherwise the swarm turn runs;
    - `turn += 1`.
  - `patrol_count(state) -> int`: `min(6, swarm_count // 2 + hive_count)`.
  - `CampaignState.claimed_this_loop: list[str]` (default empty) in `to_dict`/`from_dict`; `from_dict` accepts dicts without it.
  - `from_dict` raises `ValueError` when `owner` or `hive_age` is not a dict, and it drops unknown part kinds from `requisition`. `Game.campaign()` treats any of these as a damaged war and starts fresh (review finding from the strategy map).
  - `encounters.AMBUSH = Encounter(6, "AMBUSH", 25, ...)`: a script of drones and zigzaggers only, not in `ENCOUNTERS`.
  - `EncounterDirector(rng, encounters=ENCOUNTERS, first_drift: float = DRIFT_TIME)`.
- Removes: `MAX_ROUTE`, `valid_route`, `valid_prefix`, `route_encounters`, `apply_run`. Their tests are deleted or rewritten onto the new functions. `gameplay.py` still calls them until Task 3, so Task 1 leaves temporary wrappers marked `# removed in Task 3` to keep the suite green.

- [ ] **Step 1: Write the failing tests** in `tests/test_campaign.py`:
  - `test_can_engage_rules`: o1 yes; home no; held o1 no; m5 yes (no adjacency needed now); c1 no until all five middle are held; c2 no until c1 is held.
  - `test_encounter_for_twists`: the hive on o6 gives hull 1.5 and the script ×0.8, swarm o5 gives 1.25, neutral o1 gives 1.0, and the name is `"COLD WAKE FIELD"`.
  - `test_claim_records_once`: claiming o1 twice gives owner player and `claimed_this_loop == ["o1"]`.
  - `test_end_turn_dock_banks_all`: carried 500 with o1 held gives `salvage_gained == 600`, and `report.claimed` is the loop's claims, then the list is cleared.
  - `test_end_turn_death_banks_half`: carried 501 and died gives banked 250.
  - `test_end_turn_warden_wins`: no swarm move, status `won`.
  - `test_patrol_count`: start (2 swarm) gives 1; 9 swarm with 3 hives gives min(6, 4 + 3) = 6.
  - `test_state_round_trip` extended with `claimed_this_loop`; an old dict without the key loads.
  - `test_damaged_state_rejected`: `{"owner": [1, 2]}` raises `ValueError`, and `requisition: ["bogus", "claw"]` loads as `["claw"]`.

  In `tests/test_encounters.py`:
  - `test_ambush_encounter`: index 6, 25 s, kinds ⊆ {drone, zigzag}.
  - `test_director_first_drift`: `first_drift=1.5` reaches `active` after 1.5 s.
- [ ] **Step 2: Run** `python -m pytest tests/test_campaign.py tests/test_encounters.py -q`. Expected: FAIL (names not defined).
- [ ] **Step 3: Implement** the interfaces above. `encounter_for` is the one-node body of the old `route_encounters`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: campaign rules for free flight`.

### Task 2: Flight rules

**Files:**
- Create: `space_shooter/flight.py`
- Test: `tests/test_flight.py`

**Interfaces:**
- Consumes: `campaign.System`, `campaign.CampaignState`, `campaign.patrol_count`.
- Produces:
  - Constants: `SCALE = 3`, `WORLD = (2400, 1920)`, `BASE_SPEED = 260`, `LANE_BOOST = 1.6`, `LANE_WIDTH = 40`, `ASH_PERIOD = 4.0`, `EASE = 0.25`, `MARKER_RADIUS = 48`, `DOCK_RADIUS = 90`, `PATROL_SPEED = 140`, `CHASE_SPEED = 220`, `DETECT = 320`, `DETECT_ON_LANE = 160`, `GIVE_UP = 4.0`, `CATCH = 26`, `SPAWN_CLEARANCE = 600`, `REPAIR = 25`, `RADAR_RANGE = 900`, `MAX_PATROLS = 6`.
  - `world_pos(node) -> tuple[float, float]`: the node's `pos` × `SCALE`.
  - `class Lanes`:
    - `Lanes(system)` builds one segment per lane, in world coordinates;
    - `nearest(point) -> tuple[float, tuple[float, float], tuple[str, str]]` gives the distance, the closest point and the lane;
    - `on_lane(point) -> bool` is true when the distance ≤ `LANE_WIDTH`.
  - `@dataclass Tug(x: float, y: float, vx: float = 0.0, vy: float = 0.0, ash: float = 0.0)`. Its method `step(move, dt, on_lane) -> int`:
    - velocity eases toward `move × BASE_SPEED` (× `LANE_BOOST` on a lane), with rate `dt / EASE`, clamped to 1;
    - the position is clamped to `WORLD`;
    - off a lane `ash` accumulates, and the method returns 1 each time it passes `ASH_PERIOD`; on a lane `ash` resets to 0;
    - otherwise it returns 0.
  - `@dataclass Patrol(a: str, b: str, along: float, mode: str = "wander", unseen: float = 0.0, x: float = 0.0, y: float = 0.0)`.
  - `spawn_patrols(system, lanes, state, tug_pos, rng) -> list[Patrol]`:
    - spawns `patrol_count(state)` patrols on lanes with at least one swarm end, each at least `SPAWN_CLEARANCE` from `tug_pos`;
    - returns fewer if no lane qualifies.
  - `step_patrol(p, system, lanes, state, tug_pos, tug_on_lane, dt, rng) -> bool`:
    - wander: moves along `a→b` at `PATROL_SPEED`; at `b` it picks a random neighbour lane whose far end is not held by the player (it reverses if none);
    - it switches to chase when within `DETECT`, or `DETECT_ON_LANE` while the tug is on a lane;
    - chase: moves straight at `CHASE_SPEED`; `unseen` grows while out of range, and at `GIVE_UP` it returns to wander on the nearest lane;
    - it returns True on contact within `CATCH`.
  - `repairable(system, state, node_id, repaired: set[str]) -> bool`: true for a held `station` node, not home, not in `repaired`.

- [ ] **Step 1: Write the failing tests:**
  - `test_world_pos_scales`: home becomes (1200, 1770).
  - `test_on_lane`: the midpoint of home–o1 is on a lane, 41 px off it is not, and the world corner is not.
  - `test_tug_speed_on_and_off_lane`: after 2 s of full input, speed ≈ 260 off a lane and ≈ 416 on one (within 1%).
  - `test_tug_stays_in_world`.
  - `test_ash_wear_every_four_seconds`: 8 s off a lane gives a total of 2, and 8 s on a lane gives 0.
  - `test_patrols_spawn_clear_of_tug`: the count equals `patrol_count`, all ≥ 600 px away, and all on swarm-touching lanes.
  - `test_patrol_wanders_on_lanes`: after 30 s, still on a lane and never on held ground.
  - `test_patrol_detects_by_range`: a tug off a lane at 300 px leads to chase; a tug on a lane at 300 px does not; on a lane at 150 px it does.
  - `test_patrol_gives_up`: the tug moved 1000 px away leads back to wander after just over 4 s, not before.
  - `test_patrol_catch`.
  - `test_repairable`: a held m2 station is repairable once; a held planet m1 is not; home is not.
- [ ] **Step 2: Run** `python -m pytest tests/test_flight.py -q`. Expected: FAIL (no module).
- [ ] **Step 3: Implement** `flight.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: flight rules for lanes, ash and patrols`.

### Task 3: One loop as a run, and single fights in combat

**Files:**
- Create: `space_shooter/scenes/run.py`
- Modify: `space_shooter/scenes/gameplay.py`, `space_shooter/echoes.py`, `space_shooter/game.py` (`close_open_loop`), `space_shooter/scenes/loop_end.py`
- Test: `tests/test_campaign_play.py` (rewritten), `tests/test_echoes.py`

**Interfaces:**
- Consumes: the Task 1 functions; `EncounterDirector(first_drift=)`; `AMBUSH`.
- Produces:
  - `class CampaignRun`, created with `CampaignRun(game, seed: int | None = None)`:
    - **at creation:** it reads `game.campaign()`, builds a `Player()` and fits the requisitioned parts (as the old `_begin_campaign_turn` did), clears `state.requisition` and stores it;
    - **attributes:** `rng`, `state`, `player`, `recorder: EchoRecorder`, `traces: list[EchoTrace]` (roster at undock), `lost_echoes: list[int]`, `carried: int`, `time: float`, `reached: int = -1`, `repaired: set[str]`, `result: RunResult | None`;
    - `roster() -> list[EchoTrace]`: the traces minus the lost ones;
    - `win_fight(node_id: str | None, encounter_index: int, salvage: int) -> None`: adds the salvage to carried and raises `reached`; for a node it calls `campaign.claim` and stores the campaign;
    - `finish(died: bool, warden_killed: bool = False) -> RunResult`, idempotent, does everything the old `end_loop` did, in order:
      - stores the trace;
      - adds a record;
      - `loop += 1`;
      - calls `end_turn`;
      - sets the flags (`node_claimed`, `node_lost`, `hive_formed`, `home_threatened`, `gate_open`, `war_lost`);
      - persists;
      - builds the `RunResult` with `report`.
  - `GameplayScene(game, seed=None, run: CampaignRun | None = None, node_id: str | None = None, encounter: Encounter | None = None)`. With a run, it is in fight mode:
    - the director is `EncounterDirector(rng, (encounter,), first_drift=1.5)`;
    - it uses `run.player` (repositioned to the start point, with health, loadout and dash kept), `run.recorder`, echoes from `run.roster()`, and the echo key `encounter.index`;
    - on `run_complete` it calls `run.win_fight(node_id, encounter.index, self.score)` and pops itself;
    - on death it calls `run.finish(died=True)`, then plays the death beat and the card;
    - on a Warden kill it calls `run.finish(died=False, warden_killed=True)`, then plays the ending;
    - a destroyed echo is appended to `run.lost_echoes`.
  - Route mode and the `route=` parameter are removed, and so are the Task 1 temporary wrappers.
  - The classic mode keeps `end_loop`.
  - `EchoRecorder.has_encounter(key: int) -> bool`. In fight mode, `begin_encounter` is skipped, and samples are not recorded, when the key already exists.
  - `Game.close_open_loop()` also finishes a `FlightScene` run on the stack (`run.finish(died=True)`); the same run inside a fight is finished once.
  - The `LoopEndScene` exit plays the best due radio log (if any) in a `LogPanel` before the hangar.

- [ ] **Step 1: Write the failing tests** in `tests/test_campaign_play.py`. The helpers `fight(game, run, node)` and `clear_current` are reused.
  - `test_fight_win_claims_and_returns`:
    - a fight at o1 is won;
    - o1 is held and saved, `run.carried > 0`, and the top scene is whatever was under the fight;
    - the player's health equals what it was at the end of the fight.
  - `test_fight_death_banks_half_keeps_claims`: win o1, then die at o3. o1 stays held, salvage is banked at half, the card is shown and `turn == 1`.
  - `test_requisition_fitted_once` (focus carried over).
  - `test_repeat_type_not_recorded_twice`: two Cold Wake fights (o1, o2) record one encounter-0 segment.
  - `test_window_close_mid_fight_closes_once`: `close_open_loop` with [flight-like holder, fight] on the stack gives `turn == 1` and `loop == 2`.
  - `test_warden_kill_wins_without_docking`: status `won`, and a later `run.finish(died=True)` returns the same result.
  - `test_war_lost_resets_and_keeps_echoes` (carried over, using `finish`).
  - `test_loop_end_plays_due_log`: with `node_claimed` set, leaving the card shows `m_first_claim` before the hangar.
  - `test_classic_run_unchanged` (an existing test keeps passing).

  In `tests/test_echoes.py`: `test_recorder_has_encounter`.
- [ ] **Step 2: Run** `python -m pytest tests/test_campaign_play.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `run.py` and the gameplay fight mode. Move the bodies of `_close_campaign_turn` and the requisition fitting into `CampaignRun`. Echo pressure counts echoes with `has_encounter(echo_key)`.
- [ ] **Step 4: Run** the full suite. Expected: PASS. The old map tests that call `route=` are deleted in this task.
- [ ] **Step 5: Commit** `feat: run state across fights and single-fight combat`.

### Task 4: Flight scene, system chart and hangar

**Files:**
- Create: `space_shooter/scenes/flight.py`, `space_shooter/scenes/chart.py`
- Delete: `space_shooter/scenes/map.py`, `tests/test_map_scene.py`
- Modify: `space_shooter/scenes/hangar.py`
- Test: `tests/test_flight_scene.py`, `tests/test_chart.py`, `tests/test_scenes.py`

**Interfaces:**
- Consumes: `flight.*`, `CampaignRun`, `GameplayScene(run=, node_id=, encounter=)`, `campaign.can_engage`, `campaign.encounter_for`, `AMBUSH`.
- Produces:
  - `FlightScene(game, seed=None)`:
    - **attributes:** `run`, `tug: Tug` (starting 120 px above home), `lanes`, `patrols`, `pending_patrol`, `camera: tuple[float, float]`;
    - **each update:** first apply ash damage to `run.player.health` (≤ 0 means `run.finish(died=True)` and the card is pushed); then check, in this order:
      1. the dock prompt;
      2. location arrival: an engageable node within `MARKER_RADIUS` pushes its fight; a locked one shows "SEALED";
      3. a repair at a repairable station (+`REPAIR` hull, capped at max);
      4. a patrol catch, which pushes an `AMBUSH` fight and stores `pending_patrol`.
    - **at most one fight per frame**, and when one starts the patrols are not stepped that frame;
    - `on_enter` after a fight pushes the tug to `MARKER_RADIUS + 40` from the node (along the away vector, or straight down if they coincide). It also removes `pending_patrol` if the ambush was won;
    - **controls:** `confirm` within `DOCK_RADIUS` of home calls `run.finish(died=False)` and pushes `LoopEndScene`; `dash` dashes the tug; Tab pushes `ChartScene(game, flight=self)`; `back` pushes `PauseScene`;
    - **drawing:** space, lanes, markers coloured by owner, patrols, the tug (the player sprite rotated to its heading), the HUD (hull, carried salvage, dash, the nearest location's name and owner, the prompt: DOCK at home, SEALED on locked locations, and "LAND — ground forces not ready" on planets), and the radar (`RADAR_RANGE`, owner dots, rust patrol dots, an arrow toward home).
  - `ChartScene(game, flight=None)`:
    - the old map without the route: arrows or a click select, F fortifies, `back` pops;
    - it draws the tug and patrols when `flight` is given.
  - **Hangar menu:** `["LAUNCH", "SHIPYARD", "CHART", "LOG ARCHIVE", "RECORDS", "SETTINGS", "QUIT"]`. LAUNCH does `clear_to(FlightScene(game))`, and the opening log closes into flight.
  - **Pause:** ABANDON from pause in flight ends the loop as a death (`run.finish(died=True)`).

- [ ] **Step 1: Write the failing tests** in `tests/test_flight_scene.py`:
  - `test_launch_undocks_into_flight`.
  - `test_flying_into_location_starts_fight`: placing the tug at o1 and stepping pushes a `GameplayScene` with `node_id == "o1"`.
  - `test_return_after_win_outside_marker`: after the fight, the tug is at least `MARKER_RADIUS` from o1 and no new fight starts.
  - `test_sealed_gate_refused`: the tug on c1 gets no fight, and the prompt says `"SEALED"`.
  - `test_dock_ends_loop`: confirm near home shows the card, salvage is banked in full and `turn == 1`.
  - `test_confirm_far_from_home_does_nothing`.
  - `test_patrol_catch_starts_ambush_and_win_removes_patrol`.
  - `test_one_fight_per_frame` (focus 2): with the tug on o1 and a patrol on the tug, exactly one `GameplayScene` is pushed, with `node_id == "o1"`, and the patrol remains.
  - `test_ash_death_in_flight_ends_loop` (focus 1): with health 1, stepping 4 s off a lane shows the card and banks half.
  - `test_repair_once_per_station`.
  - `test_tab_opens_chart_and_back_returns`.
  - `test_flight_draws_every_state`: patrols, a hive, fortified ground and a low hull all draw without error.

  In `tests/test_chart.py`: selection by direction and click, fortify spends salvage, and every location is reachable by arrows (carried over from `test_map_scene.py`).

  In `tests/test_scenes.py`: the hangar labels, and the first launch's opening log closing into `FlightScene`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the scenes and the hangar wiring. Delete `map.py` and its test.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: fly the star system`.

### Task 5: Autopilot, balance, docs and review

**Files:**
- Modify: `README.md`, `tests/test_campaign_play.py`, this plan (Results), the spec if the tuning changes
- Scratch: the balance simulation in the session scratchpad (not committed)

- [ ] **Step 1:** `test_headless_campaign_autopilot`:
  - five loops through the real screens: hangar LAUNCH, then steer the tug toward the nearest engageable node by setting the move input via a monkeypatched `game.move_vector`;
  - win fights with `clear_current`, then dock or die on alternate loops;
  - the map changes, `turn == 5`, and nothing errors.
- [ ] **Step 2:** Re-run the campaign simulation with free target choice (any engageable node, up to the hull the player has left). Record the win rate and median loops in Results. Tune only if a strong player wins in under 5 loops or loses in under 6.
- [ ] **Step 3:** Update the README:
  - "The war" section: flight, lanes, patrols, docking, controls (Tab chart, Enter dock);
  - the layout entries for `flight.py`, `scenes/flight.py`, `scenes/chart.py`, `scenes/run.py`;
  - the test count;
  - the roadmap: mark the flyable map done.
- [ ] **Step 4:** Take headless screenshots of flight (with patrols and the radar) and the chart, and check them by eye.
- [ ] **Step 5:** Run a fresh review of the branch by a subagent; fix the verified findings with tests.
- [ ] **Step 6:** Commit, push `flyable-map`, open a draft PR into `main` and check its description has no footer.

## Results

- **Tests:** 356 pass headlessly, and lint and format are clean. They include a five-loop headless autopilot through the real screens (undock, fly to a fight, win it, then dock or die).
- **Balance:** a campaign-level simulation, with free choice of targets, 300 seeds per row. Each fight after the first in a loop is made harder by a factor (0.85 or 0.75) to stand in for the hull and parts carried between fights.

  | Player | Fights per loop | Win rate | Median loops to win | Median loops to lose |
  | --- | --- | --- | --- | --- |
  | Strong (skill 1.0) | 3 | 59 to 66% | 5 | 8 |
  | Average (skill 0.9) | 3 | 41 to 50% | 5 | 8 |
  | Weak (skill 0.75) | 2 | 14 to 16% | 6 | 8 |

  A strong player neither wins in under 5 loops nor loses in under 6, so the rules were not retuned. Without any fatigue (an upper bound), a strong player wins in a median of 4 loops.
