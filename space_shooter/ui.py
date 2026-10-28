"""Small drawing helpers and a keyboard-driven menu list."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from space_shooter import assets
from space_shooter.palette import ASH, BONE, STEEL, STEEL_DIM

Anchor = str  # "center", "topleft", "topright", "midtop", "midleft", "midright", "midbottom"


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    pos: tuple[int, int],
    colour=BONE,
    anchor: Anchor = "center",
    shadow: bool = True,
) -> pygame.Rect:
    fnt = assets.font(size)
    if shadow:
        sh = fnt.render(text, True, (0, 0, 0))
        rect = sh.get_rect(**{anchor: (pos[0] + 2, pos[1] + 2)})
        surface.blit(sh, rect)
    img = fnt.render(text, True, colour)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def draw_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fraction: float,
    colour,
    back=(30, 34, 50),
    border=STEEL_DIM,
) -> None:
    fraction = min(1.0, max(0.0, fraction))
    pygame.draw.rect(surface, back, rect, border_radius=3)
    if fraction > 0:
        inner = rect.copy()
        inner.width = max(2, int(rect.width * fraction))
        pygame.draw.rect(surface, colour, inner, border_radius=3)
    pygame.draw.rect(surface, border, rect, 1, border_radius=3)


class MenuItem:
    """A menu row. ``value`` returns the text shown after the label, if any;
    ``adjust`` handles left/right; ``activate`` handles confirm."""

    def __init__(
        self,
        label: str,
        activate: Callable[[], None] | None = None,
        value: Callable[[], str] | None = None,
        adjust: Callable[[int], None] | None = None,
    ) -> None:
        self.label = label
        self.activate = activate
        self.value = value
        self.adjust = adjust

    def text(self) -> str:
        return f"{self.label}:  {self.value()}" if self.value else self.label


class MenuList:
    def __init__(self, items: Sequence[MenuItem], on_move: Callable[[], None] | None = None, on_select=None) -> None:
        self.items = list(items)
        self.index = 0
        self.on_move = on_move
        self.on_select = on_select
        self.time = 0.0

    def handle_action(self, action: str) -> bool:
        """Return True if the action was consumed."""
        item = self.items[self.index]
        if action == "up":
            self.index = (self.index - 1) % len(self.items)
        elif action == "down":
            self.index = (self.index + 1) % len(self.items)
        elif action in ("left", "right"):
            if not item.adjust:
                return False
            item.adjust(-1 if action == "left" else 1)
        elif action == "confirm":
            if item.adjust and not item.activate:
                item.adjust(1)
            elif item.activate:
                if self.on_select:
                    self.on_select()
                item.activate()
                return True
            else:
                return False
        else:
            return False
        if self.on_move and action != "confirm":
            self.on_move()
        return True

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface, top: int, spacing: int = 48, size: int = 40) -> None:
        cx = surface.get_width() // 2
        for i, item in enumerate(self.items):
            selected = i == self.index
            colour = BONE if selected else ASH
            y = top + i * spacing
            rect = draw_text(surface, item.text(), size, (cx, y), colour)
            if selected:
                pulse = 6 + int(3 * abs(pygame.math.Vector2(1, 0).rotate(self.time * 360).x))
                draw_text(surface, ">", size, (rect.left - 18 - pulse, y), STEEL)
                draw_text(surface, "<", size, (rect.right + 18 + pulse, y), STEEL)


def dim_overlay(surface: pygame.Surface, alpha: int = 150) -> None:
    veil = pygame.Surface(surface.get_size())
    veil.fill((0, 0, 0))
    veil.set_alpha(alpha)
    surface.blit(veil, (0, 0))


HINT_COLOUR = STEEL_DIM
