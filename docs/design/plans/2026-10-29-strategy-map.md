# Strategy Map Implementation Plan

**Goal:** Make each loop a turn of a campaign on a 14-location star-system map with a spreading swarm, salvage spending, and a win at the Warden's core.

**Architecture:** A pure `campaign.py` owns every rule and is tested without pygame. The encounter director generalises from the fixed six-encounter run to any route. Gameplay applies the run to the campaign at loop end. Two new scenes, the map and the shipyard, sit between the hangar and gameplay.

**Spec:** `docs/design/specs/2026-10-29-strategy-map-design.md`

## Global constraints

- Commits are authored by Abdullah Bakir <abdullah.bakir.1997@gmail.com> with no footer lines, and nothing in the repository mentions an AI assistant.
- Every task ends with `ruff check .`, `ruff format --check .` and `pytest` passing.
- `campaign.py`, `save.py`, `encounters.py` and `story.py` must not import pygame.

## Review focus

1. A route given to `GameplayScene` that became invalid since it was planned must not crash. A stale save or a swarm flip can cause this; the scene should drop the invalid tail.
2. Dying in the drift before the first encounter claims nothing and still runs the swarm turn.
3. A campaign that is won or lost must start fresh on the next launch, never resume a finished state.
4. Requisitioned parts must be spent exactly once, even if the player quits mid-run.
5. A version 1 save with echoes and records must load into version 2 with `campaign = None`, losing nothing.

---

### Task 1: Campaign rules

**Files:** new `space_shooter/campaign.py`, new `space_shooter/data/system.json`; test `tests/test_campaign.py`.

**Produces:**
- `@dataclass(frozen=True) Node(id, name, ring, kind, template: int, yield_: int, ground: bool, pos: tuple[int, int])`.
- `System(nodes: dict[str, Node], lanes: dict[str, frozenset[str]])` with `neighbours(id)` and `distance_to_home(id)`; `load_system(path=None) -> System` validates that ids are unique, lanes are symmetric, home exists and templates are 0 to 5.
- `@dataclass CampaignState(owner: dict[str, str], hive_age: dict[str, int], fortified: set[str], salvage: int = 0, turn: int = 0, status: str = "active", requisition: list[str])`, with `to_dict()` and `from_dict()`. Owner values are `player`, `swarm` or `neutral`; status is `active`, `won` or `lost`.
- `new_campaign(system) -> CampaignState`: home is the player's, o5 and o6 the swarm's.
- `locked(system, state, node_id) -> bool`: c1 needs at least 4 middle-ring locations held, and c2 needs c1 held.
- `valid_route(system, state, route) -> bool`, following the spec's section 3 rules.
- `route_encounters(system, state, route) -> tuple[Encounter, ...]`: copies of the base encounters with `hull` 1.25 on swarm ground, or 1.5 with script times ×0.8 on hives.
- `@dataclass TurnReport(claimed: list[str], lost: list[str], hives: list[str], fortify_spent: list[str], home_threatened: bool, status: str, salvage_gained: int)`.
- `apply_run(system, state, route, cleared: int, run_salvage: int, warden_killed: bool) -> TurnReport` claims the first `cleared` locations and adds salvage plus yields. Killing the Warden sets status `won`. Otherwise it calls `swarm_turn`, then advances `turn`.
- `swarm_turn(system, state, rng, report)`: spread count and target order exactly as in spec section 4.
- Constants `PART_COST = 800`, `FORTIFY_COST = 1000`, `MAX_REQUISITION = 2`; `requisition(state, kind) -> bool`, `fortify(state, node_id) -> bool`.

**Tests (written first):** `test_system_loads_and_validates`, `test_bad_system_rejected`, `test_new_campaign_owners`, `test_route_rules`, `test_gate_locked_until_four_middle`, `test_route_encounter_twists`, `test_apply_run_claims_and_earns`, `test_partial_run_claims_prefix`, `test_swarm_spreads_toward_home`, `test_spread_count_grows`, `test_fortified_node_survives_once`, `test_swarm_takes_player_ground`, `test_hive_forms_after_three_turns`, `test_home_taken_loses`, `test_warden_win`, `test_requisition_and_fortify_costs`, `test_state_round_trip`.

