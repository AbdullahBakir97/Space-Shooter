# Ground Combat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land on the three planets and fight on foot with hand weapons and a small squad.

**Architecture:**
- A pure `ground.py` holds the whole ground fight as a `GroundWorld`, advanced by `step(dt, GroundInputs)`.
- A `GroundScene` reads input, draws, and reports to `CampaignRun` like the space fight mode does.
- The flight scene opens it for planets.

**Tech Stack:** Python 3.11+, pygame-ce 2.5, pytest (SDL dummy drivers), ruff.

**Spec:** `docs/design/specs/2026-10-29-ground-combat-design.md`

## Global Constraints

- Commits are authored by Abdullah Bakir <abdullah.bakir.1997@gmail.com> with no footer lines; nothing in the repository mentions an AI assistant.
- Every task ends with `ruff check .`, `ruff format --check .` and `python -m pytest` passing.
- `ground.py` must not import pygame.
- Every number in the spec's tables is a module constant in `ground.py`.

## Review Focus

1. **The pilot dies on the same frame the mission completes.** The planet is claimed, the loop ends as a death, and it closes once. Test: `test_death_on_completion_frame` (Task 3).
2. **A survivor or enemy is spawned or pushed into rock.** Bodies never end a step inside a blocking tile. Test: `test_bodies_never_inside_rock` (Task 1).
3. **A grenade is thrown at a point behind a wall.** It lands at the wall, not through it. Test: `test_grenade_stops_at_wall` (Task 1).
4. **Re-landing on a planet already won in this loop.** It is held, so no fight starts. Test: `test_held_planet_does_not_land` (Task 3).
5. **The Esc pause during a ground fight, then ABANDON.** The loop closes once, keeping the ground fight's salvage in carried. Test: `test_abandon_on_ground` (Task 3).

---

### Task 1: Ground map, movement, weapons

**Files:** create `space_shooter/ground.py`; test `tests/test_ground.py`.

**Produces:**
- **Constants** for every number in spec sections 3 and 5.
- `GroundMap`:
  - `generate_map(node_id: str) -> GroundMap`, with `tiles: list[list[int]]` (0 floor, 1 rock, 2 wreck), `pad: (x, y)`, `nests`, `beacon`, `core`, `survivors` and `crates`, as lists or points in world pixels;
  - `blocked(x, y) -> bool`;
  - `line_of_sight(a, b) -> bool`, sampled every 8 px;
  - `cast(a, b) -> point`, the last free point on the segment;
  - `reachable_from_pad(point) -> bool`.
- `Body(x, y, radius, hp, max_hp)`. `move_body(gmap, body, dx, dy)` moves along each axis separately, testing the four corners of the body's box.
- `WEAPONS: dict[str, Weapon]` and `Arsenal`:
  - `owned: list[str]`, `current: str`, `mag: dict`, `reserve: dict`, `grenades`;
  - `select(slot: int)`, `reload()`, `update(dt)`;
  - `trigger(origin, aim, rng) -> list[Shot]`;
  - `give(kind) -> str`, which returns a description of the pickup.
- `Shot(x, y, vx, vy, damage, friendly: bool, life)`.
- `Grenade(x, y, tx, ty, fuse)`.

**Tests (written first):**
- `test_map_size_and_determinism`;
- `test_points_reachable` (all three planets);
- `test_bodies_never_inside_rock` (random moves into walls for 600 steps);
- `test_line_of_sight_blocked_by_rock`;
- `test_weapon_numbers` (the table, exactly);
- `test_rifle_magazine_and_reload`;
- `test_scattergun_pellets_and_spread`;
- `test_sidearm_never_runs_dry`;
- `test_select_only_owned`;
- `test_grenade_stops_at_wall`;
- `test_pickup_gives_weapon_then_ammo`.

### Task 2: The world — pilot, swarm, squad, missions

**Files:** modify `space_shooter/ground.py`; test `tests/test_ground_world.py`.

