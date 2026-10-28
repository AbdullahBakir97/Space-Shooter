"""Window, clock, input mapping and the main loop."""

from __future__ import annotations

import pygame

from space_shooter import assets
from space_shooter.audio import AudioManager
from space_shooter.config import FPS, HEIGHT, MAX_DT, TITLE, WIDTH
from space_shooter.highscores import HighScoreTable
from space_shooter.save import load_save, write_save
from space_shooter.scenes.base import SceneManager
from space_shooter.settings_store import Settings, load_settings, save_settings
from space_shooter.starfield import Starfield
from space_shooter.story import LogDirector, load_logs_safe

KEY_ACTIONS = {
    pygame.K_UP: "up",
    pygame.K_w: "up",
    pygame.K_DOWN: "down",
    pygame.K_s: "down",
    pygame.K_LEFT: "left",
    pygame.K_a: "left",
    pygame.K_RIGHT: "right",
    pygame.K_d: "right",
    pygame.K_RETURN: "confirm",
    pygame.K_KP_ENTER: "confirm",
    pygame.K_ESCAPE: "back",
    pygame.K_p: "pause",
    pygame.K_SPACE: "fire",
    pygame.K_z: "fire",
    pygame.K_x: "bomb",
    pygame.K_LSHIFT: "bomb",
    pygame.K_RSHIFT: "bomb",
    pygame.K_F11: "fullscreen",
}
# Xbox-style layout, which SDL maps most pads to.
JOY_BUTTON_ACTIONS = {0: "fire", 1: "bomb", 2: "bomb", 3: "fire", 6: "back", 7: "pause"}
JOY_HAT_ACTIONS = {(0, 1): "up", (0, -1): "down", (-1, 0): "left", (1, 0): "right"}
AXIS_DEADZONE = 0.3


class Game:
    def __init__(self, settings: Settings | None = None, headless: bool = False) -> None:
        pygame.init()
        assets.clear_caches()
        self.settings = settings or load_settings()
        self.headless = headless
        self.screen = self._create_screen()
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.audio = AudioManager(self.settings.sfx_volume)
        self.highscores = HighScoreTable.load()
        self.save = load_save()
        logs, notice = load_logs_safe()
        if notice:
            self.save.notice = notice
        self.logs = LogDirector(logs, self.save.read_logs)
        self.starfield = Starfield()
        self.scenes = SceneManager()
        self.joystick: pygame.joystick.Joystick | None = None
        self._init_joystick()
        self.running = True
        self.fps = 0.0
        self._fire_latched = False

    # -- display -------------------------------------------------------------
    def _create_screen(self) -> pygame.Surface:
        flags = 0 if self.headless else pygame.SCALED
        if self.settings.fullscreen and not self.headless:
            flags |= pygame.FULLSCREEN
        return pygame.display.set_mode((WIDTH, HEIGHT), flags)

    def apply_display_mode(self) -> None:
        self.screen = self._create_screen()

    def toggle_fullscreen(self) -> None:
        self.settings.fullscreen = not self.settings.fullscreen
        save_settings(self.settings)
        self.apply_display_mode()

    # -- input ---------------------------------------------------------------
    def _init_joystick(self) -> None:
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count():
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
        except pygame.error:
            self.joystick = None

    def actions_from_event(self, event: pygame.event.Event) -> list[str]:
        if event.type == pygame.KEYDOWN:
            action = KEY_ACTIONS.get(event.key)
            return [action] if action else []
        if event.type == pygame.JOYBUTTONDOWN:
            action = JOY_BUTTON_ACTIONS.get(event.button)
            return [action] if action else []
        if event.type == pygame.JOYHATMOTION:
            action = JOY_HAT_ACTIONS.get(event.value)
            return [action] if action else []
        if event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
            # Treat a decisive stick flick as a menu nudge (edge-triggered).
            if abs(event.value) > 0.8 and not self._fire_latched:
                self._fire_latched = True
                if event.axis == 0:
                    return ["right" if event.value > 0 else "left"]
                return ["down" if event.value > 0 else "up"]
            if abs(event.value) < AXIS_DEADZONE:
                self._fire_latched = False
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self._init_joystick()
        return []

    def move_vector(self) -> tuple[float, float]:
        keys = pygame.key.get_pressed()
        x = float(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - float(keys[pygame.K_LEFT] or keys[pygame.K_a])
        y = float(keys[pygame.K_DOWN] or keys[pygame.K_s]) - float(keys[pygame.K_UP] or keys[pygame.K_w])
        if self.joystick is not None and x == 0 and y == 0:
            try:
                jx, jy = self.joystick.get_axis(0), self.joystick.get_axis(1)
                if abs(jx) > AXIS_DEADZONE:
                    x = jx
                if abs(jy) > AXIS_DEADZONE:
                    y = jy
                hx, hy = self.joystick.get_hat(0) if self.joystick.get_numhats() else (0, 0)
                x, y = x or hx, y or -hy
            except pygame.error:
                pass
        return x, y

    def fire_held(self) -> bool:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_z]:
            return True
        if self.joystick is not None:
            try:
                return any(self.joystick.get_button(b) for b in (0, 3, 5))
            except pygame.error:
                return False
        return False

    # -- loop ----------------------------------------------------------------
    def persist(self) -> None:
        """Write campaign progress; surface a notice instead of crashing."""
        if not write_save(self.save):
            self.save.notice = "Progress could not be saved."

    def quit(self) -> None:
        self.running = False

    def step(self, dt: float) -> None:
        """One frame: events, update, draw. Separated out so tests can drive it."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            scene = self.scenes.top
            if scene is None:
                continue
            for action in self.actions_from_event(event):
                if action == "fullscreen":
                    self.toggle_fullscreen()
                else:
                    scene.handle_action(action)
            scene.handle_event(event)
        scene = self.scenes.top
        if scene is None:
            self.running = False
            return
        scene.update(dt)
        self.scenes.draw(self.screen)
        pygame.display.flip()

    def run(self) -> None:
        from space_shooter.scenes.menu import MenuScene

        self.scenes.push(MenuScene(self))
        while self.running:
            dt = min(MAX_DT, self.clock.tick(FPS) / 1000.0)
            self.fps = self.clock.get_fps()
            self.step(dt)
        save_settings(self.settings)
        self.audio.stop_all_loops()
        pygame.quit()


def main() -> int:
    Game().run()
    return 0