### Task 2: Save version 2 and a director for any route

**Files:** `space_shooter/save.py`, `space_shooter/encounters.py`, `space_shooter/scenes/gameplay.py`; tests `tests/test_save.py`, `tests/test_encounters.py`.

**Produces:**
- `SAVE_VERSION = 2`; `SaveData.campaign: dict | None = None`; version 1 files load with `campaign = None` and are written back as version 2.
- `Encounter.hull: float = 1.0`; gameplay multiplies spawn hull by it.
- `EncounterDirector` completes after its last encounter and emits `("run_complete", None)` instead of `act_complete`; `cleared: int` counts fully cleared encounters.
- Warden checks in gameplay use `director.encounter.index == WARDEN_INDEX`, not the route position.

**Tests:** `test_v1_save_migrates_without_loss` (review focus 5), `test_campaign_round_trip_in_save`, `test_director_completes_short_route`, `test_director_counts_cleared`, `test_encounter_hull_applies`.

### Task 3: Campaign runs in gameplay

**Files:** `space_shooter/scenes/gameplay.py`, `space_shooter/scenes/loop_end.py`, `space_shooter/game.py`; test `tests/test_campaign_play.py`.

**Produces:**
- `Game.campaign() -> CampaignState` loads `save.campaign`, or starts a new campaign when it is missing, won or lost (review focus 3); `Game.store_campaign(state)` writes it back.
- `GameplayScene(game, seed=None, route=None)`: with a route, the director uses `route_encounters` for the valid prefix of that route (review focus 1), requisitioned parts are fitted at launch and cleared from the state at once (review focus 4), and a `run_complete` event ends the loop as cleared.
- `end_loop` calls `apply_run` with the cleared count, run salvage and whether the Warden fell, then stores the campaign, sets flags (`node_claimed`, `node_lost`, `hive_formed`, `home_threatened`, `gate_open`, `war_lost`) and attaches the `TurnReport` to `RunResult.report`.
- `RunResult.report: TurnReport | None`; the loop-end card lists the report and uses the titles from spec section 8.

**Tests:** `test_route_run_claims_cleared_nodes`, `test_clearing_route_ends_loop`, `test_death_in_first_drift_claims_nothing` (review focus 2), `test_requisition_fitted_once`, `test_stale_route_is_trimmed`, `test_warden_kill_wins_campaign`, `test_war_lost_resets_and_keeps_echoes`, `test_loop_end_card_lists_report`.

### Task 4: Map, shipyard, hangar and story

**Files:** new `space_shooter/scenes/map.py`, new `space_shooter/scenes/shipyard.py`, `space_shooter/scenes/hangar.py`, `space_shooter/data/act1_logs.json`; tests `tests/test_map_scene.py`, `tests/test_story.py`, `tests/test_scenes.py`.

**Produces:**
- `MapScene(game)`: `selected: str`, `route: list[str]`, `move(direction)`, `toggle()`, `fortify_selected()`, `launch()`; draws per spec section 8.
- `ShipyardScene(game)` with a menu of the six parts plus BACK.
- The hangar menu becomes LAUNCH, SHIPYARD, LOG ARCHIVE, RECORDS, SETTINGS, QUIT, and LAUNCH opens the map. The first launch's opening log closes into the map.
- Six new logs, for 26 in total.

**Tests:** `test_map_moves_selection_by_direction`, `test_map_builds_only_valid_routes`, `test_map_launch_starts_route`, `test_map_fortify_spends_salvage`, `test_shipyard_requisitions`, `test_hangar_launch_opens_map`, the bundled-logs count of 26, and `test_campaign_logs_trigger`.

### Task 5: Docs, headless campaign, review

**Files:** `README.md`, this plan's results; test `tests/test_campaign_play.py`.

**Produces:** a README section on the war; `test_headless_campaign_autopilot` (five turns, no errors, the map changes); screenshots checked; a fresh review of the branch.
