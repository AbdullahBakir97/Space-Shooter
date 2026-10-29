"""The system chart: who holds what, where the swarm is, and where the tug flies."""

from __future__ import annotations

import math

import pygame

from space_shooter import campaign, flight
from space_shooter.config import HEIGHT, WIDTH
from space_shooter.encounters import ENCOUNTERS
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM, VOID
from space_shooter.scenes.base import Scene
from space_shooter.ui import draw_text

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
CONE = 0.34  # cos of the widest angle (about 70 degrees) a move may turn from its direction
CLICK_RADIUS = 30
OWNER_NAMES = {"player": "HELD", "swarm": "SWARM", "neutral": "NEUTRAL"}


def owner_colour(system, state, node_id: str, time: float):
    """Bone for home, steel for yours, rust for the swarm, a pulsing ember for hives, ash for neutral."""
    if node_id == campaign.HOME:
        return BONE
    if state.is_hive(node_id):
        pulse = 0.5 + 0.5 * math.sin(time * 4)
        return tuple(int(r + (e - r) * pulse) for r, e in zip(RUST, EMBER, strict=True))
    owner = state.owner[node_id]
    if owner == "player":
        return STEEL
    if owner == "swarm":
        return RUST
    return STEEL_DIM if campaign.locked(system, state, node_id) else ASH


class ChartScene(Scene):
    def __init__(self, game, flight=None) -> None:
        super().__init__(game)
        self.system = game.system
        self.flight = flight  # the flight scene underneath, when opened in flight
        self.state = flight.run.state if flight is not None else game.campaign()
        self.selected = campaign.HOME
        self.time = 0.0
        self.notice = ""

    # -- planning ------------------------------------------------------------
    def move(self, direction: str) -> None:
        """Follow a lane in that direction if one goes roughly that way, else jump to the nearest location."""
        dx, dy = DIRECTIONS[direction]
        ox, oy = self.system.nodes[self.selected].pos
        scored = []
        for node in self.system.nodes.values():
            vx, vy = node.pos[0] - ox, node.pos[1] - oy
            dist = math.hypot(vx, vy)
            cos = (vx * dx + vy * dy) / dist if dist else 0.0
            if cos >= CONE:
                scored.append((node.id not in self.system.neighbours(self.selected), dist / cos**2, node.id))
        if scored:
            self.selected = min(scored)[2]
            self.game.audio.play("menu_move")

    def fortify_selected(self) -> None:
        if campaign.fortify(self.state, self.selected):
            self.game.store_campaign(self.state)
            self.notice = f"{self.system.nodes[self.selected].name} fortified."
            self.game.audio.play("menu_select")
        else:
            self.notice = f"Fortifying costs {campaign.FORTIFY_COST} salvage and needs held ground."

    # -- scene protocol ------------------------------------------------------
    def handle_action(self, action: str) -> None:
        if action in DIRECTIONS:
            self.move(action)
        elif action in ("back", "confirm"):
            self.game.scenes.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                self.fortify_selected()
            elif event.key == pygame.K_TAB:
                self.game.scenes.pop()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self.node_at(event.pos)
            if hit is not None:
                self.selected = hit

    def node_at(self, pos: tuple[int, int]) -> str | None:
        best: tuple[float, str] | None = None
        for node in self.system.nodes.values():
            dist = math.hypot(node.pos[0] - pos[0], node.pos[1] - pos[1])
            if dist <= CLICK_RADIUS and (best is None or dist < best[0]):
                best = (dist, node.id)
        return best[1] if best else None

    def update(self, dt: float) -> None:
        self.time += dt
        self.game.starfield.update(dt)

    # -- drawing -------------------------------------------------------------
    def _colour(self, node_id: str):
        return owner_colour(self.system, self.state, node_id, self.time)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(VOID)
        self.game.starfield.draw(surface)
        nodes = self.system.nodes
        drawn = set()
        for a, neighbours in self.system.lanes.items():
            for b in neighbours:
                if (b, a) in drawn:
                    continue
                drawn.add((a, b))
                pygame.draw.line(surface, STEEL_DIM, nodes[a].pos, nodes[b].pos, 1)
        for node in nodes.values():
            self._draw_node(surface, node)
        if self.flight is not None:
            for p in self.flight.patrols:
                x, y = flight.patrol_pos(self.system, p)
                pygame.draw.circle(surface, RUST, (round(x / flight.SCALE), round(y / flight.SCALE)), 3)
            tx, ty = self.flight.tug.x / flight.SCALE, self.flight.tug.y / flight.SCALE
            pygame.draw.polygon(surface, BONE, [(tx, ty - 7), (tx + 5, ty + 5), (tx - 5, ty + 5)])
        self._draw_panel(surface)
        hint = "ARROWS select   F fortify   ESC back"
        draw_text(surface, hint, 18, (WIDTH // 2, HEIGHT - 16), ASH)
        if self.notice:
            draw_text(surface, self.notice, 20, (WIDTH // 2, HEIGHT - 40), EMBER)

    def _draw_node(self, surface: pygame.Surface, node) -> None:
        colour = self._colour(node.id)
        x, y = node.pos
        radius = 11 if node.kind in ("planet", "core") else 8
        if node.kind == "planet":
            pygame.draw.circle(surface, colour, (x, y), radius)
        elif node.kind in ("gate", "core"):
            pts = [(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)]
            pygame.draw.polygon(surface, colour, pts)
        else:
            pygame.draw.rect(surface, colour, (x - radius, y - radius, radius * 2, radius * 2))
        if node.id in self.state.fortified:
            pygame.draw.circle(surface, BONE, (x, y), radius + 5, 1)
        if node.id == self.selected:
            pulse = 3 + int(2 * math.sin(self.time * 6))
            pygame.draw.circle(surface, BONE, (x, y), radius + 8 + pulse, 2)
        draw_text(surface, node.name, 14, (x, y + radius + 10), ASH if node.id != self.selected else BONE)

    def _draw_panel(self, surface: pygame.Surface) -> None:
        node = self.system.nodes[self.selected]
        owner = "HOME" if node.id == campaign.HOME else OWNER_NAMES[self.state.owner[node.id]]
        if self.state.is_hive(node.id):
            owner = "HIVE"
        lines = [(node.name, BONE, 24), (owner, self._colour(node.id), 18)]
        if node.id != campaign.HOME:
            lines.append((f"Plays as {ENCOUNTERS[node.template].name}", ASH, 16))
            if node.yield_:
                lines.append((f"Yields {node.yield_} a loop", ASH, 16))
        if node.id in self.state.fortified:
            lines.append(("Fortified", BONE, 16))
        if campaign.locked(self.system, self.state, node.id):
            need = f"hold {campaign.GATE_NEEDS_MIDDLE} middle worlds" if node.id == campaign.GATE else "take the gate"
            lines.append((f"Locked: {need}", EMBER, 16))
        lines.append((f"Salvage {self.state.salvage}   Turn {self.state.turn + 1}", STEEL, 16))
        y = 14
        for text, colour, size in lines:
            draw_text(surface, text, size, (16, y), colour, "topleft")
            y += size + 4
