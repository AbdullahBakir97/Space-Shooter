import pygame
from scripts.settings import WHITE, BLACK, WIDTH, HEIGHT
from scripts.game_functions import draw_text

class Menu:
    def __init__(self):
        self.options = ["Start Game", "Settings", "Exit"]
        self.selected = 0

    def draw(self, screen):
        screen.fill(BLACK)
        for i, option in enumerate(self.options):
            color = WHITE if i == self.selected else (100, 100, 100)
            draw_text(screen, option, 36, WIDTH // 2, HEIGHT // 2 + i * 50)

    def update(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.options[self.selected]
        return None

    def draw_settings(self, screen):
        screen.fill(BLACK)
        draw_text(screen, "Settings", 48, WIDTH // 2, HEIGHT // 4)
        draw_text(screen, "Press ESC to return to the menu", 24, WIDTH // 2, HEIGHT // 2)
