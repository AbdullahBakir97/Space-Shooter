"""Thruster dash state: charges, recharge and the active window. Pure module."""

from __future__ import annotations

DASH_TIME = 0.18
DASH_SPEED = 1100.0


class Dash:
    def __init__(self, max_charges: int, recharge: float) -> None:
        self.max_charges = max_charges
        self.recharge = recharge
        self.charges = max_charges
        self.remaining = 0.0
        self._refill = 0.0  # progress toward the next charge, seconds

    @property
    def active(self) -> bool:
        return self.remaining > 0

    @property
    def recharge_fraction(self) -> float:
        """How far the next charge has refilled (0 when full or no thrusters)."""
        if self.charges >= self.max_charges or self.recharge <= 0:
            return 0.0
        return min(1.0, self._refill / self.recharge)

    def configure(self, max_charges: int, recharge: float) -> None:
        """Follow the loadout: each newly fitted thruster brings one charge; losing one removes it."""
        if max_charges > self.max_charges:
            self.charges += max_charges - self.max_charges
        self.max_charges = max_charges
        self.recharge = recharge
        self.charges = min(self.charges, max_charges)

    def try_start(self) -> bool:
        if self.charges <= 0 or self.active:
            return False
        self.charges -= 1
        self.remaining = DASH_TIME
        return True

    def update(self, dt: float) -> None:
        self.remaining = max(0.0, self.remaining - dt)
        if self.charges >= self.max_charges:
            self._refill = 0.0
            return
        self._refill += dt
        while self._refill >= self.recharge and self.charges < self.max_charges:
            self._refill -= self.recharge
            self.charges += 1
