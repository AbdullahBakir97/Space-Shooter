# Salvage Overhaul and Challenge Pass Implementation Plan

**Goal:** Give every salvage part a visible, useful signature move, add pair bonuses, and make Normal genuinely challenging.

**Architecture:** All numbers and rules live in pure modules (`salvage.py`, new `dash.py`, `config.py`) and are unit-tested. Sprite and scene code consumes them. Part behaviour helpers move out of `scenes/gameplay.py` into `scenes/salvage_ops.py` so the scene does not grow.

**Tech stack:** Python 3.11+, pygame-ce, pytest, ruff.

**Spec:** `docs/design/specs/2026-10-29-salvage-overhaul-challenge-design.md`

## Global constraints

- Commits are authored by Abdullah Bakir <abdullah.bakir.1997@gmail.com>, with no footer lines.
- Every task ends with `ruff check .`, `ruff format --check .` and `pytest` passing.
- Pure modules (`salvage`, `dash`, `encounters`, `echoes`, `story`, `save`) must not import pygame.

## Baseline (before this plan, Normal, autopilot probe)

| Seed | Hits | Warden fight |
| --- | --- | --- |
| 1 | 4 | 10.7 s |
| 2 | 8 | 33.5 s |
| 3 | 6 | 33.6 s |

Target after Task 6: average hits at least 18, average Warden fight at least 52 s.

## Review focus

1. A dash while a log panel or pause is open must not fire or consume a charge.
2. Losing the last thruster mid-recharge must drop dash charges to zero, not crash.
3. A heavy slug that kills an enemy must not double-count the kill when it also passes through the next one.
4. Shrapnel from a broken plate must never hurt the player or echoes.
5. Echo pressure counts only echoes alive at spawn time; a roster of zero leaves numbers unchanged.

---

### Task 1: Rules and numbers

**Files:** `space_shooter/salvage.py`, new `space_shooter/dash.py`, `space_shooter/config.py`, `space_shooter/encounters.py`; tests `tests/test_salvage.py`, new `tests/test_dash.py`, `tests/test_encounters.py`, `tests/test_gameplay.py` (loop scaling).

**Produces:**
- `salvage.PAIR_NAMES = {"turret": "TWIN TURRETS", "slug": "BROADSIDE", "tractor": "GRAVITY WELL", "armour": "BULKHEAD", "thruster": "AFTERBURNER", "claw": "SCRAPPER"}`
- `Loadout.pairs() -> list[str]` kinds with count ≥ 2, in `PART_TYPES` order.
- `Loadout.heavy_every() -> int | None` (None without a slug, 4, or 3 with BROADSIDE)
- `Loadout.armour_hits() -> int` (2, or 3 with BULKHEAD); `attach` sets `armour_left` from it, and getting BULKHEAD tops up fitted plates to 3.
- `Loadout.dash_charges() -> int` (0, 1, or 2 with AFTERBURNER); `Loadout.dash_recharge() -> float` (2.5, 2.0 with AFTERBURNER, −0.5 per scarred thruster, floor 1.0).
- `Loadout.turret_period() -> float` (0.5, 0.35 with TWIN TURRETS); `Loadout.tractor_range() -> float` (0 without tractor, 360, or 2000 with GRAVITY WELL); `Loadout.drops_scarred() -> bool` (SCRAPPER).
- `Loadout.patch_share()` = `0.10 + 0.15 * min(1, claw effect)`; `salvage.PATCH_HULL = 20`.
- `dash.Dash(max_charges: int, recharge: float)`: `charges: int`, `active: bool`, `try_start() -> bool`, `update(dt)`, `configure(max_charges, recharge)` (clamps charges down, never up), constants `DASH_TIME = 0.18`, `DASH_SPEED = 1100.0`.
- Config: difficulty table from spec 4 (`Difficulty(name, enemy_speed, enemy_hp, enemy_fire_rate, score_mult)`), `ENEMY_BULLET_SPEED = 290.0`, `LOOP_HULL_STEP = 0.04`, `LOOP_HULL_CAP = 0.60`, `WARDEN_BASE_HP = 260`, `ECHO_PRESSURE_HULL = 0.08`, `ECHO_PRESSURE_FIRE = 0.10`.

