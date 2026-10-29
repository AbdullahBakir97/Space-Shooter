"""On foot: the pilot lands on a planet and fights for it with hand weapons and a few survivors."""

from __future__ import annotations

import math
import random

import pygame

from space_shooter import campaign, ground, procgen
from space_shooter.config import HEIGHT, WIDTH
from space_shooter.ground import GroundInputs, GroundWorld
from space_shooter.palette import ASH, BONE, EMBER, RUST, STEEL, STEEL_DIM, VOID
from space_shooter.scenes.base import Scene
from space_shooter.ui import draw_bar, draw_text

DEATH_BEAT = 1.2
BANNER_TIME = 2.5
VIGNETTE = 380
EXPLOSION_TIME = 0.4
AIM_STICK = 220.0  # px ahead of the pilot a full right-stick push aims
# floor, rock, wreck colours per planet; other ground falls back to KESS
PALETTES = {
    "m1": ((44, 44, 46), (86, 84, 82), (64, 72, 84)),
    "m3": ((52, 34, 28), (112, 58, 40), (70, 64, 70)),
    "m5": ((70, 66, 58), (150, 144, 132), (88, 92, 100)),
}
SOUNDS = {"shot": "shoot", "kill": "explosion", "explosion": "explosion", "pilot_hit": "player_hit"}
SOUNDS |= {"pickup": "pickup", "joined": "powerup", "survivor_down": "player_death"}


def _map_surface(world: GroundWorld, node_id: str) -> pygame.Surface:
    floor, rock, wreck = PALETTES.get(node_id, PALETTES["m1"])
    w, h = world.map.size
    surface = pygame.Surface((int(w), int(h)))
    surface.fill(floor)
    rng = random.Random(node_id)
    for _ in range(int(w * h / 900)):  # grit
        x, y = rng.randrange(int(w)), rng.randrange(int(h))
        shade = tuple(max(0, c + rng.randint(-14, 14)) for c in floor)
        surface.fill(shade, (x, y, 2, 2))
    t = ground.TILE
    for ty, row in enumerate(world.map.tiles):
        for tx, tile in enumerate(row):
            rect = pygame.Rect(tx * t, ty * t, t, t)
            if tile == ground.ROCK:
                pygame.draw.rect(surface, rock, rect)
                pygame.draw.line(surface, tuple(min(255, c + 24) for c in rock), rect.topleft, rect.topright, 2)
            elif tile == ground.WRECK:
                pygame.draw.rect(surface, wreck, rect)
                pygame.draw.rect(surface, STEEL_DIM, rect, 1)
                surface.fill(ASH, (rect.x + 6, rect.y + 6, 3, 3))
    pad = (round(world.map.pad[0]), round(world.map.pad[1]))
    pygame.draw.circle(surface, STEEL_DIM, pad, int(ground.PAD_RADIUS), 2)
    tug = procgen.tug_frames()[0]
    surface.blit(tug, tug.get_rect(center=(pad[0] - 24, pad[1])))
    return surface


def _vignette() -> pygame.Surface:
    size = (WIDTH * 2, HEIGHT * 2)
    veil = pygame.Surface(size, pygame.SRCALPHA)
    veil.fill((0, 0, 0, 235))
    for r in range(VIGNETTE, 0, -6):
        alpha = int(235 * (r / VIGNETTE) ** 2)
        pygame.draw.circle(veil, (0, 0, 0, alpha), (WIDTH, HEIGHT), r)
    return veil


