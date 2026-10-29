# Act 1 implementation decisions and deferred items

Recorded while implementing `2026-10-28-act1-core-loop.md`. Each ruling is a call made where the plan or spec was silent or wrong, with what it costs if it was the wrong call.

## Rulings

- Ruling: execute on the designated feature branch without a git worktree — the session is pinned to this branch and it is not main — cost if wrong: none, branch is isolated.
- | 3 → 8 | trigger_moment(name) | Task 8 names it public; Task 3 implements moments. Ruling: create GameplayScene.trigger_moment in Task 3 — later task relies on it — cost if wrong: rename |
- Task 1: Ruling: added test_game_persist_sets_notice_when_unwritable after writing Game.persist — verified it fails against a broken persist and passes on the real one — cost if wrong: none
- Task 2: Ruling: committed ruff's formatting of Python blocks in the plan markdown — ruff format covers .md here and CI runs format --check — cost if wrong: none
- Task 2: Ruling: added Drop.pickup_delay (0.8 s for knocked and ejected parts) and Drop.collectable — a knocked part spawned on the ship was re-collected the same frame, defeating the spec's recover-it-if-brave rule — cost if wrong: one constant
- Task 2: Ruling: kept combo.py and the WaveDirector until their planned removal (Tasks 3 and 6) but removed combo use from gameplay now — plan removes combo text in Task 2 and the module in Task 6 — cost if wrong: none
- Task 2: Ruling: boss kills force a rare part drop (two drops became one rare) — spec 6.3 says rares come from Warden phases; keeps the placeholder boss in line — cost if wrong: tuning
- Task 3: Ruling: put loop_hull_multiplier in encounters.py (plan named only the config constants) — pure and testable next to encounter data — cost if wrong: move one function
- Task 3: Ruling: hulks block bullets but not the ship's movement — spec only requires blocking shots; pushing the ship adds collision code for little play value — cost if wrong: players can hide inside a hulk sprite
- Task 3: Ruling: wave-based speed and hull ramps removed; difficulty now comes from authored scripts plus loop scaling — spec 4.4 replaces random waves — cost if wrong: tuning
- Task 3: Ruling: GameOverScene receives director.index + 1 as "wave" until Task 6 replaces it — keeps the old scene working — cost if wrong: none, temporary
- Task 4: Ruling: added gun_volley() in entities/parts.py, shared by Player.try_fire and Echo — echoes must fire exactly what the player's loadout fires — cost if wrong: none
- Task 4: Ruling: GameplayScene.end_loop(victory) introduced now (plan defines it in Task 6) — death must store the trace in this task and Task 6 needs a single loop-closing path — cost if wrong: none
- Task 4: Ruling: echoes are rammed for 2 hits and deal 1 hit to non-boss enemies they touch — spec says echoes collide with enemies but gives no numbers — cost if wrong: tuning
- Task 4: Ruling: echo_lost:<loop> flag is set now (plan puts it in Task 5) — same code path as first_echo_lost — cost if wrong: none
- Task 5: Ruling: the gameplay test fixture `game` silences the radio (empty LogDirector); story tests use `story_game` — otherwise every mechanics test would stall behind a log panel on the first drift — cost if wrong: none, story behaviour has its own tests
- Task 5: Ruling: added test_bad_log_data_starts_silent_with_notice here (Review Focus 2) — owner task for log loading — cost if wrong: none
- Task 6: Ruling: difficulty moved from the old main menu into Settings — the hangar menu in the spec has no difficulty entry but spec section 3 keeps the presets — cost if wrong: one menu item
- Task 6: Ruling: "reached" is the 0-based encounter index everywhere (records, roster, story) — consistent with EncounterDirector.index — cost if wrong: off-by-one in labels only
- Task 6: Ruling: quitting from the hangar never touches the loop; only an open GameplayScene closes a loop on QUIT — Review Focus 1 is about mid-run — cost if wrong: none
- Task 7: Ruling: Warden registers itself in ENEMY_CLASSES from the end of enemies.py (lazy import) — avoids a circular import between enemies.py and warden.py — cost if wrong: none
- Task 7: Ruling: added Warden.arrived flag — the bob above the station line re-entered the arrival branch and silenced all attacks (found by test_collapse_spawns_rings_and_exposes_eye) — cost if wrong: none
- Task 7: Ruling: Collapse phase keeps slow aimed single shots (big rounds) between rings, per plan; volleys use 1.15x bullet speed — tuning not in spec — cost if wrong: tuning
- Task 8: Ruling: drone_sound(rate=None) generates at the mixer's own frequency — a Sound buffer must match the mixer format, so the plan's 22050 default would play at the wrong pitch — cost if wrong: none
- Task 8: Ruling: generated PCM is cached as bytes per process; Sound objects are rebuilt per Game — keeps test runs fast and survives pygame re-init — cost if wrong: none
- Task 8: Ruling: reduced flashing makes the star flare harmless as well as flash-free — spec 4.4 says "disabled to a warning only" — cost if wrong: Last Light is easier with reduced flashing on
- Task 8: Ruling: the player tug is recoloured to steel (procgen.tug_frames) — the palette rule removes bright blue from play — cost if wrong: none
- Task 8: Ruling: hangar shows "LOOP OF ASH" as text instead of the bundled title art, which reads SPACE INVADERS — found in the tone screenshot pass — cost if wrong: none
- Task 8: Ruling: loop-end closing lines re-indexed by encounter (they were shifted by one) — test_closing_line_matches_where_the_loop_ended — cost if wrong: none
- Task 8: Ruling: radio lines moved to the bottom-right of centre so they don't overlap the hull schematic — layout — cost if wrong: none
- Task 9: Ruling: removed X/Shift and pad buttons 1-2 bomb mappings (B now maps to back) — bombs no longer exist and the keys did nothing — cost if wrong: none
- Final: Ruling: HUD marking a finished echo as lost promoted from Minor to Important — it tells the player permanent save data was lost when it was not — cost if wrong: none