**Tests (written first):** `test_pairs_detected_in_type_order`, `test_heavy_every`, `test_bulkhead_tops_up_plates`, `test_dash_numbers_from_loadout`, `test_turret_period_and_tractor_range`, `test_scrapper`, `test_patch_share_halved`; `test_dash_charges_recharge_one_at_a_time`, `test_dash_active_window`, `test_dash_configure_clamps_down`, `test_dash_without_charges_refuses`; `test_loop_scaling_caps` (loop 5 → 1.16, loop 30 → 1.60); `test_difficulty_table`.

### Task 2: Turret, heavy slug, claw

**Files:** `space_shooter/entities/parts.py`, `space_shooter/entities/bullets.py`, `space_shooter/entities/player.py`, new `space_shooter/scenes/salvage_ops.py`, `space_shooter/scenes/gameplay.py`; tests `tests/test_entities.py`, `tests/test_gameplay.py`.

**Produces:**
- `PartRig.update(dt, loadout, origin, enemies, damage_mult)` uses `TURRET_RANGE = 900`, picks the enemy nearest the ship, fires bursts of 2 (0.08 s apart) for scarred turrets, uses `loadout.turret_period()`, fires paired turrets on the same tick, and stores `PartRig.aim[slot] -> float` radians for drawing.
- `bullets.HeavySlug(pos, vel, damage=4)`: `pierce = 10**6`, `shove = 28`.
- `gun_volley(x, top, loadout, damage_mult=1.0, heavy=False)` swaps each slug round for a `HeavySlug` when `heavy`.
- `Player.trigger_count`; `try_fire()` passes `heavy=True` on every `loadout.heavy_every()`-th pull.
- `salvage_ops.claw_contacts(scene, dt)`: enemies within 20 px of a claw slot take 2 damage, at most once per 0.3 s per enemy; a claw kill forces a drop.
- Gameplay: heavy hits shove the enemy up 28 px; `_drop` makes part drops scarred when `drops_scarred()`.
- `draw_loadout` draws turret barrels rotated to `rig.aim`.

**Tests:** `test_turret_reaches_top_of_screen`, `test_turret_targets_nearest_to_ship`, `test_scarred_turret_bursts`, `test_twin_turrets_fire_together`, `test_heavy_slug_every_fourth_pull`, `test_broadside_every_third`, `test_heavy_slug_pierces_line_and_shoves`, `test_heavy_kill_counted_once` (Review focus 3), `test_claw_tears_and_forces_drop`, `test_claw_cooldown_per_enemy`, `test_scrapper_drops_are_scarred`.

### Task 3: Tractor, armour, echo bullets vs hazards

**Files:** `space_shooter/scenes/salvage_ops.py`, `space_shooter/entities/bullets.py`, `space_shooter/entities/parts.py`, `space_shooter/salvage.py` (break event), `space_shooter/scenes/gameplay.py`; tests as above.

**Produces:**
- `Bullet.speed_scale: float = 1.0`, applied in `Bullet.update`.
- `salvage_ops.tractor(scene, dt) -> tuple[float, float] | None`: pulls drops within `tractor_range()` toward the ship and returns the beam target for drawing. Knocked-off parts are pulled from any range.
- `salvage_ops.drag_field(scene)`: enemy bullets within 150 px get `speed_scale = 0.6`, others 1.0; only with a tractor.
- `HitOutcome.kind == "armour_broken"` when a plate absorbs its last hit; the player treats it like `"armour"`.
- `salvage_ops.shrapnel(scene, pos)`: 10 radial `PlayerBullet`s at 520 px/s, damage 1, added to `player_bullets` (they never touch the player or echoes).
- Armour sprites draw 0, 1 or 2 crack lines by hits taken.
- Echo bullets collide with hulks and debris exactly like player bullets.

**Tests:** `test_tractor_range_360_pulls_distant_drop`, `test_gravity_well_pulls_from_anywhere`, `test_drag_field_slows_near_bullets_only`, `test_no_drag_without_tractor`, `test_armour_break_reported`, `test_armour_break_spawns_shrapnel`, `test_shrapnel_never_hurts_player` (Review focus 4), `test_echo_bullets_hit_hulks`.

### Task 4: Thruster dash

**Files:** `space_shooter/game.py` (key and pad mapping), `space_shooter/entities/player.py`, `space_shooter/scenes/gameplay.py`, `space_shooter/effects.py`; tests `tests/test_entities.py`, `tests/test_gameplay.py`.

**Produces:**
- Keys X, Left Shift, Right Shift and pad button 2 map to action `"dash"`.
- `Player.dash: Dash`, reconfigured from the loadout every frame; `Player.start_dash(direction) -> bool`; while active the ship moves at `DASH_SPEED` along the normalised direction (up when zero), and `invuln_timer >= remaining dash time`.
- `effects.Afterimage(image, pos)`: a fading copy, spawned every 0.03 s during a dash.
- `GameplayScene.handle_action("dash")` starts a dash only while gameplay is the top scene and the player is alive.