class GroundScene(Scene):
    def __init__(self, game, run, node_id: str, encounter, seed: int | None = None) -> None:
        super().__init__(game)
        self.run = run
        self.node_id = node_id
        self.encounter = encounter
        pace = campaign.HIVE_PACE if run.state.is_hive(node_id) else 1.0
        self.world = GroundWorld(node_id, hull=encounter.hull, pace=pace, seed=seed or 0)
        self.map_image = _map_surface(self.world, node_id)
        self.veil = _vignette()
        self.camera = (0.0, 0.0)
        self.paid = 0  # salvage already handed to the run
        self.fight_over = False
        self.result = None
        self.death_timer: float | None = None
        self.banner = (self.world.objective_text(), BANNER_TIME)
        self.notice: tuple[str, float] | None = None
        self.explosions: list[tuple[tuple[float, float], float]] = []
        self.pending = GroundInputs()
        self.inputs_override = None  # a callable returning GroundInputs (tests and autopilots)
        self.mouse_aim = False
        self.time = 0.0
        self._update_camera()

    # -- the run -------------------------------------------------------------
    def _pay(self) -> None:
        self.run.carried += self.world.score - self.paid
        self.paid = self.world.score

    def end_loop(self, victory: bool = False):
        """The pilot fell (or the loop was abandoned): bank what was earned and close the loop."""
        if self.run.result is None:
            self._pay()
            self.run.last_fought = self.node_id
        self.result = self.run.finish(died=True)
        return self.result

    def take_off(self) -> bool:
        if not (self.world.complete and self.world.at_pad()) or self.result is not None or self.fight_over:
            return False
        self._pay()
        self.run.carried += self.world.squad_bonus()
        self.run.last_fought = self.node_id
        self.fight_over = True
        self.game.audio.stop_all_loops()
        if self.game.scenes.top is self:
            self.game.scenes.pop()
        return True

    # -- input ---------------------------------------------------------------
    def handle_action(self, action: str) -> None:
        if self.death_timer is not None:
            return
        if action in ("pause", "back"):
            from space_shooter.scenes.pause import PauseScene

            self.game.scenes.push(PauseScene(self.game))
        elif action in ("confirm", "fire"):  # the gamepad's A button takes off at the tug
            self.take_off()
        elif action == "dash":
            self.pending.roll = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            keys = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}
            if event.key in keys:
                self.pending.slot = keys[event.key]
            elif event.key == pygame.K_r:
                self.pending.reload = True
            elif event.key == pygame.K_g:
                self.pending.grenade = True
            elif event.key == pygame.K_q:
                self.pending.order = "follow"
            elif event.key == pygame.K_e:
                self.pending.order = "hold"
        elif event.type == pygame.MOUSEMOTION or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
            self.mouse_aim = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            x, y = self.to_world(event.pos)
            self.pending.order = ("move", x, y)

    def to_world(self, pos) -> tuple[float, float]:
        return (pos[0] + self.camera[0], pos[1] + self.camera[1])

    def _inputs(self) -> GroundInputs:
        if self.inputs_override is not None:
            return self.inputs_override()
        inputs, self.pending = self.pending, GroundInputs()
        inputs.move = self.game.move_vector()
        inputs.aim = self.world.aim
        stick = self._right_stick()
        if stick is not None:
            inputs.aim = (self.world.pilot.x + stick[0] * AIM_STICK, self.world.pilot.y + stick[1] * AIM_STICK)
        elif self.mouse_aim:
            inputs.aim = self.to_world(pygame.mouse.get_pos())
        inputs.fire = self.game.fire_held() or (self.mouse_aim and pygame.mouse.get_pressed()[0])
        return inputs

    def _right_stick(self):
        pad = self.game.joystick
        if pad is None:
            return None
        try:
            axes = (3, 4) if pad.get_numaxes() > 4 else (2, 3)
            x, y = pad.get_axis(axes[0]), pad.get_axis(axes[1])
        except pygame.error:
            return None
        if min(x, y) < -0.98:  # an analogue trigger at rest, not a stick: this pad maps them differently
            return None
        return (x, y) if math.hypot(x, y) > 0.35 else None

    # -- update --------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.game.starfield.update(dt)
        self.explosions = [(p, t - dt) for p, t in self.explosions if t - dt > 0]
        if self.banner:
            self.banner = (self.banner[0], self.banner[1] - dt) if self.banner[1] > dt else None
        if self.notice:
            self.notice = (self.notice[0], self.notice[1] - dt) if self.notice[1] > dt else None
        if self.death_timer is not None:
            self.death_timer -= dt
            if self.death_timer <= 0 and self.result is not None:
                from space_shooter.scenes.loop_end import LoopEndScene

                self.death_timer = float("inf")
                self.game.scenes.push(LoopEndScene(self.game, self.result))
            return
        if self.fight_over:
            return
        if self.run.result is None:
            self.run.time += dt
        for event, value in self.world.step(dt, self._inputs()):
            self._on_event(event, value)
        self._update_camera()

    def _on_event(self, event: str, value) -> None:
        sound = SOUNDS.get(event)
        if sound:
            self.game.audio.play(sound)
        if event == "complete":
            self.run.win_fight(self.node_id, self.encounter.index, self.world.score - self.paid)
            self.paid = self.world.score
            self.banner = (f"{self.game.system.nodes[self.node_id].name} IS TAKEN", BANNER_TIME)
        elif event == "pickup":
            self.notice = (str(value), 2.0)
        elif event == "joined":
            self.notice = ("A SURVIVOR JOINS YOU  -  Q follow   E hold   right-click move", 3.0)
        elif event == "survivor_down":
            self.notice = ("A SURVIVOR IS DOWN", 2.0)
        elif event == "explosion":
            self.explosions.append((value, EXPLOSION_TIME))
        elif event == "pilot_dead":
            self.game.audio.stop_all_loops()
            self.end_loop()
            self.death_timer = DEATH_BEAT

    def _update_camera(self) -> None:
        w, h = self.world.map.size
        p = self.world.pilot
        self.camera = (min(max(0.0, p.x - WIDTH / 2), w - WIDTH), min(max(0.0, p.y - HEIGHT / 2), h - HEIGHT))

    # -- drawing -------------------------------------------------------------
    def to_screen(self, point) -> tuple[int, int]:
        return (round(point[0] - self.camera[0]), round(point[1] - self.camera[1]))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(VOID)
        surface.blit(self.map_image, (-round(self.camera[0]), -round(self.camera[1])))
        world, pulse = self.world, 0.5 + 0.5 * math.sin(self.time * 5)
        if world.map.beacon is not None:
            b = self.to_screen(world.map.beacon)
            pygame.draw.circle(surface, STEEL_DIM, b, int(ground.BEACON_RADIUS), 1)
            pygame.draw.circle(surface, EMBER if world.complete else STEEL, b, 10 + int(4 * pulse))
            if world.hold_time > 0:
                frac = min(1.0, world.hold_time / ground.HOLD_TIME)
                rect = pygame.Rect(0, 0, 60, 60)
                rect.center = b
                pygame.draw.arc(surface, EMBER, rect, math.pi / 2, math.pi / 2 + frac * 2 * math.pi, 4)
        if world.core is not None:
            x, y = self.to_screen(world.core)
            pygame.draw.polygon(surface, EMBER, [(x, y - 10), (x + 8, y), (x, y + 10), (x - 8, y)])
        for kind, x, y in world.pickups:
            sx, sy = self.to_screen((x, y))
            if kind == "crate":
                pygame.draw.rect(surface, BONE, (sx - 9, sy - 9, 18, 18), 2)
                pygame.draw.line(surface, BONE, (sx - 9, sy), (sx + 9, sy), 1)
            else:
                pygame.draw.rect(surface, STEEL, (sx - 5, sy - 4, 10, 8))
        for n in world.nests:
            x, y = self.to_screen(n.body.pos)
            if n.alive:
                pygame.draw.circle(surface, RUST, (x, y), int(n.body.radius + 3 * pulse))
                pygame.draw.circle(surface, EMBER, (x, y), 6 + int(3 * pulse))
            else:
                pygame.draw.circle(surface, STEEL_DIM, (x, y), int(n.body.radius), 2)
        for e in world.enemies:
            self._draw_enemy(surface, e)
        for s in world.survivors:
            self._draw_survivor(surface, s)
        for shot in world.shots:
            x, y = self.to_screen((shot.x, shot.y))
            if shot.friendly:
                pygame.draw.line(surface, BONE, (x, y), (x - shot.vx * 0.012, y - shot.vy * 0.012), 2)
            else:
                pygame.draw.circle(surface, EMBER, (x, y), 4)
        for g in world.grenades:
            x, y = self.to_screen((g.x, g.y))
            pygame.draw.circle(surface, EMBER if int(self.time * 10) % 2 else ASH, (x, y), 5)
        for pos, t in self.explosions:
            r = int(ground.GRENADE_RADIUS * (1 - t / EXPLOSION_TIME))
            pygame.draw.circle(surface, EMBER, self.to_screen(pos), max(2, r), 3)
        self._draw_pilot(surface)
        px, py = self.to_screen(world.pilot.pos)
        surface.blit(self.veil, (px - WIDTH, py - HEIGHT))
        self._draw_hud(surface)

    def _draw_enemy(self, surface, e) -> None:
        x, y = self.to_screen(e.pos)
        r = int(e.body.radius)
        if e.kind == "crawler":
            for i in range(6):
                a = i * math.pi / 3 + self.time * 6
                pygame.draw.line(surface, RUST, (x, y), (x + math.cos(a) * (r + 4), y + math.sin(a) * (r + 4)), 2)
            pygame.draw.circle(surface, RUST, (x, y), r - 3)
        else:
            pygame.draw.circle(surface, EMBER, (x, y), r)
            pygame.draw.circle(surface, VOID, (x, y), r // 3)

    def _draw_survivor(self, surface, s) -> None:
        if not s.alive:
            x, y = self.to_screen(s.pos)
            pygame.draw.line(surface, STEEL_DIM, (x - 8, y - 8), (x + 8, y + 8), 2)
            pygame.draw.line(surface, STEEL_DIM, (x + 8, y - 8), (x - 8, y + 8), 2)
            return
        x, y = self.to_screen(s.pos)
        colour = STEEL if s.state != "waiting" else STEEL_DIM
        pygame.draw.circle(surface, colour, (x, y), int(s.body.radius))
        if s.state == "waiting" and int(self.time * 2) % 2:
            draw_text(surface, "!", 20, (x, y - 24), BONE)
        elif s.state != "waiting":
            draw_bar(surface, pygame.Rect(x - 12, y - 22, 24, 4), s.body.hp / s.body.max_hp, STEEL)

    def _draw_pilot(self, surface) -> None:
        w = self.world
        x, y = self.to_screen(w.pilot.pos)
        a = math.atan2(w.aim[1] - w.pilot.y, w.aim[0] - w.pilot.x)
        colour = ASH if w.rolling else BONE
        pygame.draw.line(surface, STEEL, (x, y), (x + math.cos(a) * 20, y + math.sin(a) * 20), 4)
        pygame.draw.circle(surface, colour, (x, y), int(w.pilot.radius))
        if w.carrying:
            pygame.draw.polygon(surface, EMBER, [(x, y - 22), (x + 6, y - 15), (x, y - 8), (x - 6, y - 15)])
        cx, cy = self.to_screen(w.aim)
        pygame.draw.circle(surface, BONE, (cx, cy), 8, 1)
        pygame.draw.line(surface, BONE, (cx - 12, cy), (cx - 4, cy), 1)
        pygame.draw.line(surface, BONE, (cx + 4, cy), (cx + 12, cy), 1)

    def _draw_hud(self, surface) -> None:
        w, a = self.world, self.world.arsenal
        name = self.game.system.nodes[self.node_id].name
        draw_text(surface, name, 20, (20, 14), BONE, "topleft")
        draw_bar(surface, pygame.Rect(20, 42, 180, 10), max(0.0, w.pilot.hp) / w.pilot.max_hp, STEEL)
        draw_text(surface, f"HEALTH {max(0, round(w.pilot.hp))}", 16, (206, 47), ASH, "midleft")
        weapon = a.weapon
        ammo = "unlimited" if weapon.mag is None else f"{a.mag[a.current]} / {a.reserve[a.current]}"
        if a.reloading > 0:
            ammo = "RELOADING"
        draw_text(surface, f"{weapon.name}  {ammo}", 18, (20, HEIGHT - 58), BONE, "topleft")
        slots = "   ".join(f"{i + 1} {ground.WEAPONS[k].name}" for i, k in enumerate(ground.SLOTS) if k in a.owned)
        draw_text(surface, f"{slots}   G grenades {a.grenades}", 14, (20, HEIGHT - 34), ASH, "topleft")
        squad = [s for s in w.survivors if s.state != "waiting" or not s.alive]
        for i, s in enumerate(squad):
            label = "DOWN" if not s.alive else s.state.upper()
            draw_text(surface, f"SURVIVOR {i + 1}  {label}", 14, (WIDTH - 20, 16 + i * 18), STEEL, "topright")
        draw_text(surface, w.objective_text(), 20, (WIDTH // 2, 16), EMBER if w.complete else BONE)
        if w.complete and w.at_pad():
            draw_text(surface, "ENTER  TAKE OFF", 24, (WIDTH // 2, HEIGHT - 110), EMBER)
        if self.banner:
            draw_text(surface, self.banner[0], 34, (WIDTH // 2, HEIGHT // 2 - 120), BONE)
        if self.notice:
            draw_text(surface, self.notice[0], 18, (WIDTH // 2, 44), STEEL)
