"""Flying the star system between fights: lanes, patrols, the radar, docking home."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter import campaign, flight
from space_shooter.config import HEIGHT, PLAYER_MAX_HEALTH, WIDTH
from space_shooter.encounters import AMBUSH
from space_shooter.flight import Lanes, Tug
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM, VOID
from space_shooter.scenes.base import Scene
from space_shooter.scenes.chart import OWNER_NAMES, owner_colour
from space_shooter.scenes.run import CampaignRun
from space_shooter.ui import draw_bar, draw_text

DASH_IMPULSE = 900.0  # px/s the tug is thrown along a dash before its drift settles again
RETURN_GAP = 40.0  # how far outside a marker the tug comes back after a fight
STAR_LAYERS = ((0.25, 140, 1), (0.5, 90, 2))  # parallax factor, count, size
RADAR_SIZE = 64
RADAR_CENTRE = (WIDTH - 80, HEIGHT - 84)


class FlightScene(Scene):
    def __init__(self, game, seed: int | None = None) -> None:
        super().__init__(game)
        self.run = CampaignRun(game, seed=seed)
        self.system = game.system
        self.lanes = Lanes(self.system)
        hx, hy = flight.world_pos(self.system.nodes[campaign.HOME])
        self.tug = Tug(hx, hy - 120)
        self.heading = -math.pi / 2
        self.patrols = flight.spawn_patrols(
            self.system, self.lanes, self.run.state, (self.tug.x, self.tug.y), self.run.rng
        )
        self.fight = None  # the fight scene in progress, pushed over this one
        self.fight_node: str | None = None
        self.pending_patrol: flight.Patrol | None = None
        self.prompt = ""
        self.nearest = campaign.HOME
        self.time = 0.0
        self.camera = (0.0, 0.0)
        star_rng = random.Random(7)
        self.stars = [
            [(star_rng.uniform(0, flight.WORLD[0]), star_rng.uniform(0, flight.WORLD[1])) for _ in range(count)]
            for _, count, _ in STAR_LAYERS
        ]
        self._update_camera()

    # -- the run -------------------------------------------------------------
    @property
    def tug_pos(self) -> tuple[float, float]:
        return (self.tug.x, self.tug.y)

    def _start_fight(self, node_id: str | None) -> None:
        from space_shooter.scenes.gameplay import GameplayScene
        from space_shooter.scenes.ground import GroundScene

        state = self.run.state
        encounter = AMBUSH if node_id is None else campaign.encounter_for(self.system, state, node_id)
        self.fight_node = node_id
        if node_id is not None and self.system.nodes[node_id].ground:  # planets are taken on foot
            self.fight = GroundScene(self.game, self.run, node_id, encounter, seed=self.run.rng.randrange(1 << 30))
            self.game.scenes.push(self.fight)
            return
        self.fight = GameplayScene(
            self.game, seed=self.run.rng.randrange(1 << 30), run=self.run, node_id=node_id, encounter=encounter
        )
        self.game.scenes.push(self.fight)

    def _after_fight(self) -> None:
        """Back in space: fly on from just outside the location, or past the patrol that was beaten."""
        won = self.fight.fight_over
        self.fight = None
        if self.fight_node is not None:
            nx, ny = flight.world_pos(self.system.nodes[self.fight_node])
            dx, dy = self.tug.x - nx, self.tug.y - ny
            dist = math.hypot(dx, dy)
            ux, uy = (dx / dist, dy / dist) if dist > 1 else (0.0, 1.0)
            gap = flight.MARKER_RADIUS + RETURN_GAP
            self.tug.x, self.tug.y = nx + ux * gap, ny + uy * gap
        elif won and self.pending_patrol in self.patrols:
            self.patrols.remove(self.pending_patrol)
        self.tug.vx = self.tug.vy = 0.0
        self.fight_node = None
        self.pending_patrol = None

    def _end(self, died: bool) -> None:
        from space_shooter.scenes.loop_end import LoopEndScene

        self.game.audio.stop_all_loops()
        self.game.scenes.push(LoopEndScene(self.game, self.run.finish(died=died)))

    def dock(self) -> bool:
        hx, hy = flight.world_pos(self.system.nodes[campaign.HOME])
        if math.hypot(self.tug.x - hx, self.tug.y - hy) > flight.DOCK_RADIUS:
            return False
        self.game.audio.play("menu_select")
        self._end(died=False)
        return True

    # -- scene protocol ------------------------------------------------------
    def on_enter(self) -> None:
        self.game.audio.set_bed_level(0.12)
        self.game.starfield.boost = 1.0

    def handle_action(self, action: str) -> None:
        if self.run.result is not None:
            return
        if action in ("pause", "back"):
            from space_shooter.scenes.pause import PauseScene

            self.game.scenes.push(PauseScene(self.game))
        elif action == "confirm":
            self.dock()
        elif action == "dash" and self.run.player.start_dash(self.game.move_vector()):
            dx, dy = self.run.player.dash_dir
            self.tug.vx, self.tug.vy = dx * DASH_IMPULSE, dy * DASH_IMPULSE
            self.game.audio.play("knock")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB and self.run.result is None:
            from space_shooter.scenes.chart import ChartScene

            self.game.scenes.push(ChartScene(self.game, flight=self))

    def update(self, dt: float) -> None:
        if self.run.result is not None:
            return
        if self.fight is not None:
            self._after_fight()
        self.time += dt
        self.run.time += dt
        player = self.run.player
        player.dash.configure(player.loadout.dash_charges(), player.loadout.dash_recharge())
        player.dash.update(dt)
        on_lane = self.lanes.on_lane(self.tug_pos)
        worn = self.tug.step(self.game.move_vector(), dt, on_lane)
        if math.hypot(self.tug.vx, self.tug.vy) > 20:
            self.heading = math.atan2(self.tug.vy, self.tug.vx)
        if worn:
            player.health = max(0, player.health - worn)
            if player.health <= 0:
                player.dead = True
                self._end(died=True)
                return
        self._update_camera()
        if self._check_locations():
            return  # one fight a frame: the patrols wait
        for p in self.patrols:
            if flight.step_patrol(p, self.system, self.lanes, self.run.state, self.tug_pos, on_lane, dt, self.run.rng):
                self.pending_patrol = p
                self._start_fight(None)
                return

    def _check_locations(self) -> bool:
        """Prompts, arrivals and repairs at the location nearest the tug; True when a fight began."""
        state, run = self.run.state, self.run
        best = min(
            self.system.nodes.values(),
            key=lambda n: math.dist(flight.world_pos(n), self.tug_pos),
        )
        self.nearest = best.id
        dist = math.dist(flight.world_pos(best), self.tug_pos)
        self.prompt = ""
        if best.id == campaign.HOME:
            if dist <= flight.DOCK_RADIUS:
                self.prompt = "ENTER  DOCK"
            return False
        if dist > flight.MARKER_RADIUS:
            return False
        if campaign.can_engage(self.system, state, best.id):
            self._start_fight(best.id)
            return True
        if campaign.locked(self.system, state, best.id):
            self.prompt = "SEALED"
        if flight.repairable(self.system, state, best.id, run.repaired):
            run.repaired.add(best.id)
            run.player.health = min(PLAYER_MAX_HEALTH, run.player.health + flight.REPAIR)
            self.prompt = f"HULL PATCHED +{flight.REPAIR}"
            self.game.audio.play("pickup")
        return False

    def _update_camera(self) -> None:
        cx = min(max(0.0, self.tug.x - WIDTH / 2), flight.WORLD[0] - WIDTH)
        cy = min(max(0.0, self.tug.y - HEIGHT / 2), flight.WORLD[1] - HEIGHT)
        self.camera = (cx, cy)

    # -- drawing -------------------------------------------------------------
    def to_screen(self, point: tuple[float, float]) -> tuple[int, int]:
        return (round(point[0] - self.camera[0]), round(point[1] - self.camera[1]))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(VOID)
        cx, cy = self.camera
        for (factor, _, size), layer in zip(STAR_LAYERS, self.stars, strict=True):
            for x, y in layer:
                sx, sy = (x - cx * factor) % WIDTH, (y - cy * factor) % HEIGHT
                surface.fill(STEEL_DIM if size == 1 else ASH, (sx, sy, size, size))
        state = self.run.state
        for _a, _b, pa, pb in self.lanes.segments:
            pygame.draw.line(surface, STEEL_DIM, self.to_screen(pa), self.to_screen(pb), 2)
        for node in self.system.nodes.values():
            self._draw_node(surface, node, state)
        for p in self.patrols:
            self._draw_patrol(surface, p)
        self._draw_tug(surface)
        self._draw_hud(surface)

    def _draw_node(self, surface, node, state) -> None:
        x, y = self.to_screen(flight.world_pos(node))
        if not (-120 < x < WIDTH + 120 and -120 < y < HEIGHT + 120):
            return
        colour = owner_colour(self.system, state, node.id, self.time)
        radius = 26 if node.kind in ("planet", "core") else 18
        if node.kind == "planet":
            pygame.draw.circle(surface, colour, (x, y), radius)
            pygame.draw.circle(surface, VOID, (x - radius // 3, y - radius // 3), radius // 3)
        elif node.kind in ("gate", "core"):
            pygame.draw.polygon(surface, colour, [(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)])
        else:
            pygame.draw.rect(surface, colour, (x - radius, y - radius, radius * 2, radius * 2), 3)
        ring = flight.DOCK_RADIUS if node.id == campaign.HOME else flight.MARKER_RADIUS
        pygame.draw.circle(surface, STEEL_DIM, (x, y), int(ring), 1)
        if node.id in state.fortified:
            pygame.draw.circle(surface, BONE, (x, y), radius + 7, 1)
        draw_text(surface, node.name, 16, (x, y + int(ring) + 12), ASH)

    def _draw_patrol(self, surface, p) -> None:
        x, y = self.to_screen(flight.patrol_pos(self.system, p))
        if not (-30 < x < WIDTH + 30 and -30 < y < HEIGHT + 30):
            return
        colour = EMBER if p.mode == "chase" else RUST
        pygame.draw.polygon(surface, colour, [(x, y - 9), (x + 9, y + 7), (x, y + 2), (x - 9, y + 7)])
        if p.mode == "chase" and int(self.time * 6) % 2:
            pygame.draw.circle(surface, EMBER, (x, y), 16, 1)

    def _draw_tug(self, surface) -> None:
        base = self.run.player.frames[0]
        image = pygame.transform.rotozoom(base, -math.degrees(self.heading) - 90, 0.6)
        surface.blit(image, image.get_rect(center=self.to_screen(self.tug_pos)))

    def _draw_hud(self, surface) -> None:
        player, state = self.run.player, self.run.state
        draw_text(surface, f"LOOP {self.run.loop}", 24, (20, 16), BONE, "topleft")
        draw_bar(surface, pygame.Rect(20, 46, 180, 10), player.health / PLAYER_MAX_HEALTH, STEEL)
        draw_text(surface, f"HULL {player.health}", 16, (206, 51), ASH, "midleft")
        draw_text(surface, f"CARRYING {self.run.carried:,} salvage", 16, (20, 64), ASH, "topleft")
        if player.dash.max_charges:
            pips = "o" * player.dash.charges + "." * (player.dash.max_charges - player.dash.charges)
            draw_text(surface, f"DASH {pips}", 16, (20, 84), STEEL, "topleft")
        node = self.system.nodes[self.nearest]
        owner = (
            "HOME"
            if node.id == campaign.HOME
            else ("HIVE" if state.is_hive(node.id) else OWNER_NAMES[state.owner[node.id]])
        )
        draw_text(surface, node.name, 20, (WIDTH - 20, 16), BONE, "topright")
        draw_text(
            surface, owner, 16, (WIDTH - 20, 40), owner_colour(self.system, state, node.id, self.time), "topright"
        )
        if self.prompt:
            draw_text(surface, self.prompt, 24, (WIDTH // 2, HEIGHT - 120), EMBER)
        if self.lanes.on_lane(self.tug_pos):
            draw_text(surface, "ON LANE", 14, (WIDTH // 2, 18), STEEL)
        else:
            draw_text(surface, "OPEN SPACE - ASH WEARING HULL", 14, (WIDTH // 2, 18), RUST)
        draw_text(surface, "TAB chart   ENTER dock at home   ESC pause", 16, (WIDTH // 2, HEIGHT - 16), STEEL_DIM)
        self._draw_radar(surface)

    def _draw_radar(self, surface) -> None:
        cx, cy = RADAR_CENTRE
        pygame.draw.circle(surface, VOID, (cx, cy), RADAR_SIZE)
        pygame.draw.circle(surface, STEEL_DIM, (cx, cy), RADAR_SIZE, 1)
        scale = RADAR_SIZE / flight.RADAR_RANGE

        def blip(point):
            dx, dy = point[0] - self.tug.x, point[1] - self.tug.y
            if math.hypot(dx, dy) > flight.RADAR_RANGE:
                return None
            return (round(cx + dx * scale), round(cy + dy * scale))

        for node in self.system.nodes.values():
            pos = blip(flight.world_pos(node))
            if pos is not None:
                pygame.draw.circle(surface, owner_colour(self.system, self.run.state, node.id, self.time), pos, 3)
        for p in self.patrols:
            pos = blip(flight.patrol_pos(self.system, p))
            if pos is not None:
                pygame.draw.circle(surface, RUST, pos, 2)
        hx, hy = flight.world_pos(self.system.nodes[campaign.HOME])
        angle = math.atan2(hy - self.tug.y, hx - self.tug.x)
        tip = (cx + math.cos(angle) * (RADAR_SIZE - 4), cy + math.sin(angle) * (RADAR_SIZE - 4))
        pygame.draw.circle(surface, BONE, (round(tip[0]), round(tip[1])), 3)
        pygame.draw.circle(surface, BONE, (cx, cy), 2)