**Tests:** `test_dash_needs_thruster`, `test_dash_moves_fast_and_is_invulnerable`, `test_dash_direction_defaults_up`, `test_afterburner_two_dashes`, `test_losing_thruster_clears_charges` (Review focus 2), `test_dash_ignored_while_paused` (Review focus 1), `test_dash_key_mapping`.

### Task 5: Challenge pass

**Files:** `space_shooter/entities/enemies.py`, `space_shooter/entities/warden.py`, `space_shooter/scenes/gameplay.py`; tests `tests/test_entities.py`, `tests/test_warden.py`, `tests/test_gameplay.py`.

**Produces:**
- `Enemy(..., armed: bool = True)`. Drone: aimed shot every `uniform(2.6, 3.6) / fire_mult` s, armed only from encounter index 1. Zigzag: 3-round spread (±0.25 rad) every `3.0 / fire_mult` s. Diver: 3-round burst at dive start. No enemy fires while `y <= 40`.
- Gameplay spawn applies echo pressure: `hp_mult *= 1 + 0.08 * live`, `fire_mult *= 1 + 0.10 * live`, where `live` = echoes alive at that moment.
- Warden: hull 260, periods 0.75 / 0.95 / 2.6 / 1.1, `on_phase_change` → `world.warden_phase_drop(center)` drops one scarred part on entering phases 2 and 3.

**Tests:** `test_drone_unarmed_in_cold_wake`, `test_drone_fires_aimed_when_armed`, `test_zigzag_fires_spread`, `test_diver_bursts_on_dive`, `test_enemies_hold_fire_off_screen`, `test_echo_pressure_scales_spawns`, `test_no_pressure_without_echoes` (Review focus 5), `test_warden_numbers`, `test_warden_phase_changes_drop_scarred_parts`; existing Warden tests updated to 260 hull.

### Task 6: HUD, docs, balance check

**Files:** `space_shooter/hud.py`, `README.md`, `docs/design/plans/2026-10-29-salvage-overhaul-challenge.md` (results); tests `tests/test_effects.py`.

**Produces:**
- HUD: dash pips beside the hull cells (filled per charge, outline when recharging); active pair names listed under the parts count.
- README part table and controls updated (dash), difficulty table updated.
- Balance probe re-run on seeds 1 to 3; numbers recorded in this plan's results section and the commit message. If the target is missed, tune `config.py` numbers only and re-run.

**Tests:** `test_hud_draws_with_every_pair_active`, `test_hud_lists_pair_names`.

## Results

Balance probe after Task 6, Normal, same autopilot and seeds as the baseline:

| Seed | Hits (before → after) | Warden fight (before → after) |
| --- | --- | --- |
| 1 | 4 → 21 | 10.7 s → 59.7 s |
| 2 | 8 → 34 | 33.5 s → 99.1 s |
| 3 | 6 → 21 | 33.6 s → 84.9 s |

Average hits 6 → 25 (target 18) and average Warden fight 26 s → 81 s (target 52).

Tuning needed to get there:
- Warden base hull went 260 → 600.
- Normal fire rate went 1.5 → 1.8, and Hard 2.0 → 2.4.
- The slug cannon's normal round went 3 → 2 damage, scarred 5 → 3. It fired on every trigger pull and was half of all damage dealt to the Warden.

The autopilot never dodges or dashes, so a real player will take fewer hits.

## Decisions

- **Warden hull tests moved earlier.** They were updated in Task 1, because the hull number lives in config and changed there.
- **The death test now loops until the ship actually dies.** On the harder Normal, a warm-up ram plus the guaranteed first drop could absorb a single lethal hit.
- **Turret range test replaced.** The old 260 px range test is now `test_turret_reaches_top_of_screen`.
- **Values the spec left open.** Heavy slug 4 (scarred 6) and claw 2 (scarred 3) damage; claw reach is 20 px plus the enemy's collision radius.
- **Armour.** The last absorbed hit now reports `armour_broken`.
- **Drag field.** It is drawn as a faint ring whenever a tractor is fitted.
- **Thrusters.** A newly fitted thruster arrives with its charge.
- **Slug damage.** The slug's base damage was tuned in `entities/parts.py`, not `config.py`, because that is where the number lives.
