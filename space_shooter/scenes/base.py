from __future__ import annotations

import pygame


class Scene:
    """A screen in the game. Transparent scenes are drawn over the one beneath."""

    transparent = False

    def __init__(self, game) -> None:
        self.game = game

    def on_enter(self) -> None: ...

    def on_exit(self) -> None: ...

    def handle_event(self, event: pygame.event.Event) -> None: ...

    def handle_action(self, action: str) -> None: ...

    def update(self, dt: float) -> None: ...

    def draw(self, surface: pygame.Surface) -> None: ...


class SceneManager:
    def __init__(self) -> None:
        self.stack: list[Scene] = []

    @property
    def top(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)
        scene.on_enter()

    def pop(self) -> None:
        if self.stack:
            self.stack.pop().on_exit()

    def replace(self, scene: Scene) -> None:
        self.pop()
        self.push(scene)

    def clear_to(self, scene: Scene) -> None:
        while self.stack:
            self.pop()
        self.push(scene)

    def draw(self, surface: pygame.Surface) -> None:
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].transparent:
            start -= 1
        for scene in self.stack[start:]:
            scene.draw(surface)
