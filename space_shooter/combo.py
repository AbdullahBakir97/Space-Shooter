"""Kill-chain multiplier. Pure logic."""

from __future__ import annotations

from space_shooter.config import COMBO_MAX, COMBO_WINDOW


class Combo:
    def __init__(self, window: float = COMBO_WINDOW, max_mult: int = COMBO_MAX) -> None:
        self.window = window
        self.max_mult = max_mult
        self.multiplier = 1
        self.chain = 0
        self.timer = 0.0

    def register_kill(self) -> int:
        """Record a kill and return the multiplier that applies to it."""
        self.chain += 1
        self.timer = self.window
        # every 3 chained kills bumps the multiplier
        self.multiplier = min(self.max_mult, 1 + self.chain // 3)
        return self.multiplier

    def update(self, dt: float) -> bool:
        """Advance time; return True the frame the chain breaks."""
        if self.chain == 0:
            return False
        self.timer -= dt
        if self.timer <= 0:
            self.reset()
            return True
        return False

    def reset(self) -> None:
        self.chain = 0
        self.multiplier = 1
        self.timer = 0.0

    @property
    def fraction(self) -> float:
        """Remaining fraction of the combo window, for the HUD bar."""
        return max(0.0, self.timer / self.window) if self.chain else 0.0
