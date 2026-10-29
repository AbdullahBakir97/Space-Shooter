# Loop of Ash Act 1 Implementation Plan

**Goal:** Turn the rebuilt wave shooter into Act 1 of *Loop of Ash*: a time-loop run with echoes of past runs, salvage parts bolted onto the hull, authored encounters, a radio-log story, the Warden boss, and a grim look and sound.

**Architecture:** New pure-logic modules (`save`, `salvage`, `encounters`, `echoes`, `story`) carry the rules and are unit-tested without a display. Thin pygame layers (sprites in `entities/`, scenes in `scenes/`, `procgen` for generated art and audio) consume them. `GameplayScene` becomes a coordinator; combat helpers move out so it stays near 400 lines.

**Tech Stack:** Python 3.11+, pygame-ce 2.5+, pytest, ruff. Standard library only for generation (`array`, `struct`, `base64`, `math`, `random`).

**Spec:** `docs/design/specs/2026-10-28-act1-core-loop-design.md`

## Global Constraints

- Python and pygame-ce only; no new runtime dependencies (no numpy).
- Palette tokens exactly: void `(4, 5, 9)`, steel `(96, 128, 160)`, steel_dim `(48, 60, 76)`, ash `(130, 128, 124)`, rust `(140, 62, 40)`, bone `(210, 205, 196)`, ember `(255, 122, 40)`. Bright cyan, yellow, magenta and green are removed from play.
- Tone: no score popups, no fanfares, no combo text. Log text at most 3 lines, understated, no jokes.
- Every pure module (`save`, `salvage`, `encounters`, `echoes` except drawing, `story`) must import without a display.
- Missing assets, missing mixer, corrupt or unwritable save, bad log data: degrade with a notice, never crash.
- After every task: `ruff check .`, `ruff format --check .` and `pytest` pass, and `python main.py` still launches.

## Review Focus

