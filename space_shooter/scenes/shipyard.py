"""Spend campaign salvage on parts fitted at the next launch."""

from __future__ import annotations

import pygame

from space_shooter import campaign
from space_shooter.config import HEIGHT, WIDTH
from space_shooter.palette import ASH, BONE, EMBER, STEEL
from space_shooter.salvage import PART_TYPES
from space_shooter.scenes.base import Scene
from space_shooter.ui import MenuItem, MenuList, dim_overlay, draw_text


class ShipyardScene(Scene):
    transparent = True

    def __init__(self, game) -> None:
        super().__init__(game)
        self.notice = ""
        items = [
            MenuItem(PART_TYPES[kind].label, lambda k=kind: self.buy(k), value=lambda: str(campaign.PART_COST))
            for kind in campaign.PART_KINDS
        ]
        items.append(MenuItem("BACK", self.game.scenes.pop))
        self.menu = MenuList(
            items,
            on_move=lambda: self.game.audio.play("menu_move"),
            on_select=lambda: self.game.audio.play("menu_select"),
        )

    def buy(self, kind: str) -> None:
        state = self.game.campaign()
        if campaign.requisition(state, kind):
            self.game.store_campaign(state)
            self.notice = f"{PART_TYPES[kind].label} will be fitted at launch."
        elif len(state.requisition) >= campaign.MAX_REQUISITION:
            self.notice = f"The yard can fit {campaign.MAX_REQUISITION} parts a loop."
        else:
            self.notice = "Not enough salvage."

    def handle_action(self, action: str) -> None:
        if action == "back":
            self.game.scenes.pop()
        else:
            self.menu.handle_action(action)

    def update(self, dt: float) -> None:
        self.menu.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        dim_overlay(surface, 240)
        state = self.game.campaign()
        cx = WIDTH // 2
        draw_text(surface, "SHIPYARD", 48, (cx, 70), BONE)
        draw_text(surface, f"Campaign salvage {state.salvage}", 22, (cx, 116), STEEL)
        fitted = ", ".join(PART_TYPES[k].label for k in state.requisition) or "nothing"
        draw_text(surface, f"Fitted next launch: {fitted}", 20, (cx, 144), ASH)
        self.menu.draw(surface, 210, spacing=46, size=30)
        if self.notice:
            draw_text(surface, self.notice, 20, (cx, HEIGHT - 70), EMBER)
        draw_text(surface, "Requisitioned parts fly for one loop.", 18, (cx, HEIGHT - 40), ASH)
