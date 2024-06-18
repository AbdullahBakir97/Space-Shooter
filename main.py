import pygame
import sys
from scripts.settings import *
from scripts.sprites import Player, Enemy, Bullet, PowerUp
from scripts.game_functions import check_collisions, draw_text, spawn_enemies, spawn_boss, save_high_score, load_high_scores, draw_high_scores
from scripts.menu import Menu
from scripts.sounds import load_sounds

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Shooter")
clock = pygame.time.Clock()

# Load assets
background_img = pygame.image.load("images/background.png").convert()

# Load sounds
shoot_sound, explosion_sound, powerup_sound = load_sounds()

# Initialize groups
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
bullets = pygame.sprite.Group()
powerups = pygame.sprite.Group()

# Initialize player
player = Player()
all_sprites.add(player)

# Initialize menu
menu = Menu()

# Game state variables
score = 0
level = 1
state = "menu"

# Main game loop
running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if state == "menu":
        selected_option = menu.update(event)
        if selected_option == "Start Game":
            state = "game"
            spawn_enemies(level, enemies, all_sprites)
        elif selected_option == "Settings":
            state = "settings"
        elif selected_option == "Exit":
            running = False
        menu.draw(screen)
    elif state == "settings":
        menu.draw_settings(screen)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            state = "menu"
    elif state == "game":
        all_sprites.update()
        check_collisions(player, enemies, bullets, powerups, all_sprites, score)
        if len(enemies) == 0:
            level += 1
            if level % 5 == 0:
                spawn_boss(all_sprites, enemies)
            else:
                spawn_enemies(level, enemies, all_sprites)

        screen.fill(BLACK)
        screen.blit(background_img, (0, 0))
        all_sprites.draw(screen)
        draw_text(screen, f"Score: {score}", 18, WIDTH // 2, 10)
        draw_text(screen, f"Health: {player.health}", 18, WIDTH - 100, 10)
        pygame.display.flip()

        if player.health <= 0:
            save_high_score(score)
            high_scores = load_high_scores()
            draw_high_scores(screen, high_scores)
            pygame.display.flip()
            pygame.time.wait(2000)
            state = "menu"

pygame.quit()
sys.exit()