1. **Closing the window mid-run** must end the loop like a death: the loop counter advances and the trace is kept as an echo. Test in Task 6.
2. **Bad log data** (a user edits `act1_logs.json` into invalid JSON or a bad condition) must start the game with logs disabled and a hangar notice. Test in Task 5.
3. **Unwritable data directory** must not crash on save; `write_save` returns `False` and the hangar shows a notice. Test in Task 1.
4. **Reduced flashing** must also cover the Last Light star flare and the Ash Shelf blackout (warning text only, no full-screen effect). Test in Task 8.
5. **Echo with no data for an encounter** (it died earlier, or the recording is shorter than the player's time) must simply be absent or faded, never raise. Test in Task 4.

## Task order and why it differs from the spec

The spec lists Warden before the hangar. The plan builds the hangar and loop-end card first (Task 6) so the Warden's victory (Task 7) has somewhere to go. Encounters come before echoes because echo playback is keyed to encounter index.

---

### Task 1: Palette, save data, migration, settings flag

**Files:**
- Create: `space_shooter/palette.py`, `space_shooter/save.py`
- Modify: `space_shooter/settings_store.py`, `space_shooter/game.py`
- Test: `tests/test_save.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `palette.VOID, STEEL, STEEL_DIM, ASH, RUST, BONE, EMBER: tuple[int, int, int]`
  - `save.SAVE_FILE = "save.json"`, `save.SAVE_VERSION = 1`, `save.MAX_RECORDS = 10`
  - `save.Sample = tuple[int, float, float, float, bool]` meaning `(encounter, t_rel, x, y, fired)`
  - `@dataclass save.Record(loop: int, reached: int, salvage: int, time: float, difficulty: str = "normal")`
  - `@dataclass save.EchoData(loop: int, reached: int, duration: float, samples: str, loadouts: list[dict])` where `loadouts` items are `{"encounter": int, "t": float, "parts": dict[str, str]}`
  - `@dataclass save.SaveData(version: int = 1, loop: int = 1, echoes: list[EchoData], flags: set[str], read_logs: list[str], records: list[Record], act1_complete: bool = False)` plus a non-persisted `notice: str | None = None`
  - `save.pack_samples(samples: list[Sample]) -> str` and `save.unpack_samples(text: str) -> list[Sample]`
  - `save.load_save(directory: Path | None = None) -> SaveData`
  - `save.write_save(data: SaveData, directory: Path | None = None) -> bool`
  - `save.add_record(data: SaveData, record: Record) -> int | None` (1-based rank or None)
  - `Settings.reduced_flashing: bool = False`
  - `Game.save: SaveData` loaded in `Game.__init__`; `Game.persist() -> None` writes it and sets `save.notice` on failure.

- [ ] **Step 1: Write failing tests in `tests/test_save.py`**

```python
def test_pack_round_trip():
    s = [(0, 0.0, 10.5, 20.25, False), (2, 1.05, 400.0, 500.0, True)]
    back = unpack_samples(pack_samples(s))
    assert [(e, f) for e, _, _, _, f in back] == [(0, False), (2, True)]
    assert [v for row in back for v in row[1:4]] == pytest.approx([v for row in s for v in row[1:4]], abs=1e-4)


def test_round_trip(tmp_path):
    d = SaveData(loop=4, flags={"warden_seen"}, read_logs=["a1_open"])
    d.echoes.append(EchoData(3, 2, 64.0, pack_samples([(0, 0.0, 1, 2, True)]), []))
    assert write_save(d, tmp_path)
    back = load_save(tmp_path)
    assert back.loop == 4 and back.flags == {"warden_seen"} and back.echoes[0].loop == 3


def test_fresh_when_missing(tmp_path):
    assert load_save(tmp_path).loop == 1


def test_migrates_high_scores(tmp_path):
    (tmp_path / "high_scores.json").write_text(
        '[{"name":"ZED","score":900,"wave":3,"difficulty":"hard","timestamp":0}]'
    )
    d = load_save(tmp_path)
    assert d.records == [Record(loop=0, reached=0, salvage=900, time=0.0, difficulty="hard")]


def test_corrupt_is_backed_up(tmp_path):
    (tmp_path / "save.json").write_text("{nope")
    d = load_save(tmp_path)
    assert d.loop == 1 and d.notice and (tmp_path / "save.json.bak").exists()


def test_newer_version_is_backed_up(tmp_path):
    (tmp_path / "save.json").write_text('{"version": 99}')
    assert load_save(tmp_path).notice and (tmp_path / "save.json.bak").exists()


def test_unwritable_directory_returns_false(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")  # a file, not a directory
    assert write_save(SaveData(), target) is False


def test_records_order_and_limit():
    d = SaveData()
    for i in range(12):
        add_record(d, Record(loop=i, reached=i % 6, salvage=i * 10, time=1.0))
    assert len(d.records) == 10
    assert [(r.reached, r.salvage) for r in d.records] == sorted(
        ((r.reached, r.salvage) for r in d.records), reverse=True
    )
```

Add to `tests/test_settings.py`: `Settings(reduced_flashing=True)` round-trips through save/load.

- [ ] **Step 2: Run `pytest tests/test_save.py -v`.** Expected: FAIL, `ModuleNotFoundError: space_shooter.save`.

- [ ] **Step 3: Implement `palette.py` and `save.py`.** Samples pack with `struct` format `"<Bfff?"` per sample, then `base64.b64encode`. Records sort by `(-reached, -salvage, loop)`. `load_save` order: read `save.json`; on `ValueError`/wrong shape or `version > SAVE_VERSION`, copy the file to `save.json.bak` and return a fresh `SaveData` with `notice = "Save data was unreadable and has been reset. A backup was kept."`; if `save.json` is missing and `high_scores.json` exists, migrate its entries. `write_save` catches `OSError` and returns `False`. Add `reduced_flashing` to `Settings` and its `normalised()`. In `Game.__init__` set `self.save = load_save()`; `persist()` calls `write_save` and on `False` sets `self.save.notice = "Progress could not be saved."`.

- [ ] **Step 4: Run `pytest -q`.** Expected: all pass.

- [ ] **Step 5: Commit** `feat: add palette, versioned save data and reduced flashing setting`.

---

### Task 2: Salvage parts, drops, and the player refactor

**Files:**
- Create: `space_shooter/salvage.py`, `space_shooter/entities/parts.py`, `space_shooter/procgen.py`
- Modify: `space_shooter/entities/player.py`, `space_shooter/entities/bullets.py`, `space_shooter/scenes/gameplay.py`, `space_shooter/hud.py`, `space_shooter/config.py`
- Delete: `space_shooter/entities/powerups.py`
- Test: `tests/test_salvage.py`, `tests/test_entities.py`, `tests/test_gameplay.py`

**Interfaces:**
- Consumes: `palette` (Task 1).
- Produces:
  - `salvage.SLOTS = ("fore_l", "fore_r", "wing_l", "wing_r", "aft_l", "aft_r")`
  - `salvage.SLOT_OFFSETS: dict[str, tuple[int, int]]` pixel offsets from ship centre at draw scale: fore `(∓14, -30)`, wing `(∓30, 2)`, aft `(∓16, 30)` (left negative x).
  - `@dataclass(frozen=True) salvage.PartType(kind: str, slots: tuple[str, ...], label: str)`; `salvage.PART_TYPES` with kinds and slots exactly: `turret` wing+aft, `slug` fore, `tractor` aft, `armour` all six, `thruster` aft, `claw` fore.
  - `salvage.PART_DROP_WEIGHTS = {"turret": 25, "slug": 15, "tractor": 15, "armour": 20, "thruster": 15, "claw": 10}`
  - `@dataclass salvage.Part(kind: str, rare: bool = False, armour_left: int = 2)`; `Part.code -> str` is `kind` or `kind + "*"` when rare; `salvage.part_from_code(code: str) -> Part | None` (unknown kinds return None).
  - `@dataclass salvage.HitOutcome(kind: str, slot: str | None = None, part: Part | None = None)` with `kind` in `"armour" | "knocked" | "hull"`.
  - `class salvage.Loadout`: `slots: dict[str, Part | None]`; `attach(part: Part, contact: tuple[float, float]) -> tuple[str, Part | None]` (slot used, ejected part); `absorb_hit(rng: random.Random) -> HitOutcome`; `count(kind: str) -> int`; `effect(kind: str) -> float` (sum of 1.0 per normal part, 1.5 per rare); `speed_multiplier() -> float`; `drop_chance(base: float) -> float`; `patch_share() -> float`; `to_codes() -> dict[str, str]`; `from_codes(codes: dict[str, str]) -> Loadout`; `parts() -> list[tuple[str, Part]]`.
  - `salvage.roll_drop(rng: random.Random, chance: float, patch_share: float = 0.2) -> str | None` returning `"patch"`, a part kind, or None.
  - `salvage.KNOCK_CHANCE = 0.35`, `salvage.DROP_BASE = 0.18`, `salvage.PATCH_HULL = 25`
  - `bullets.SlugBullet(pos, vel, damage=3, pierce=1)`
  - `parts.Drop(pygame.sprite.Sprite)`: `__init__(code: str, pos, vel=(0, 90), lifetime: float | None = None)`; attribute `code`; blinks during its last 2 s of `lifetime` and dies at 0.
  - `parts.PartRig`: `update(dt, loadout, origin: tuple[float, float], enemies, damage_mult: float) -> list[Bullet]` firing turrets (period 0.5 s, range 260 px, rare 0.33 s).
  - `parts.draw_loadout(surface, loadout: Loadout, center: tuple[int, int], alpha: int = 255) -> None`
  - `procgen.part_sprite(kind: str, rare: bool) -> pygame.Surface` small pixel shapes (about 6x6 source pixels at 4x) in steel and rust; rare adds an ember pixel.
  - `Player` loses `lives`, `bombs`, `weapon_level`, `respawn_timer`, shield; keeps `health` as hull 0..100. Adds `loadout: Loadout`, `dead: bool`. `try_fire() -> list[Bullet]` returns one main round plus one `SlugBullet` per slug cannon. `take_damage(amount: int, rng) -> str` returns `"ignored" | "armour" | "knocked" | "hit" | "died"` and exposes the last `HitOutcome` as `last_outcome`. Speed is `PLAYER_SPEED * loadout.speed_multiplier()`.

- [ ] **Step 1: Write failing tests in `tests/test_salvage.py`**

```python
def test_slot_validity():
    lo = Loadout()
    slot, ejected = lo.attach(Part("slug"), contact=(-20, -40))
    assert slot == "fore_l" and ejected is None
    with pytest.raises(ValueError):
        Loadout().attach(Part("unknown"), (0, 0))


def test_closest_free_valid_slot():
    lo = Loadout()
    lo.attach(Part("armour"), (30, 30))
    assert lo.slots["aft_r"].kind == "armour"


def test_full_valid_slots_replace_oldest_and_eject():
    lo = Loadout()
    lo.attach(Part("slug"), (-14, -30))
    lo.attach(Part("claw"), (14, -30))
    slot, ejected = lo.attach(Part("slug", rare=True), (14, -30))
    assert ejected.kind == "slug" and slot == "fore_l"


def test_armour_absorbs_before_knock():
    lo = Loadout()
    lo.attach(Part("armour"), (0, 0))
    lo.attach(Part("turret"), (-30, 2))
    rng = random.Random(0)
    assert [lo.absorb_hit(rng).kind for _ in range(2)] == ["armour", "armour"]
    assert lo.count("armour") == 0  # plate destroyed after 2 hits


def test_knock_rate_close_to_35_percent():
    rng = random.Random(1)
    knocked = 0
    for _ in range(2000):
        lo = Loadout()
        lo.attach(Part("turret"), (-30, 2))
        knocked += lo.absorb_hit(rng).kind == "knocked"
    assert 0.31 < knocked / 2000 < 0.39


def test_empty_loadout_always_hull():
    assert Loadout().absorb_hit(random.Random(0)).kind == "hull"


def test_thruster_caps_at_two():
    lo = Loadout()
    lo.attach(Part("thruster"), (-16, 30))
    lo.attach(Part("thruster"), (16, 30))
    assert lo.speed_multiplier() == pytest.approx(1.30)


def test_claw_raises_drop_chance_and_patch_share():
    lo = Loadout()
    lo.attach(Part("claw"), (14, -30))
    assert lo.drop_chance(DROP_BASE) == pytest.approx(0.27)
    assert lo.patch_share() == pytest.approx(0.35)


def test_roll_drop_distribution():
    rng = random.Random(4)
    results = [roll_drop(rng, 1.0) for _ in range(5000)]
    assert 0.17 < results.count("patch") / 5000 < 0.23 and None not in results


def test_codes_round_trip_ignores_unknown():
    lo = Loadout()
    lo.attach(Part("turret", rare=True), (-30, 2))
    assert Loadout.from_codes(lo.to_codes() | {"aft_l": "laser"}).to_codes() == lo.to_codes()
```

Update `tests/test_entities.py`: remove lives, shield and weapon-level tests; add `test_player_fire_adds_slug_rounds` (one slug cannon gives 2 bullets, one of them `SlugBullet`), `test_player_dies_once_at_zero_hull` (`take_damage(999, rng) == "died"`, `dead` is True, `try_fire()` is empty), `test_thruster_moves_player_faster`.

- [ ] **Step 2: Run `pytest tests/test_salvage.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement `salvage.py`.** Closest slot is by squared distance from `contact` to `SLOT_OFFSETS`. Track attach order to find the oldest. Effects: speed `1 + 0.15 * min(2.0, effect("thruster"))`; drop chance `min(0.9, base * (1 + 0.5 * effect("claw")))`; patch share `0.2 + 0.15 * min(1.0, effect("claw"))`. Absorb order: first armour plate with `armour_left > 0` takes the hit (removed at 0); else if any part, with probability `KNOCK_CHANCE` remove a random part and return `"knocked"`; else `"hull"`.

- [ ] **Step 4: Implement `procgen.part_sprite`, `SlugBullet`, `parts.py`, and the player refactor.** In `GameplayScene`: replace `PowerUp` with `Drop`; on kill call `roll_drop(self.rng, loadout.drop_chance(DROP_BASE) * difficulty drop mult, loadout.patch_share())`; collecting a part code attaches it with the contact point relative to the ship centre, ejecting any replaced part as a `Drop` with `lifetime=6.0`; `"patch"` heals `PATCH_HULL`; on `"knocked"` spawn the knocked part as a `Drop` with `lifetime=6.0` and a sideways drift; tractor pulls drops within 180 px at 220 px/s per tractor effect and auto-collects knocked parts. Remove bombs, shields, weapon pickups, combo text and score popups. Player death goes straight to the existing `GameOverScene`. Draw parts with `draw_loadout`. HUD shows hull and the six slot states instead of lives, bombs and weapon pips.

- [ ] **Step 5: Update `tests/test_gameplay.py`.** Replace the bomb test with `test_collecting_drop_attaches_part`; keep the score and game-over tests working against the new player (score still accumulates internally as salvage value).

- [ ] **Step 6: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 7: Commit** `feat: add salvage parts, hardpoints and drops; refactor player`.

---

### Task 3: Authored encounters, drifts and hazards

**Files:**
- Create: `space_shooter/encounters.py`, `space_shooter/entities/hazards.py`
- Modify: `space_shooter/scenes/gameplay.py`, `space_shooter/entities/enemies.py`, `space_shooter/config.py`
- Delete: `space_shooter/waves.py`, `tests/test_waves.py`
- Test: `tests/test_encounters.py`, `tests/test_gameplay.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) encounters.Spawn(at: float, kind: str, x_frac: float)`
  - `@dataclass(frozen=True) encounters.SpawnEntry(at: float, pattern: str, kind: str, count: int, x: float)` with `pattern` in `"line" | "vee" | "column" | "pincer" | "scatter" | "single"`
  - `@dataclass(frozen=True) encounters.Encounter(index: int, name: str, time_cap: float | None, script: tuple[SpawnEntry, ...], hazards: tuple[str, ...] = (), moments: tuple[tuple[float, str], ...] = ())`
  - `encounters.ENCOUNTERS: tuple[Encounter, ...]` of length 6; `encounters.WARDEN_INDEX = 5`; `encounters.DRIFT_TIME = 6.0`
  - `encounters.expand(entry: SpawnEntry, rng: random.Random) -> list[Spawn]`
  - `class encounters.EncounterDirector(rng, encounters=ENCOUNTERS)`: `update(dt: float, enemies_alive: int) -> list[Spawn]`; attributes `index: int` (current or next encounter), `state: str` in `"drift" | "active" | "clearing" | "complete"`, `t_rel: float` (time inside the active encounter); `drain_events() -> list[tuple[str, object]]` yielding `("drift_start", index)`, `("encounter_start", index)`, `("moment", name)`, `("retreat", index)`, `("encounter_end", index)`, `("act_complete", None)`.
  - `Enemy.retreat() -> None` (moves up off-screen at 1.5x speed and is killed above y = -80).
  - `hazards.AshCloud`, `hazards.Hulk(pos, hp=8, rare_drop: bool = False)`, `hazards.Debris(pos, vel)`; all `update(dt, world)`. Hulks block player and enemy bullets.
  - `world.aim_point() -> tuple[float, float]` on `GameplayScene`: the world position of the player's first armour plate if one exists, else the player position. Gunners and the existing boss aim at it.
  - Loop scaling: `config.LOOP_HULL_STEP = 0.03`, `config.LOOP_HULL_CAP = 0.45`; enemy hull multiplier `1 + min(cap, step * (loop - 1))`.

Encounter content (times in seconds; implementer writes the scripts within these totals):

| Index | Name | Time cap | Enemies in script | Kinds | Hazards | Moments |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | COLD WAKE | 60 | 18 | drone | none | `first_drop` at 0 |
| 1 | ASH SHELF | 70 | 24 | drone, zigzag | `ash` | `blackout` at 25 |
| 2 | GRAVEYARD | 75 | 28 | diver, drone | `hulks` | `hulk_breach` at 30 |
| 3 | PICKET LINE | 80 | 32 | gunner, drone | none | none |
| 4 | LAST LIGHT | 90 | 40 | all four | `debris` | `flare` at 45 |
| 5 | THE WARDEN | None | 1 | warden | none | none |

Moments: `first_drop` makes the first kill of encounter 0 always drop a part. `blackout` darkens the playfield to 85 % for 4 s, leaving bullets and ember visible. `hulk_breach` breaks the nearest hulk and drops a rare part. `flare` shows a 1.5 s warning, then for 2 s deals 30 hull damage to the player and 2 hits to enemies and echoes not shadowed by a hulk (a hulk above them whose x-range covers them). Until Task 7, kind `"warden"` spawns the existing `Boss`.

- [ ] **Step 1: Write failing tests in `tests/test_encounters.py`**

```python
def test_six_encounters_warden_last():
    assert len(ENCOUNTERS) == 6 and ENCOUNTERS[WARDEN_INDEX].script[0].kind == "warden"


@pytest.mark.parametrize("idx,total", [(0, 18), (1, 24), (2, 28), (3, 32), (4, 40)])
def test_script_totals(idx, total):
    assert sum(len(expand(e, random.Random(0))) for e in ENCOUNTERS[idx].script) == total


def test_patterns_positions_in_range_and_ordered():
    for p in ("line", "vee", "column", "pincer", "scatter", "single"):
        spawns = expand(SpawnEntry(2.0, p, "drone", 5 if p != "single" else 1, 0.5), random.Random(1))
        assert all(0.0 <= s.x_frac <= 1.0 and s.at >= 2.0 for s in spawns)


def test_pincer_uses_both_edges():
    xs = {s.x_frac < 0.5 for s in expand(SpawnEntry(0, "pincer", "drone", 4, 0.5), random.Random(0))}
    assert xs == {True, False}


def test_director_flow_drift_active_clear():
    d = EncounterDirector(random.Random(0))
    assert d.state == "drift"
    d.update(DRIFT_TIME + 0.01, 0)
    assert d.state == "active" and ("encounter_start", 0) in d.drain_events()


def test_time_cap_emits_retreat():
    d = EncounterDirector(random.Random(0))
    d.update(DRIFT_TIME + 0.01, 0)
    for _ in range(61 * 10):
        d.update(0.1, 5)
    assert ("retreat", 0) in d.drain_events()


def test_completing_warden_emits_act_complete():
    d = EncounterDirector(random.Random(0))
    d.index = WARDEN_INDEX
    d.update(DRIFT_TIME + 0.01, 0)
    d.update(0.1, 1)
    d.update(0.1, 0)
    assert ("act_complete", None) in d.drain_events() and d.state == "complete"


def test_moment_fires_once():
    d = EncounterDirector(random.Random(0))
    d.index = 1
    d.update(DRIFT_TIME + 0.01, 0)
    events = []
    for _ in range(300):
        d.update(0.1, 3)
        events += d.drain_events()
    assert events.count(("moment", "blackout")) == 1
```

Add to `tests/test_gameplay.py`: `test_encounter_spawns_after_drift`, `test_hulk_blocks_bullets`, `test_aim_point_prefers_armour`, `test_loop_scaling_caps` (loop 30 multiplier is 1.45).

- [ ] **Step 2: Run `pytest tests/test_encounters.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement `encounters.py`.** Pattern expansion rules: `line` spreads `count` across `x ± 0.08 * (count - 1) / 2` at the same time; `vee` is a line where member `i` spawns at `at + 0.15 * abs(i - centre)`; `column` same x, `at + 0.35 * i`; `pincer` alternates x = 0.06 and 0.94, `at + 0.25 * (i // 2)`; `scatter` uses `rng.uniform(0.08, 0.92)` with `at + 0.2 * i`; `single` one spawn at x. Clamp x to `[0.0, 1.0]`. The director sorts the expanded plan per encounter; `active` becomes `clearing` when the plan is exhausted; `clearing` with zero enemies ends the encounter and starts the next drift, or `complete` after the Warden.

- [ ] **Step 4: Implement hazards and wire the director into `GameplayScene`**, replacing `WaveDirector`. Banners show the encounter name on `encounter_start` in bone text. Drifts have no enemies.

- [ ] **Step 5: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 6: Commit** `feat: replace random waves with authored Act 1 encounters and hazards`.

---

### Task 4: Echoes

**Files:**
- Create: `space_shooter/echoes.py`, `space_shooter/entities/echo.py`
- Modify: `space_shooter/scenes/gameplay.py`, `space_shooter/config.py`
- Test: `tests/test_echoes.py`, `tests/test_gameplay.py`

**Interfaces:**
- Consumes: `save.Sample`, `save.EchoData`, `save.pack_samples`, `save.unpack_samples` (Task 1); `Loadout.to_codes`, `Loadout.from_codes`, `PartRig`, `draw_loadout` (Task 2); encounter indices and events (Task 3).
- Produces:
  - `echoes.SAMPLE_RATE = 20`, `echoes.MAX_ACTIVE = 5`, `echoes.MAX_STORED = 12`, `echoes.MIN_SECONDS = 10.0`, `echoes.ECHO_HP = 6`, `echoes.ECHO_DAMAGE = 0.6`
  - `@dataclass echoes.EchoTrace(loop: int, reached: int, duration: float, samples: list[Sample], loadouts: list[tuple[int, float, dict[str, str]]])` with `to_data() -> EchoData` and `from_data(EchoData) -> EchoTrace`.
  - `class echoes.EchoRecorder(loop: int)`: `begin_encounter(index: int)`, `note_fire()`, `note_loadout(codes: dict[str, str])`, `sample(t_rel: float, x: float, y: float)`, `finish(reached: int, duration: float) -> EchoTrace`.
  - `@dataclass echoes.EchoState(x: float, y: float, fired: bool, ended: bool, loadout: dict[str, str])`
  - `class echoes.EchoPlayback(trace: EchoTrace)`: `has_encounter(index: int) -> bool`; `advance(index: int, t_rel: float) -> EchoState | None` (None when the trace has no data for that encounter).
  - `echoes.select_roster(traces: list[EchoTrace], limit: int = MAX_ACTIVE) -> list[EchoTrace]`
  - `echoes.store_trace(traces: list[EchoTrace], new: EchoTrace) -> list[EchoTrace]` (drops traces under `MIN_SECONDS`, keeps `MAX_STORED`, shortest dropped first)
  - `echoes.densest_cluster(points: list[tuple[float, float]], radius: float = 90.0, fallback: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]`
  - `entities.echo.Echo(trace: EchoTrace)` sprite: `hp`, `loop`, `playback`, `rig: PartRig`; `update(dt, encounter: int, t_rel: float, world)`; `hit(damage: int) -> bool`; `draw(surface)` at 35 % opacity with a faint trail.
  - `GameplayScene.radio(text: str) -> None` shows a radio line bottom-left for 3 s; `GameplayScene.echo_positions() -> list[tuple[float, float]]`; `GameplayScene.fire_echo_bullets(bullets) -> None`.

- [ ] **Step 1: Write failing tests in `tests/test_echoes.py`**

```python
def test_recorder_samples_at_20hz_and_marks_fire():
    r = EchoRecorder(loop=3)
    r.begin_encounter(0)
    for i in range(61):
        if i == 10:
            r.note_fire()
        r.sample(i / 60, 100 + i, 200)
    t = r.finish(reached=0, duration=1.0)
    assert len(t.samples) == 21 and sum(s[4] for s in t.samples) == 1


def test_playback_interpolates_and_reports_fire_once():
    t = EchoTrace(1, 0, 1.0, [(0, 0.0, 0, 0, False), (0, 0.05, 10, 0, True), (0, 0.1, 20, 0, False)], [])
    p = EchoPlayback(t)
    s = p.advance(0, 0.025)
    assert s.x == pytest.approx(5) and not s.fired
    assert p.advance(0, 0.06).fired and not p.advance(0, 0.07).fired


def test_playback_ends_at_last_sample():
    t = EchoTrace(1, 0, 0.1, [(0, 0.0, 0, 0, False), (0, 0.1, 20, 0, False)], [])
    assert EchoPlayback(t).advance(0, 5.0).ended


def test_missing_encounter_returns_none():
    t = EchoTrace(1, 0, 0.1, [(0, 0.0, 0, 0, False)], [])
    assert EchoPlayback(t).advance(3, 1.0) is None


def test_loadout_follows_time():
    t = EchoTrace(1, 0, 2, [(0, 0.0, 0, 0, False), (0, 2.0, 0, 0, False)], [(0, 1.0, {"wing_l": "turret"})])
    p = EchoPlayback(t)
    assert p.advance(0, 0.5).loadout == {} and p.advance(0, 1.5).loadout == {"wing_l": "turret"}


def test_roster_furthest_then_most_recent():
    ts = [EchoTrace(i, reached, 30.0, [], []) for i, reached in enumerate([1, 4, 4, 2, 0, 3, 4])]
    assert [t.loop for t in select_roster(ts)] == [6, 2, 1, 5, 3]


def test_store_drops_short_and_caps():
    traces = []
    for i in range(15):
        traces = store_trace(traces, EchoTrace(i, 0, 10.0 + i, [], []))
    traces = store_trace(traces, EchoTrace(99, 0, 4.0, [], []))
    assert len(traces) == 12 and 99 not in [t.loop for t in traces] and min(t.duration for t in traces) == 13.0


def test_densest_cluster():
    pts = [(0, 0), (10, 0), (0, 10), (500, 500)]
    cx, cy = densest_cluster(pts, 90)
    assert cx < 20 and cy < 20
    assert densest_cluster([], 90, fallback=(7, 8)) == (7, 8)


def test_trace_data_round_trip():
    t = EchoTrace(2, 1, 12.0, [(0, 0.0, 1.5, 2.5, True)], [(0, 0.0, {"fore_l": "slug*"})])
    back = EchoTrace.from_data(t.to_data())
    assert back.loop == 2 and back.loadouts == t.loadouts and back.samples[0][4] is True
```

Add to `tests/test_gameplay.py`: `test_echoes_fly_and_fire` (three seeded traces with fire events in encounter 0, run two seconds into it, assert echo bullets exist), `test_destroyed_echo_is_removed_from_save` (sets flag `first_echo_lost` and a radio line), `test_death_stores_trace_and_advances_loop`, `test_echo_without_encounter_data_is_absent` (Review Focus 5: a trace covering only encounter 0 produces no live echo in encounter 1 and raises nothing).

- [ ] **Step 2: Run `pytest tests/test_echoes.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement `echoes.py`.** The recorder keeps the next due sample time per encounter (`t_rel >= next_t`, step `1 / SAMPLE_RATE`); `note_fire` latches until the next stored sample. Playback keeps a per-encounter cursor; `fired` is true if any sample in `(last_t, t_rel]` fired. The loadout at a time is the last loadout entry for that encounter at or before `t_rel`, else the last entry of any earlier encounter, else `{}`. Roster: sort by `(-reached, -loop)`. `densest_cluster`: for each point count neighbours within `radius`; return the mean of the best point's neighbours.

- [ ] **Step 4: Wire echoes into `GameplayScene`.** At scene start build `Echo` sprites from `select_roster(traces from game.save)`. Record every frame during active encounters. Echo bullets deal `ECHO_DAMAGE` of player damage (round up, minimum 1). Enemy bullets and enemies hit echoes; an echo at 0 hp is killed, removed from `game.save.echoes` by loop, flag `first_echo_lost` set, radio line `"Echo {loop} is gone."`. On player death: `finish`, `store_trace`, `game.save.loop += 1`, `game.persist()`, then the existing game-over scene.

- [ ] **Step 5: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 6: Commit** `feat: add echoes of previous loops that replay and fight beside the player`.

---

### Task 5: Story system and log panel

**Files:**
- Create: `space_shooter/story.py`, `space_shooter/data/__init__.py`, `space_shooter/data/act1_logs.json`, `space_shooter/scenes/log_panel.py`
- Modify: `space_shooter/scenes/gameplay.py`, `pyproject.toml` (package data)
- Test: `tests/test_story.py`

**Interfaces:**
- Consumes: `SaveData.flags`, `SaveData.read_logs`, `SaveData.records` (Task 1); drift events (Task 3).
- Produces:
  - `story.SPEAKERS = ("pilot", "fleet", "warden", "unknown")`
  - `@dataclass(frozen=True) story.LogEntry(id: str, speaker: str, lines: tuple[str, ...], when: str, priority: int = 0)`
  - `@dataclass(frozen=True) story.StoryState(loop: int, reached: int, echoes_lost: int, flags: frozenset[str])`
  - `story.parse_condition(text: str) -> Callable[[StoryState], bool]`; grammar: clauses joined by ` and `; a clause is `always`, `flag:NAME`, `not flag:NAME`, or `FIELD OP INT` with FIELD in `loop | reached | echoes_lost` and OP in `>= <= == > <`. Raises `ValueError` on anything else.
  - `story.load_logs(path: Path | None = None) -> list[LogEntry]` (raises `ValueError` on invalid data: duplicate id, 0 or more than 3 lines, unknown speaker, bad condition)
  - `story.load_logs_safe(path: Path | None = None) -> tuple[list[LogEntry], str | None]` (returns `([], notice)` on any error)
  - `class story.LogDirector(logs: list[LogEntry], read: list[str])`: `next_log(state: StoryState) -> LogEntry | None`, `mark_read(log_id: str) -> None`, `unlocked() -> list[LogEntry]`, `get(log_id: str) -> LogEntry | None`
  - `story.state_from_save(save: SaveData, reached: int | None = None) -> StoryState`
  - `scenes.log_panel.LogPanel(game, entry: LogEntry, on_close: Callable[[], None] | None = None)` transparent scene; typewriter at 40 characters per second; the first `confirm`/`fire`/`back` completes the text, the next closes and calls `on_close`; plays `"static"` on enter.
  - `Game.logs: LogDirector` built in `Game.__init__`; a non-None notice from `load_logs_safe` is copied to `save.notice`.

Act 1 logs (ids, speakers and triggers fixed here; copy follows the tone rules and story beats in the spec, at most 3 lines each):

| id | speaker | when | priority |
| --- | --- | --- | --- |
| a1_open | pilot | always | 100 |
| a1_empty_channel | pilot | reached >= 1 | 10 |
| a1_ash | fleet | reached >= 2 | 10 |
| a1_loop2 | pilot | loop >= 2 | 50 |
| a1_loop3 | pilot | loop >= 3 | 40 |
| a1_echo_seen | pilot | loop >= 2 and reached >= 1 | 45 |
| a1_echo_distrust | pilot | loop >= 4 | 30 |
| a1_first_echo_lost | pilot | flag:first_echo_lost | 60 |
| a1_graveyard | fleet | reached >= 3 | 20 |
| a1_picket | fleet | reached >= 4 | 20 |
| a1_last_light | pilot | reached >= 5 | 25 |
| a1_warden_seen | unknown | flag:warden_seen | 70 |
| a1_warden_speaks | warden | flag:warden_seen and loop >= 3 | 65 |
| a1_loop6 | pilot | loop >= 6 | 15 |
| a1_loop10 | pilot | loop >= 10 | 15 |
| a1_echoes_lost3 | pilot | echoes_lost >= 3 | 35 |
| a1_fleet_static | fleet | loop >= 8 | 5 |
| a1_end_1 | warden | flag:act1_complete | 90 |
| a1_end_2 | pilot | flag:act1_complete | 89 |
| a1_end_3 | unknown | flag:act1_complete | 88 |

`echoes_lost` is the number of distinct echoes destroyed, stored as flag count `echo_lost:<loop>`; `state_from_save` counts flags with that prefix. `reached` is the best `reached` across records, or the given value when passed.

- [ ] **Step 1: Write failing tests in `tests/test_story.py`**

```python
@pytest.mark.parametrize(
    "text,state,expected",
    [
        ("always", S(), True),
        ("loop >= 3", S(loop=3), True),
        ("loop >= 3", S(loop=2), False),
        ("flag:warden_seen", S(flags={"warden_seen"}), True),
        ("not flag:warden_seen", S(flags={"warden_seen"}), False),
        ("flag:a and reached > 1", S(flags={"a"}, reached=2), True),
    ],
)
def test_conditions(text, state, expected):
    assert parse_condition(text)(state) is expected


@pytest.mark.parametrize("bad", ["loop >> 3", "flag:", "health >= 2", "loop >= x", ""])
def test_bad_conditions_raise(bad):
    with pytest.raises(ValueError):
        parse_condition(bad)


def test_priority_and_unread():
    logs = [LogEntry("a", "pilot", ("x",), "always", 1), LogEntry("b", "pilot", ("y",), "always", 5)]
    d = LogDirector(logs, read=[])
    assert d.next_log(S()).id == "b"
    d.mark_read("b")
    assert d.next_log(S()).id == "a"
    d.mark_read("a")
    assert d.next_log(S()) is None and [e.id for e in d.unlocked()] == ["a", "b"]


def test_bundled_logs_valid():
    logs = load_logs()
    assert len(logs) == 20 and len({l.id for l in logs}) == 20
    assert all(1 <= len(l.lines) <= 3 for l in logs)


def test_invalid_file_is_safe(tmp_path):
    p = tmp_path / "logs.json"
    p.write_text('[{"id":"a","speaker":"pilot","lines":["x"],"when":"loop >> 1"}]')
    logs, notice = load_logs_safe(p)
    assert logs == [] and notice


def test_echoes_lost_counted_from_flags():
    save = SaveData(flags={"echo_lost:3", "echo_lost:5", "warden_seen"})
    assert state_from_save(save).echoes_lost == 2
```

(`S(**kw)` is a small test helper building `StoryState` with defaults `loop=1, reached=0, echoes_lost=0, flags=frozenset()`.)

Add to `tests/test_gameplay.py`: `test_drift_pushes_log_panel_once` and `test_log_panel_completes_then_closes`.

- [ ] **Step 2: Run `pytest tests/test_story.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement `story.py`, write `act1_logs.json`, implement `LogPanel`.** Package data: add `[tool.setuptools.package-data] space_shooter = ["data/*.json"]`. During a drift, gameplay asks `game.logs.next_log(state_from_save(game.save, reached=current index))` once at `drift_start`; if one is returned, mark it read, persist, and push a `LogPanel`. Destroyed echoes also add flag `echo_lost:<loop>`.

- [ ] **Step 4: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 5: Commit** `feat: add radio-log story system with Act 1 logs`.

---

### Task 6: Hangar, loop-end card, archive and records

**Files:**
- Create: `space_shooter/scenes/hangar.py`, `space_shooter/scenes/loop_end.py`, `space_shooter/scenes/archive.py`, `space_shooter/scenes/records.py`
- Modify: `space_shooter/game.py`, `space_shooter/scenes/gameplay.py`, `space_shooter/scenes/pause.py`, `space_shooter/scenes/settings.py`
- Delete: `space_shooter/scenes/menu.py`, `space_shooter/scenes/gameover.py`, `space_shooter/scenes/highscores.py`, `space_shooter/highscores.py`, `space_shooter/combo.py`, `tests/test_highscores.py`, `tests/test_combo.py`
- Test: `tests/test_gameplay.py` (rename to cover scenes), `tests/test_scenes.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass scenes.loop_end.RunResult(loop: int, reached: int, salvage: int, time: float, echoes_lost: list[int], victory: bool)`
  - `scenes.loop_end.LoopEndScene(game, result: RunResult)`: shows "LOOP n" (or "THE WARDEN IS SILENT" on victory), encounter name reached, salvage value, echoes lost, one closing line; `confirm`/`fire`/`back` after 0.8 s returns to the hangar via `game.scenes.clear_to(HangarScene(game))`.
  - `scenes.hangar.HangarScene(game)`: menu `LAUNCH`, `LOG ARCHIVE`, `RECORDS`, `SETTINGS`, `QUIT`; shows loop counter, up to five echo names from `select_roster`, the most recent read log's first line, and `save.notice` (cleared after display). On first enter with `read_logs` empty, pushes `LogPanel(a1_open, on_close=self.launch)`.
  - `scenes.archive.ArchiveScene(game)` lists `game.logs.unlocked()`; confirm opens the selected log in a `LogPanel`.
  - `scenes.records.RecordsScene(game)` table of `save.records`: loop, reached encounter name, salvage, time `m:ss`, difficulty initial.
  - `GameplayScene.end_loop(victory: bool) -> RunResult`: single place that finishes the trace, stores it, adds the record, advances `loop` (also on victory), persists, and returns the result. Death calls it after 1.2 s of slow motion (time scale 0.3) and pushes `LoopEndScene`.
  - Pause menu: `RESUME`, `SETTINGS`, `ABANDON LOOP` (calls `end_loop(False)` then shows the card).
  - `Game.step` on `pygame.QUIT` while a `GameplayScene` is in the stack calls its `end_loop(False)` before stopping.
  - Settings gains `REDUCED FLASHING` toggle.

- [ ] **Step 1: Write failing tests in `tests/test_scenes.py`**

```python
def test_first_launch_shows_opening_log_then_launches(game):
    game.scenes.push(HangarScene(game))
    assert isinstance(game.scenes.top, LogPanel)
    press(game, "confirm")
    press(game, "confirm")
    assert isinstance(game.scenes.top, GameplayScene)


def test_death_shows_card_then_hangar_with_next_loop(game):
    scene = start_run(game)
    scene.player.take_damage(999, random.Random(0))
    run_frames(game, 120)
    assert isinstance(game.scenes.top, LoopEndScene)
    run_frames(game, 60)
    press(game, "confirm")
    assert isinstance(game.scenes.top, HangarScene) and game.save.loop == 2


def test_abandon_counts_as_loop_end(game):
    scene = start_run(game)
    run_frames(game, 60 * 12)
    scene.handle_action("pause")
    select(game, "ABANDON LOOP")
    assert game.save.loop == 2 and len(game.save.records) == 1


def test_quit_mid_run_saves_loop(game, tmp_path):  # Review Focus 1
    start_run(game)
    run_frames(game, 60 * 12)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game.step(1 / 60)
    assert load_save().loop == 2 and load_save().echoes


def test_hangar_shows_notice_once(game):
    game.save.notice = "Progress could not be saved."
    h = HangarScene(game)
    game.scenes.push(h)
    h.draw(game.screen)
    assert game.save.notice is None


def test_archive_lists_read_logs(game):
    game.logs.mark_read("a1_open")
    game.scenes.push(ArchiveScene(game))
    assert [e.id for e in game.scenes.top.entries] == ["a1_open"]
```

`press`, `select`, `start_run` and `run_frames` live in `tests/helpers.py`.

- [ ] **Step 2: Run `pytest tests/test_scenes.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement the scenes and `end_loop`; switch `Game.run` to push `HangarScene`; delete the replaced modules and tests.**

- [ ] **Step 4: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 5: Commit** `feat: add hangar, loop-end card, log archive and loop records`.

---

### Task 7: The Warden

**Files:**
- Create: `space_shooter/entities/warden.py`
- Modify: `space_shooter/procgen.py`, `space_shooter/entities/enemies.py`, `space_shooter/scenes/gameplay.py`, `space_shooter/hud.py`, `space_shooter/config.py`
- Test: `tests/test_warden.py`, `tests/test_scenes.py`

**Interfaces:**
- Consumes: `densest_cluster`, `GameplayScene.echo_positions()`, `aim_point()`, `fire_enemy_bullet`, `end_loop(True)`.
- Produces:
  - `config.WARDEN_BASE_HP = 160`, `config.WARDEN_SALVAGE = 5000`
  - `procgen.warden_sprites(scale: int = 4) -> tuple[pygame.Surface, pygame.Surface]` (body about 48x32 source pixels, mirrored symmetric; separate ember eye layer)
  - `entities.warden.Warden(Enemy)`: `kind = "warden"`; `__init__(x: float, hp_mult: float = 1.0, speed_mult: float = 1.0, fire_mult: float = 1.0)`; `phase -> int` (1 above 66 %, 2 above 33 %, else 3); `eye_exposed -> bool` (phase 3, between debris rings, 1.5 s windows); `hit(damage)` doubles damage while the eye is exposed.
  - World additions used by the Warden: `GameplayScene.spawn_debris_ring(center: tuple[float, float], count: int) -> None`.
  - Phase behaviour: 1 Sweep, a rotating fan of 7 shots every 0.9 s rotating 0.35 rad per volley; 2 Hunt, alternating aimed 5-shot volleys at `densest_cluster(echo_positions(), 90, fallback=aim_point())` then at `aim_point()`, every 1.1 s; 3 Collapse, a debris ring of 12 every 3 s, each followed by a 1.5 s eye exposure, plus slow aimed single shots every 1.4 s.
  - Kind `"warden"` spawns `Warden`; the old `Boss` class is deleted. First sight sets flag `warden_seen`. Death: heavy explosion, a single low `procgen.tone(55, 2.5)` (silent until Task 8 adds `tone`; guard with `getattr`), flags `act1_complete`, `end_loop(True)`, then push `a1_end_1`, `a1_end_2`, `a1_end_3` as chained `LogPanel`s before the `LoopEndScene`.
  - HUD shows the Warden's hull as a thin rust bar labelled `THE WARDEN`.

- [ ] **Step 1: Write failing tests in `tests/test_warden.py`**

```python
def test_hp_scales_with_difficulty(display):
    assert Warden(400.0).max_hp == 160 and Warden(400.0, hp_mult=1.4).max_hp == 224


def test_phases(display):
    w = Warden(400.0)
    w.hit(55)
    assert w.phase == 2
    w.hit(53)
    assert w.phase == 3


def test_hunt_targets_densest_echo_cluster(display):
    world = FakeWorld(echoes=[(100, 400), (110, 410), (700, 400)])
    w = Warden(400.0)
    w.hp = int(w.max_hp * 0.5)
    w.y = w.target_y
    run(w, world, seconds=1.2)
    assert any(vx < 0 for _, (vx, vy), _ in world.shots)  # first volley leans toward x≈105


def test_eye_exposed_doubles_damage(display):
    w = Warden(400.0)
    w.hp = 40
    w.force_exposed(True)
    w.hit(5)
    assert w.hp == 30


def test_stays_on_screen(display):
    w = Warden(400.0)
    pygame.sprite.Group(w)
    run(w, FakeWorld(), seconds=20)
    assert w.alive() and 0 < w.rect.centery < 320
```

Add to `tests/test_scenes.py`: `test_warden_victory_completes_act` (start at `WARDEN_INDEX`, kill the Warden, step through three log panels, assert the loop-end card shows victory and `save.act1_complete` and `"act1_complete" in save.flags`).

- [ ] **Step 2: Run `pytest tests/test_warden.py -v`.** Expected: FAIL on import.

- [ ] **Step 3: Implement `warden_sprites`, `Warden` and the gameplay hooks.** `force_exposed(value: bool)` is a test seam that sets the exposure window.

- [ ] **Step 4: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 5: Commit** `feat: add the Warden, Act 1's adaptive three-phase boss`.

---

### Task 8: Look and sound pass

**Files:**
- Modify: `space_shooter/procgen.py`, `space_shooter/starfield.py`, `space_shooter/effects.py`, `space_shooter/hud.py`, `space_shooter/audio.py`, `space_shooter/config.py`, `space_shooter/entities/enemies.py`, `space_shooter/entities/bullets.py`, all scenes (palette)
- Test: `tests/test_procgen.py`, `tests/test_effects.py`

**Interfaces:**
- Produces:
  - `procgen.scarred_variant(name: str, kind: str, scale: int = 4) -> pygame.Surface` desaturates toward rust and adds 2 to 4 deterministic scorch pixels seeded by `(name, kind)`; each kind keeps one accent: zigzag steel, diver ash, gunner ember.
  - `procgen.cockpit_overlay(size: tuple[int, int]) -> pygame.Surface` (cracked frame lines, scanlines every 3 px at alpha 18).
  - `procgen.drone_sound(seconds: float = 8.0, rate: int = 22050) -> pygame.mixer.Sound | None`: two sines at 55 Hz and 55.7 Hz plus low-passed noise, 16-bit, seamless by choosing a length that is a whole number of cycles of both sines' beat; None when the mixer is not initialised.
  - `procgen.static_sound(seconds: float = 0.6) -> Sound | None`, `procgen.tone(freq: float, seconds: float) -> Sound | None`.
  - `AudioManager.register(key: str, sound: Sound | None) -> None`, `AudioManager.set_bed_level(level: float) -> None` (bed loops on its own channel; 0.25 in encounters, 0.12 in drifts and the hangar).
  - `starfield.Starfield` becomes two dim layers plus `DyingStar` (ember disc partly above the top edge, radius pulsing ±4 px over 6 s) and `AshField` (60 slow ash flecks drawn behind gameplay).
  - `effects.Flash.enabled: bool` and `effects.ScreenShake.cap: float`; reduced flashing sets `Flash.enabled = False` and `ScreenShake.cap = 4.0`. The `blackout` and `flare` moments show warning text only when reduced flashing is on.
  - Explosions: fewer particles (8 per enemy), smoke particles in ash that live 1.2 s, ember core.
  - Cockpit HUD: tug schematic at bottom-left with six slot markers (steel when filled, steel_dim empty, ember on rare), hull as a segmented bar of 10 cells, `LOOP n` top-left, echo roster icons top-right greying out when lost, encounter name fading in at encounter start, `cockpit_overlay` drawn last.
  - Sound retune in `config.SOUND_FILES`: explosion `Explosions/Medium Length/sfx_exp_medium1.wav`, shoot `Weapons/Single Shot Sounds/` lowest file at volume 0.2, part knock-off `General Sounds/Impacts/sfx_sounds_impact3.wav`, low-hull alarm only below 25 hull; remove `wave` and `high_score` fanfares.
  - All play colours come from `palette`; the old bright colour constants are deleted from `config.py`.

- [ ] **Step 1: Write failing tests**

```python
def test_scarred_variant_size_and_determinism(display):
    a, b = scarred_variant("enemy0", "drone"), scarred_variant("enemy0", "drone")
    assert a.get_size() == (48, 64) and pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def test_warden_sprite_symmetric(display):
    body, eye = warden_sprites(1)
    assert pygame.transform.flip(body, True, False).get_at((5, 5)) == body.get_at((body.get_width() - 6, 5))


def test_drone_sound_when_mixer_available():
    if not audio.init_mixer():
        pytest.skip("no mixer")
    snd = drone_sound(2.0)
    assert snd is not None and snd.get_length() == pytest.approx(2.0, abs=0.2)


def test_reduced_flashing_disables_flash_and_caps_shake(game):  # Review Focus 4
    game.settings.reduced_flashing = True
    scene = start_run(game)
    scene.flash.trigger((255, 255, 255), 200)
    assert scene.flash.alpha == 0
    scene.shake.add(50)
    assert scene.shake.strength <= 4.0


def test_flare_with_reduced_flashing_is_warning_only(game):  # Review Focus 4
    game.settings.reduced_flashing = True
    scene = start_run(game, encounter=4)
    scene.trigger_moment("flare")
    run_frames(game, 60 * 4)
    assert scene.flash.alpha == 0 and scene.player.health == 100


def test_hud_draws_with_full_loadout(game): ...  # draw HUD with six parts and five echoes; no exception
```

- [ ] **Step 2: Run the new tests.** Expected: FAIL on missing functions.

- [ ] **Step 3: Implement the procgen functions, starfield, effects, HUD and audio changes; apply the palette to every scene.** `GameplayScene.trigger_moment(name: str)` is the public entry used by the director events and the tests.

- [ ] **Step 4: Render headless screenshots of hangar, an encounter with echoes and parts, the Warden, a log panel and the loop-end card, and check each against the tone rules.**

- [ ] **Step 5: Run `ruff check . && ruff format --check . && pytest -q`.** Expected: all pass.

- [ ] **Step 6: Commit** `feat: grim visual and audio pass with cockpit HUD and generated drone`.

---

### Task 9: Cleanup, docs and release notes

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`, `pyproject.toml` (version `2.0.0`, description), `space_shooter/__init__.py`, `space_shooter/config.py`
- Delete: any constant, sound key or helper no longer referenced

- [ ] **Step 1: Find dead code.** Run `ruff check --select F401,F841 .` and `grep -rn` for each `config` constant; remove unused ones.

- [ ] **Step 2: Rewrite the README** around *Loop of Ash*: premise in three sentences, how echoes and salvage work, the part table, controls without bombs, Act 1 structure, settings including reduced flashing, project layout with the new modules, and a "Roadmap" listing the strategy map, ground combat, the Hive and the Factions as upcoming milestones.

- [ ] **Step 3: Run `ruff check . && ruff format --check . && pytest -q` and a 3-minute headless soak run through two loops.** Expected: all pass, no exceptions.

- [ ] **Step 4: Commit** `docs: rewrite README for Loop of Ash Act 1 and remove dead code`, push, and update the pull request title and body for Act 1.