## Final review fixes

- damaged echo or record in save.json crashing the hangar every launch — test_damaged_echo_is_dropped_with_notice, test_damaged_record_is_dropped RED→GREEN, suite 206/206
- ash clouds destroying player bullets — test_ash_cloud_hides_but_does_not_destroy_player_bullets RED→GREEN, suite 206/206
- Last Light flare having no shelter (hulks added, hulk drift 6→1.5 px/s) — test_last_light_has_shelter_from_the_flare RED→GREEN, suite 206/206
- encounter logs playing one encounter late (thresholds lowered by one, a1_ash priority 12) — test_encounter_logs_play_in_the_drift_before_their_encounter RED→GREEN, suite 206/206
- hangar re-decoding every echo per frame — test_hangar_decodes_echoes_once RED→GREEN, suite 206/206
- echo ram damage applied every frame of overlap (0.6 s cooldown) — test_echo_contact_damage_has_a_cooldown RED→GREEN, suite 206/206
- HUD marking finished echoes as lost — test_hud_does_not_mark_a_finished_echo_as_lost RED→GREEN, suite 206/206

## Deferred minors

- Warden phases drop no rare parts (spec 6.3)
- hangar roster does not show how far each echo reached (spec 4.2)
- Graveyard hulk breach does nothing if every hulk was already shot
- Warden ring debris thrown upward is never culled (performance only)
- a throwaway sprite Group of blockers is built every frame
- star flare full-screen flash lasts about 0.4 s, not 2 s
- saving mid-combat on echo loss or Warden sighting can hitch about 15 ms on large saves
- a save-reset notice can be overwritten by a bad-logs notice
- Esc or gamepad B in the hangar quits with no confirmation
- echo bullets pass through hulks and debris
- migrated legacy records display COLD WAKE as their encounter
- gameplay.py is about 640 lines against the spec's target of about 400