**Produces:**
- `GroundInputs`: `move=(0, 0)`, `aim=(0, 0)` (world), `fire=False`, `roll=False`, `reload=False`, `slot=None`, `grenade=False`, `order=None` (`"follow"`, `"hold"` or `("move", x, y)`).
- `GroundWorld(node_id, mission, hull=1.0, pace=1.0, seed=0)`:
  - mission is `nests`, `hold` or `carry`, from `MISSIONS = {"m1": "nests", "m3": "hold", "m5": "carry"}`;
  - attributes: `map`, `pilot: Body`, `arsenal`, `enemies`, `survivors`, `shots`, `grenades`, `crates`, `nests`, `score`, `complete: bool`, `carrying: bool`, `hold_time: float`, `objective_text()`, `at_pad() -> bool`.
- `step(dt, inputs) -> list[tuple[str, object]]`, with events `shot`, `hit`, `kill`, `pickup`, `joined`, `survivor_down`, `pilot_hit`, `pilot_dead`, `complete` and `explosion`.
- The roll, enemy behaviour, the flow field, survivors and missions follow spec sections 4 to 7.
- `squad_bonus() -> int` is 100 per survivor alive.

**Tests (written first):**
- `test_pilot_moves_and_rolls_invulnerable`;
- `test_crawler_paths_around_wall`;
- `test_crawler_contact_damage_cooldown`;
- `test_spitter_keeps_range_and_needs_sight`;
- `test_nest_spawns_up_to_cap_only_near`;
- `test_hull_twist_and_hive_pace`;
- `test_bullets_kill_and_score`;
- `test_grenade_damages_enemies_only`;
- `test_survivor_joins_and_follows`;
- `test_hold_and_move_orders`;
- `test_survivor_shoots_visible_enemy`;
- `test_dead_survivor_drops_ammo`;
- `test_nests_mission`;
- `test_hold_mission_needs_presence_and_waves_come`;
- `test_carry_mission`;
- `test_pilot_death_event`.

### Task 3: Ground scene and landing

**Files:**
- create `space_shooter/scenes/ground.py`;
- modify `space_shooter/scenes/flight.py`, `space_shooter/scenes/pause.py` and `space_shooter/game.py`;
- test `tests/test_ground_scene.py`.

**Produces:**
- `GroundScene(game, run, node_id, encounter, seed=None)`:
  - attributes: `world`, `fight_over`, `result`, `node_id`;
  - it builds `GroundInputs` from the keyboard, mouse and gamepad;
  - on `complete` it calls `run.win_fight(node_id, encounter.index, world.score)` at once (claim saved), and the score already paid is not paid again;
  - take-off (confirm at the pad, once complete) adds `squad_bonus()` and any later score to `run.carried`, sets `fight_over` and pops;
  - `end_loop(victory=False)` adds the unpaid score to `run.carried` and returns `run.finish(died=True)`;
  - pilot death runs a 1.2 s beat, then the `LoopEndScene`;
  - drawing: a pre-rendered map surface tinted per planet, entities, the vignette, and a HUD (health, weapon and ammo, grenades, squad and orders, objective and progress, prompt).
- `FlightScene._start_fight` opens a `GroundScene` when the node has `ground`.
- Pause ABANDON and `close_open_loop` call `end_loop` on any scene that has one.

**Tests (written first):**
- `test_flying_into_planet_lands`;
- `test_mission_complete_claims_and_takeoff_returns`;
- `test_takeoff_needs_pad_and_completion`;
- `test_ground_death_ends_loop`;
- `test_death_on_completion_frame`;
- `test_held_planet_does_not_land`;
- `test_abandon_on_ground`;
- `test_window_close_on_ground`;
- `test_ground_draws_every_state`;
- `test_mouse_aim_and_keys`.

### Task 4: Autopilot, docs, review

- [ ] `test_headless_ground_autopilot`:
  - land on KESS from flight with scripted `GroundInputs`;
  - kill the nests by moving near them and firing;
  - take off, then dock.
- [ ] README: a "On the ground" section with the controls; the layout entries; the test count; mark ground combat done in the roadmap.
- [ ] Take headless screenshots of all three planets and check them by eye.
- [ ] Run a fresh review of the branch by a subagent; fix the verified findings with tests.
- [ ] Commit, push `ground-combat`, open a draft PR without a footer, and check it.
