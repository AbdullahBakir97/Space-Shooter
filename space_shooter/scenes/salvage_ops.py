"""Salvage part behaviour that needs the whole scene: claw, tractor, drag field, shrapnel.

Kept out of gameplay.py so the scene stays a coordinator.
"""

from __future__ import annotations

import math

from space_shooter.salvage import SLOT_OFFSETS

CLAW_RADIUS = 20.0
CLAW_DAMAGE = 2
CLAW_DAMAGE_RARE = 3
CLAW_COOLDOWN = 0.3


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
