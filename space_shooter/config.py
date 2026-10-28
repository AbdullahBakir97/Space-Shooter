"""Tunable constants. Nothing here imports pygame."""

from __future__ import annotations

from dataclasses import dataclass

# --- Window -----------------------------------------------------------------
TITLE = "Space Shooter"
WIDTH, HEIGHT = 800, 640
FPS = 60
SPRITE_SCALE = 4  # source art is 12x16 pixels; drawn at 48x64
MAX_DT = 1 / 20  # clamp frame time so a stall never teleports entities

# --- Colours ----------------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SPACE = (6, 8, 20)
GREY = (120, 128, 150)
DIM = (70, 76, 96)
CYAN = (90, 220, 255)
BLUE = (91, 144, 223)
YELLOW = (242, 252, 36)
ORANGE = (254, 167, 17)
RED = (251, 59, 2)
GREEN = (80, 230, 120)
MAGENTA = (230, 90, 220)

# --- Player -----------------------------------------------------------------
PLAYER_SPEED = 380.0  # px/s
PLAYER_MAX_HEALTH = 100
PLAYER_INVULN_TIME = 2.0  # seconds after respawn / hit
PLAYER_HIT_INVULN_TIME = 0.6
PLAYER_COLLISION_DAMAGE = 35
PLAYER_BULLET_DAMAGE = 1  # enemy HP is counted in bullet hits
WEAPON_COOLDOWN = 0.2  # main gun, seconds between shots
BULLET_SPEED = 820.0
ENEMY_BULLET_SPEED = 260.0

# --- Enemies ----------------------------------------------------------------
ENEMY_BASE_SPEED = 120.0
ENEMY_SCORE = {"drone": 100, "zigzag": 150, "diver": 200, "gunner": 300, "warden": 5000}
ENEMY_HP = {"drone": 1, "zigzag": 2, "diver": 1, "gunner": 3}
WARDEN_BASE_HP = 160  # hits, before difficulty
WARDEN_SALVAGE = 5000
LOOP_HULL_STEP = 0.03  # enemy hull grows 3% per loop...
LOOP_HULL_CAP = 0.45  # ...up to +45%

# --- Combo ------------------------------------------------------------------
COMBO_WINDOW = 1.6  # seconds between kills to keep the chain alive
COMBO_MAX = 8


# --- Effects ----------------------------------------------------------------
SHAKE_HIT = 6.0
SHAKE_EXPLOSION = 3.0
SHAKE_BOSS_DEATH = 18.0
LOW_HEALTH_THRESHOLD = 30


@dataclass(frozen=True)
class Difficulty:
    """Multipliers applied to the base tuning."""

    name: str
    enemy_speed: float
    enemy_hp: float
    spawn_rate: float
    enemy_fire_rate: float
    score_mult: float


DIFFICULTIES: dict[str, Difficulty] = {
    "easy": Difficulty("Easy", 0.85, 0.8, 0.8, 0.7, 0.8),
    "normal": Difficulty("Normal", 1.0, 1.0, 1.0, 1.0, 1.0),
    "hard": Difficulty("Hard", 1.25, 1.4, 1.3, 1.5, 1.5),
}
DIFFICULTY_ORDER = ["easy", "normal", "hard"]

# --- Sounds (relative to paths.SOUNDS_DIR) ----------------------------------
SOUND_FILES = {
    "shoot": "Weapons/Lasers/sfx_wpn_laser8.wav",
    "enemy_shoot": "Weapons/Lasers/sfx_wpn_laser2.wav",
    "explosion": "Explosions/Short/sfx_exp_short_hard2.wav",
    "explosion_big": "Explosions/Medium Length/sfx_exp_medium3.wav",
    "boss_death": "Explosions/Long/sfx_exp_long4.wav",
    "player_hit": "General Sounds/Simple Damage Sounds/sfx_damage_hit4.wav",
    "player_death": "Explosions/Clusters/sfx_exp_cluster7.wav",
    "powerup": "General Sounds/Positive Sounds/sfx_sounds_powerup6.wav",
    "bomb": "Explosions/Odd/sfx_exp_odd1.wav",
    "menu_move": "General Sounds/Menu Sounds/sfx_menu_move2.wav",
    "menu_select": "General Sounds/Menu Sounds/sfx_menu_select4.wav",
    "pause_in": "General Sounds/Pause Sounds/sfx_sounds_pause1_in.wav",
    "pause_out": "General Sounds/Pause Sounds/sfx_sounds_pause1_out.wav",
    "wave": "General Sounds/Fanfares/sfx_sounds_fanfare3.wav",
    "low_health": "General Sounds/Alarms/Low health Alarms/sfx_lowhealth_alarmloop1.wav",
    "game_over": "General Sounds/Negative Sounds/sfx_sounds_error10.wav",
    "high_score": "General Sounds/Fanfares/sfx_sounds_fanfare1.wav",
    "boss_warning": "General Sounds/Alarms/Alarms/sfx_alarm_loop2.wav",
}
SOUND_VOLUMES = {
    "shoot": 0.35,
    "enemy_shoot": 0.3,
    "low_health": 0.5,
    "boss_warning": 0.5,
}
