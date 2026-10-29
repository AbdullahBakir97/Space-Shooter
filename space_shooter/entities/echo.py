"""A ghost of a previous loop, replaying its recorded flight."""

from __future__ import annotations

import pygame

from space_shooter import assets
from space_shooter.echoes import ECHO_DAMAGE, ECHO_HP, EchoPlayback, EchoTrace
from space_shooter.entities.parts import PartRig, draw_loadout, gun_volley
from space_shooter.palette import STEEL
from space_shooter.salvage import Loadout

ECHO_ALPHA = 90  # about 35 % opacity
FADE_TIME = 1.0
TRAIL_LENGTH = 6


class Echo(pygame.sprite.Sprite):
    def __init__(self, trace: EchoTrace) -> None:
        super().__init__()
        self.trace = trace
        self.loop = trace.loop
        self.playback = EchoPlayback(trace)
        self.hp = ECHO_HP
        self.ram_cooldown = 0.0
        self.rig = PartRig()
        self.loadout = Loadout()
        self._codes: dict[str, str] = {}
        self.active = False
        self.fading = 0.0
        self.base_image = assets.silhouette("player0", STEEL).copy()
        self.image = self.base_image
        self.rect = self.image.get_rect()
        self.radius = 16
        self.x = self.y = -100.0
        self.trail: list[tuple[float, float]] = []

    @property
    def name(self) -> str:
        return f"ECHO {self.loop}"

    def hide(self) -> None:
        self.active = False

    def update(self, dt: float, encounter: int, t_rel: float, world) -> None:
        self.ram_cooldown = max(0.0, self.ram_cooldown - dt)
        if self.fading > 0:
            self.fading -= dt
            self.image = self.base_image.copy()
            self.image.set_alpha(int(ECHO_ALPHA * max(0.0, self.fading) / FADE_TIME))
            if self.fading <= 0:
                self.kill()
            return
        state = self.playback.advance(encounter, t_rel)
        if state is None:
            self.active = False
            return
        self.active = True
        self.trail = ([(self.x, self.y)] + self.trail)[:TRAIL_LENGTH]
        self.x, self.y = state.x, state.y
        self.rect.center = (round(self.x), round(self.y))
        if state.loadout != self._codes:
            self._codes = state.loadout
            self.loadout = Loadout.from_codes(state.loadout)
        if state.ended:
            self.active = False
            self.fading = FADE_TIME
            return
        shots = []
        if state.fired:
            shots += gun_volley(self.x, self.rect.top, self.loadout, ECHO_DAMAGE)
        shots += self.rig.update(dt, self.loadout, (self.x, self.y), world.enemies, ECHO_DAMAGE)
        if shots:
            world.fire_echo_bullets(shots)

    def hit(self, damage: int) -> bool:
        self.hp -= damage
        return self.hp <= 0

    def draw(self, surface: pygame.Surface) -> None:
        if not (self.active or self.fading > 0):
            return
        for i, (tx, ty) in enumerate(self.trail[1:], start=1):
            dot = pygame.Surface((4, 4), pygame.SRCALPHA)
            dot.fill((*STEEL, max(0, 60 - i * 10)))
            surface.blit(dot, (tx - 2, ty + 24))
        img = self.image
        if self.active:
            img = self.base_image
            img.set_alpha(ECHO_ALPHA)
        surface.blit(img, self.rect)
        if self.active:
            draw_loadout(surface, self.loadout, self.rect.center, alpha=ECHO_ALPHA, aim=self.rig.aim)
