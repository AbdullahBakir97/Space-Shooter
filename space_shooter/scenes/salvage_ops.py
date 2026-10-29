"""Salvage part behaviour that needs the whole scene: claw, tractor, drag field, shrapnel.

Kept out of gameplay.py so the scene stays a coordinator.
"""

from __future__ import annotations

import math

import pygame

from space_shooter.entities.bullets import PlayerBullet
from space_shooter.salvage import SLOT_OFFSETS

CLAW_RADIUS = 20.0
CLAW_DAMAGE = 2
CLAW_DAMAGE_RARE = 3
CLAW_COOLDOWN = 0.3
TRACTOR_SPEED = 260.0
DRAG_RADIUS = 150.0
DRAG_SCALE = 0.6
SHRAPNEL_COUNT = 10
SHRAPNEL_SPEED = 520.0


def claw_contacts(scene, dt: float) -> None:
    """Enemies touching a claw take damage (once per 0.3 s each); claw kills always drop."""
    player = scene.player
    cooldowns: dict[int, float] = scene.__dict__.setdefault("claw_cooldowns", {})
    for key in list(cooldowns):
        cooldowns[key] -= dt
        if cooldowns[key] <= 0:
            del cooldowns[key]
    claws = [(slot, part) for slot, part in player.loadout.parts() if part.kind == "claw"]
    if not claws:
        return
    for slot, part in claws:
        cx, cy = player.x + SLOT_OFFSETS[slot][0], player.y + SLOT_OFFSETS[slot][1]
        for enemy in list(scene.enemies):
            if id(enemy) in cooldowns or not enemy.alive():
                continue
            reach = CLAW_RADIUS + getattr(enemy, "radius", 0)
            if math.hypot(enemy.x - cx, enemy.y - cy) > reach:
                continue
            cooldowns[id(enemy)] = CLAW_COOLDOWN
            if enemy.hit(CLAW_DAMAGE_RARE if part.rare else CLAW_DAMAGE):
                scene._kill_enemy(enemy, force_drop=not enemy.is_boss)


def tractor(scene, dt: float) -> tuple[float, float] | None:
    """Pull drops toward the ship; return the position the beam is locked on, if any.

    Knocked-off parts are reeled in from any range; other drops from ``tractor_range()``.
    """
    loadout = scene.player.loadout
    reach = loadout.tractor_range()
    if reach <= 0:
        return None
    px, py = scene.player.x, scene.player.y
    strength = loadout.effect("tractor")
    beam: tuple[float, float] | None = None
    best = math.inf
    for drop in scene.drops:
        dist = math.hypot(px - drop.x, py - drop.y)
        if dist > reach and drop.lifetime is None:
            continue
        if dist < best:
            best, beam = dist, (drop.x, drop.y)
        step = min(dist, TRACTOR_SPEED * strength * dt)
        if dist > 0:
            drop.x += (px - drop.x) / dist * step
            drop.y += (py - drop.y) / dist * step
    return beam


def drag_field(scene) -> None:
    """With a tractor fitted, enemy bullets close to the ship slow down."""
    active = scene.player.loadout.count("tractor") > 0 and scene.player.alive_in_world
    px, py = scene.player.x, scene.player.y
    for bullet in scene.enemy_bullets:
        near = active and math.hypot(bullet.x - px, bullet.y - py) <= DRAG_RADIUS
        bullet.speed_scale = DRAG_SCALE if near else 1.0


def shrapnel(scene, pos) -> None:
    """A breaking armour plate bursts outward. Shrapnel is friendly: it only hits enemies."""
    for i in range(SHRAPNEL_COUNT):
        angle = math.tau * i / SHRAPNEL_COUNT
        vel = (math.cos(angle) * SHRAPNEL_SPEED, math.sin(angle) * SHRAPNEL_SPEED)
        shard = PlayerBullet(pos, vel, 1)
        shard.image = pygame.transform.rotate(shard.image, 90 - math.degrees(angle))  # point along its flight
        shard.rect = shard.image.get_rect(center=shard.rect.center)
        scene.player_bullets.add(shard)
